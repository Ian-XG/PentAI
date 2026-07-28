import shutil
from typing import Callable

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import ConditionalContainer, Layout, HSplit, Window
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.widgets import Frame, TextArea
from rich.text import Text

from pentai.ui.tui_core import render_to_ansi


class OutputBuffer:
    def __init__(self) -> None:
        self._renderers: list = []
        self._version = 0
        self._cache_width = None
        self._cache_version = -1
        self._cache_text = ""

    def append_renderer(self, fn) -> None:
        # fn: Callable[[int], str] rendering ANSI at the given width
        self._renderers.append(fn)
        self._version += 1

    def append(self, renderable, theme=None) -> None:
        self.append_renderer(lambda w, r=renderable, t=theme: render_to_ansi(r, width=w, theme=t))

    def append_full_width(self, text: str, style: str) -> None:
        # a highlight bar padded to the CURRENT width at render time (so it reflows on resize)
        self.append_renderer(lambda w, s=text, st=style: render_to_ansi(Text(s.ljust(w), style=st), width=w))

    def clear(self) -> None:
        self._renderers.clear()
        self._version += 1

    def render(self, width: int) -> str:
        if width == self._cache_width and self._version == self._cache_version:
            return self._cache_text
        text = "".join(fn(width) for fn in self._renderers)
        self._cache_width = width
        self._cache_version = self._version
        self._cache_text = text
        return text

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

    input_area = TextArea(prompt="> ", multiline=False, accept_handler=accept)
    input_frame = Frame(input_area, title="message")

    def _output_rows() -> int:
        # rows available for the output region: total minus input frame (3) and status (1) and a margin
        return max(1, shutil.get_terminal_size((100, 24)).lines - 5)

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
        content=Window(content=FormattedTextControl(lambda: [("bold", " " + (get_thinking() or "") + " ")]), height=1),
        filter=Condition(lambda: get_thinking() is not None),
    )

    root = HSplit([output_window, jump_bar, thinking_bar, input_frame, status_window])

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
        full_screen=True,
        mouse_support=True,
        input=pt_input,
        output=pt_output,
        refresh_interval=0.5,
    )
