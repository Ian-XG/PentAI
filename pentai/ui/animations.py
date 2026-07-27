import random
from typing import Callable

_GLITCH_CHARS = "!@#$%&*/\\|<>=+-_?01"

def run_once(fn: Callable[[], None]) -> Callable[[], None]:
    state = {"done": False}
    def wrapper() -> None:
        if not state["done"]:
            state["done"] = True
            fn()
    return wrapper

def glitch_frames(text: str, frames: int = 6, rng=None) -> list[str]:
    rng = rng or random.Random()
    positions = [i for i, c in enumerate(text) if not c.isspace()]
    out: list[str] = []
    for _ in range(frames):
        chars = list(text)
        if positions:
            k = max(1, (len(positions) * 2) // 5)
            for i in rng.sample(positions, min(k, len(positions))):
                chars[i] = rng.choice(_GLITCH_CHARS)
        out.append("".join(chars))
    out.append(text)
    return out
