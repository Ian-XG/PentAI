import shutil
from typing import Callable, TypeVar

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from rich.text import Text

from .theme import get_palette
from .tui_core import render_to_ansi

T = TypeVar("T")

HINT = "↑/↓ navigate · enter select · esc cancel"


def move_index(idx: int, direction: int, length: int) -> int:
    """Pure index math for the selector: current index + direction (-1/+1),
    clamped to [0, length-1]. Clamps at the ends rather than wrapping."""
    if length <= 0:
        return idx
    return max(0, min(length - 1, idx + direction))


def _render(options: list[T], active_idx: int, title: str,
           render_row: Callable[[T, bool], str], palette: dict) -> Text:
    accent = palette["accent"]
    dim = palette["dim"]
    out = Text()
    out.append(title + "\n", style=f"bold {accent}")
    out.append("\n")
    for i, opt in enumerate(options):
        selected = i == active_idx
        label = render_row(opt, selected)
        if selected:
            out.append(f"❯ {label}\n", style=f"bold {accent}")
        else:
            out.append(f"  {label}\n", style=dim)
    out.append("\n")
    out.append(HINT, style=dim)
    return out


def select(options: list[T], *, title: str, render_row: Callable[[T, bool], str],
          active_index: int = 0, palette: dict | None = None,
          pt_input=None, pt_output=None) -> int | None:
    """Inline (non-full-screen) arrow-key selector, like the pickers in Claude
    Code / OpenClaw / Hermes Agent. Up/Down (or k/j) move the highlight (clamped,
    no wraparound); Enter confirms and returns the selected index; Esc, Ctrl-C,
    and Ctrl-D cancel and return None. Renders inline so it doesn't take over
    the whole screen."""
    if not options:
        return None
    palette = palette or get_palette("green")
    n = len(options)
    state = {"idx": max(0, min(active_index, n - 1))}
    result: dict = {"value": None}

    def _width() -> int:
        return shutil.get_terminal_size((100, 24)).columns

    def get_text():
        return ANSI(render_to_ansi(_render(options, state["idx"], title, render_row, palette),
                                   width=_width()))

    control = FormattedTextControl(get_text, focusable=True)
    window = Window(content=control, height=n + 4)

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event) -> None:
        state["idx"] = move_index(state["idx"], -1, n)
        event.app.invalidate()

    @kb.add("down")
    @kb.add("j")
    def _down(event) -> None:
        state["idx"] = move_index(state["idx"], 1, n)
        event.app.invalidate()

    @kb.add("enter")
    def _confirm(event) -> None:
        result["value"] = state["idx"]
        event.app.exit()

    @kb.add("escape")
    @kb.add("c-c")
    @kb.add("c-d")
    def _cancel(event) -> None:
        result["value"] = None
        event.app.exit()

    app = Application(layout=Layout(window), key_bindings=kb, full_screen=False,
                      input=pt_input, output=pt_output)
    app.run()
    return result["value"]
