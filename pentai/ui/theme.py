PALETTES: dict[str, dict[str, str]] = {
    "green": {"primary": "bold green", "accent": "bright_green", "dim": "green dim", "alert": "bold red"},
    "amber": {"primary": "bold yellow", "accent": "bright_yellow", "dim": "yellow dim", "alert": "bold red"},
    "red":   {"primary": "bold red", "accent": "bright_red", "dim": "red dim", "alert": "bold white on red"},
}

def get_palette(name: str) -> dict[str, str]:
    return PALETTES.get(name, PALETTES["green"])
