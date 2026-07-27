from rich.theme import Theme

_TAGS = {"AI": "[AI]", "EXEC": "[EXEC]", "VULN": "[!] VULN", "INFO": "[INFO]"}

def format_tag(kind: str, text: str) -> str:
    tag = _TAGS.get(kind, _TAGS["INFO"])
    return f"{tag} {text}"

def markdown_theme(palette: dict[str, str]) -> Theme:
    accent = palette["accent"]
    dim = palette["dim"]
    return Theme({
        "markdown.h1": f"bold {accent}",
        "markdown.h2": f"bold {accent}",
        "markdown.h3": accent,
        "markdown.h4": accent,
        "markdown.h5": accent,
        "markdown.h6": accent,
        "markdown.item.number": accent,
        "markdown.item.bullet": accent,
        "markdown.table.header": f"bold {accent}",
        "markdown.hr": dim,
        "markdown.code": accent,
        "markdown.link": accent,
    })
