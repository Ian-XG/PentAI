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


def build_app(*, output: OutputBuffer,
              on_submit: Callable[[str], None],
              on_stop: Callable[[], None],
              on_cycle_mode: Callable[[], None],
              get_status: Callable[[], str],
              pt_input=None, pt_output=None) -> Application:

    def accept(buff: Buffer) -> bool:
        text = buff.text
        on_submit(text)
        return False  # clear the input after submit

    input_area = TextArea(prompt="> ", multiline=False, accept_handler=accept)
    input_frame = Frame(input_area, title="message")

    output_window = Window(
        content=FormattedTextControl(lambda: ANSI(output.text()), focusable=False),
        wrap_lines=True,
    )
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

    return Application(
        layout=Layout(root, focused_element=input_area),
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
        input=pt_input,
        output=pt_output,
    )
