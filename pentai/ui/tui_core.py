from io import StringIO
from rich.console import Console

def render_to_ansi(renderable, width: int = 100) -> str:
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor",
                      width=width, soft_wrap=False)
    console.print(renderable)
    return buf.getvalue()

class TurnQueue:
    def __init__(self) -> None:
        self._items: list[str] = []

    def enqueue(self, msg: str) -> None:
        if msg.strip():
            self._items.append(msg)

    def pop(self) -> str | None:
        return self._items.pop(0) if self._items else None

    def __len__(self) -> int:
        return len(self._items)

    @property
    def pending(self) -> list[str]:
        return list(self._items)
