SIGIL = r"""
                  ◈
        ╲╲╲╲     ╱│╲     ╱╱╱╱
      ╲╲╲╲╲╲    ╱ │ ╲    ╱╱╱╱╱╱
    ▚▚▚▚▚▚▚▚   ╱  │  ╲   ▞▞▞▞▞▞▞▞
  ◄═══════════════│═══════════════►
                 ╲│╱
                  │
                  ▼
      P   E   N   T   A   I
"""

# The core (apex, center stem, arrowheads, wordmark) reads bright/bold; the
# surrounding struts stay dim - depth instead of one flat wash of color.
# isalpha() picks out the wordmark on its own; everything else is matched by
# character, so this needs no fragile index/column math to stay in sync with
# SIGIL's exact spacing.
_SIGIL_CORE_CHARS = frozenset("◈│═►◄▼")

def render_sigil_rich(accent: str, dim: str):
    from rich.text import Text
    text = Text()
    lines = SIGIL.strip("\n").split("\n")
    for i, line in enumerate(lines):
        for ch in line:
            style = f"bold {accent}" if (ch in _SIGIL_CORE_CHARS or ch.isalpha()) else dim
            text.append(ch, style=style)
        if i < len(lines) - 1:
            text.append("\n")
    return text

def boot_lines() -> list[str]:
    return [
        "[ OK ] initializing modules",
        "[ OK ] loading playbooks",
        "[ OK ] provider adapters online",
        "[ OK ] scope guard armed",
    ]
