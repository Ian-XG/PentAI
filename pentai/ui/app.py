import shutil
from typing import Callable

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import Frame, TextArea


class OutputBuffer:
    def __init__(self) -> None:
        self._text = ""

    def append(self, ansi: str) -> None:
        self._text += ansi

    def text(self) -> str:
        return self._text

    def clear(self) -> None:
        self._text = ""

    def visible(self, rows: int, offset: int = 0) -> str:
        lines = self._text.split("\n")
        if rows <= 0 or len(lines) <= rows:
            return self._text
        end = len(lines) - offset
        end = max(rows, min(end, len(lines)))   # clamp so a full window is always shown
        start = max(0, end - rows)
        return "\n".join(lines[start:end])

    def line_count(self) -> int:
        return self._text.count("\n") + 1


def build_app(*, output: OutputBuffer,
              on_submit: Callable[[str], None],
              on_stop: Callable[[], None],
              on_cycle_mode: Callable[[], None],
              get_status: Callable[[], str],
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

    output_control = FormattedTextControl(
        lambda: ANSI(output.visible(_output_rows(), scroll["offset"])), focusable=False
    )
    output_window = Window(content=output_control, wrap_lines=True)
    status_window = Window(
        content=FormattedTextControl(lambda: get_status()),
        height=1,
    )

    root = HSplit([output_window, input_frame, status_window])

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
        rows = _output_rows()
        max_offset = max(0, output.line_count() - rows)
        scroll["offset"] = min(scroll["offset"] + rows, max_offset)
        event.app.invalidate()

    @kb.add("pagedown")
    def _(event) -> None:
        scroll["offset"] = max(0, scroll["offset"] - _output_rows())
        event.app.invalidate()

    @kb.add("end")
    @kb.add("c-e")
    def _(event) -> None:
        scroll["offset"] = 0
        event.app.invalidate()

    return Application(
        layout=Layout(root, focused_element=input_area),
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
        input=pt_input,
        output=pt_output,
    )
