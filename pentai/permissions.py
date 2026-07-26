MODES: list[str] = ["ask", "auto", "bypass"]

def next_mode(mode: str) -> str:
    if mode not in MODES:
        return MODES[0]
    return MODES[(MODES.index(mode) + 1) % len(MODES)]

def should_prompt_exec(mode: str) -> bool:
    return mode == "ask"

def should_prompt_oos(mode: str) -> bool:
    return mode != "bypass"
