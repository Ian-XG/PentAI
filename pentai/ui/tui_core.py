import shutil
from io import StringIO
from rich.console import Console

def render_to_ansi(renderable, width: int | None = None, theme=None) -> str:
    w = shutil.get_terminal_size((100, 24)).columns if width is None else width
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor",
                      width=w, soft_wrap=False, theme=theme)
    console.print(renderable)
    return buf.getvalue()

def format_thinking(chars: int, elapsed_seconds: float) -> str:
    tokens = chars // 4  # rough token estimate from streamed characters
    tok = f"{tokens/1000:.1f}k" if tokens >= 1000 else str(tokens)
    secs = int(elapsed_seconds)
    t = f"{secs//60}m {secs%60}s" if secs >= 60 else f"{secs}s"
    return f"Thinking... ({tok} tokens - {t})"

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
