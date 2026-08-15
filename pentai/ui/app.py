import shutil
from typing import Callable

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import ConditionalContainer, Layout, HSplit, Window
from prompt_toolkit.layout.containers import WindowAlign, FloatContainer, Float
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea
from rich.text import Text

from pentai.commands import SLASH_COMMANDS
from pentai.ui.tui_core import render_to_ansi, output_rows

# Phosphor-green theme for the "/" completion dropdown, so it matches the TUI
# instead of prompt_toolkit's default light-gray menu. Selected row is inverted
# (dark on green); descriptions render dim; scrollbar picks up the accent.
MENU_STYLE = Style.from_dict({
    "completion-menu": "bg:#0a0f0a",
    "completion-menu.completion": "bg:#0a0f0a #46e08a",
    "completion-menu.completion.current": "bg:#46e08a #05070a bold",
    "completion-menu.meta.completion": "bg:#0a0f0a #2f7d54",
    "completion-menu.meta.completion.current": "bg:#2f7d54 #d7ffe6",
    "scrollbar.background": "bg:#12321f",
    "scrollbar.button": "bg:#46e08a",
})


class SlashCompleter(Completer):
    """Claude-Code-style '/' menu: typing '/' lists every slash command with
    a short description alongside it; narrows as more of the name is typed;
    stops once the first token (command name) is complete and a space follows."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/") or " " in text:
            return
        for name, desc in SLASH_COMMANDS:
            if name.startswith(text):
                yield Completion(name, start_position=-len(text), display_meta=desc)


class OutputBuffer:
    def __init__(self) -> None:
        self._renderers: list = []
        self._cache_width = None
        self._cache_rendered: list[str] = []   # rendered text per renderer, at _cache_width

    def append_renderer(self, fn) -> None:
        # fn: Callable[[int], str] rendering ANSI at the given width
        self._renderers.append(fn)
        if self._cache_width is not None:
            # render just the new one at the already-known width instead of
            # invalidating everything - cli.py appends a renderer per text
            # delta/tool event during a turn, so re-rendering the WHOLE
            # session on every one of those was O(n) per chunk, O(n^2) over
            # a session. A width change (the only thing that can change how
            # earlier content wraps) still forces a full recompute below.
            self._cache_rendered.append(fn(self._cache_width))

    def append(self, renderable, theme=None) -> None:
        self.append_renderer(lambda w, r=renderable, t=theme: render_to_ansi(r, width=w, theme=t))

    def append_full_width(self, text: str, style: str) -> None:
        # a highlight bar padded to the CURRENT width at render time (so it reflows on resize)
        self.append_renderer(lambda w, s=text, st=style: render_to_ansi(Text(s.ljust(w), style=st), width=w))

    def clear(self) -> None:
        self._renderers.clear()
        self._cache_rendered.clear()

    def render(self, width: int) -> str:
        if width != self._cache_width:
            self._cache_width = width
            self._cache_rendered = [fn(width) for fn in self._renderers]
        return "".join(self._cache_rendered)

    def line_count(self, width: int) -> int:
        return self.render(width).count("\n") + 1

    def visible(self, rows: int, offset: int, width: int) -> str:
        text = self.render(width)
        lines = text.split("\n")
        if rows <= 0 or len(lines) <= rows:
            return text
        end = len(lines) - offset
        end = max(rows, min(end, len(lines)))   # clamp so a full window is always shown
        start = max(0, end - rows)
        return "\n".join(lines[start:end])


def build_app(*, output: OutputBuffer,
              on_submit: Callable[[str], None],
              on_stop: Callable[[], None],
              on_cycle_mode: Callable[[], None],
              get_status: Callable[[], str],
              get_thinking: Callable[[], str | None] = lambda: None,
              pt_input=None, pt_output=None) -> Application:

    scroll = {"offset": 0}

    def accept(buff: Buffer) -> bool:
        text = buff.text
        scroll["offset"] = 0
        on_submit(text)
        return False  # clear the input after submit

    input_area = TextArea(prompt="> ", multiline=False, accept_handler=accept,
                          completer=SlashCompleter(), complete_while_typing=True)
    input_frame = Frame(input_area, title="message")

    def _output_rows() -> int:
        return output_rows(shutil.get_terminal_size((100, 24)).lines,
                           scrolled=scroll["offset"] > 0, thinking=get_thinking() is not None)

    def _output_width() -> int:
        return max(20, shutil.get_terminal_size((100, 24)).columns)

    def _max_offset() -> int:
        return max(0, output.line_count(_output_width()) - _output_rows())

    def _scroll_up(n: int = 3) -> None:
        scroll["offset"] = min(_max_offset(), scroll["offset"] + n)

    def _scroll_down(n: int = 3) -> None:
        scroll["offset"] = max(0, scroll["offset"] - n)

    def _to_bottom() -> None:
        scroll["offset"] = 0

    def _output_mouse(mouse_event):
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            _scroll_up()
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            _scroll_down()
        else:
            return NotImplemented
        return None

    output_control = FormattedTextControl(
        lambda: ANSI(output.visible(_output_rows(), scroll["offset"], _output_width())), focusable=False
    )
    output_control.mouse_handler = _output_mouse
    output_window = Window(content=output_control, wrap_lines=True)

    def _jump_fragments():
        def handler(mouse_event):
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                _to_bottom()
            return None
        return [("reverse bold", " ↓ Jump to bottom (End) ", handler)]

    jump_bar = ConditionalContainer(
        content=Window(content=FormattedTextControl(_jump_fragments), height=1, align=WindowAlign.CENTER),
        filter=Condition(lambda: scroll["offset"] > 0),
    )

    status_window = Window(
        content=FormattedTextControl(lambda: get_status()),
        height=1,
    )

    thinking_bar = ConditionalContainer(
        content=Window(content=FormattedTextControl(lambda: [("bold ansibrightgreen", " " + (get_thinking() or "") + " ")]), height=1),
        filter=Condition(lambda: get_thinking() is not None),
    )

    # FloatContainer + CompletionsMenu is what actually renders the "/" dropdown;
    # a custom full-screen Application has no completions menu unless we add one.
    root = FloatContainer(
        content=HSplit([output_window, jump_bar, thinking_bar, input_frame, status_window]),
        floats=[
            Float(xcursor=True, ycursor=True,
                  content=CompletionsMenu(max_height=10, scroll_offset=1)),
        ],
    )

    kb = KeyBindings()

    @kb.add("c-c")
    @kb.add("c-d")
    def _(event) -> None:
        event.app.exit()

    @kb.add("s-tab")
    def _(event) -> None:
        on_cycle_mode()
        event.app.invalidate()

    @kb.add("escape", eager=True)
    def _(event) -> None:
        on_stop()

    @kb.add("pageup")
    def _(event) -> None:
        _scroll_up(_output_rows())
        event.app.invalidate()

    @kb.add("pagedown")
    def _(event) -> None:
        _scroll_down(_output_rows())
        event.app.invalidate()

    @kb.add("end")
    @kb.add("c-e")
    def _(event) -> None:
        _to_bottom()
        event.app.invalidate()

    return Application(
        layout=Layout(root, focused_element=input_area),
        key_bindings=kb,
        style=MENU_STYLE,
        full_screen=True,
        mouse_support=True,
        input=pt_input,
        output=pt_output,
        refresh_interval=0.5,
    )
