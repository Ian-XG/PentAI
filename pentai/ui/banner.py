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

SIGIL_SIMPLE = r"""
        /|\
   <----+---->
        |
        v
    P E N T A I
"""

def render_banner(palette: dict[str, str], simple: bool = False) -> str:
    art = SIGIL_SIMPLE if simple else SIGIL
    tagline = "[ authorized use only ]"
    return f"{art}\n      {tagline}\n"

def boot_lines() -> list[str]:
    return [
        "[ OK ] initializing modules",
        "[ OK ] loading playbooks",
        "[ OK ] provider adapters online",
        "[ OK ] scope guard armed",
    ]
