from rich.theme import Theme

_TAGS = {"AI": "[AI]", "EXEC": "[EXEC]", "VULN": "[!] VULN", "INFO": "[INFO]"}

def format_tag(kind: str, text: str) -> str:
    tag = _TAGS.get(kind, _TAGS["INFO"])
    return f"{tag} {text}"

def markdown_theme(palette: dict[str, str]) -> Theme:
    accent = palette["accent"]
    dim = palette["dim"]
    primary = palette["primary"]
    return Theme({
        # a visual hierarchy instead of every level reading identically -
        # report titles (h1) carry the most weight, down to h4-6 blending
        # into body text the way a deeply nested heading should.
        "markdown.h1": f"bold {primary} underline",
        "markdown.h2": f"bold {accent}",
        "markdown.h3": accent,
        "markdown.h4": dim,
        "markdown.h5": dim,
        "markdown.h6": dim,
        "markdown.item.number": accent,
        "markdown.item.bullet": accent,
        "markdown.table.header": f"bold {accent}",
        "markdown.table.border": accent,
        "markdown.hr": dim,
        "markdown.code": accent,
        "markdown.link": accent,
    })
