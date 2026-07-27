# tests/test_ui_render.py
from pentai.ui.render import format_tag

def test_format_tag_known():
    assert format_tag("EXEC", "nmap 10.0.0.5").startswith("[EXEC]")
    assert format_tag("VULN", "SQLi").startswith("[!] VULN")

def test_format_tag_unknown_falls_back():
    assert format_tag("bogus", "x").startswith("[INFO]")

def test_markdown_theme_has_markdown_styles():
    from pentai.ui.render import markdown_theme
    from pentai.ui.theme import get_palette
    theme = markdown_theme(get_palette("green"))
    for key in ("markdown.h1", "markdown.item.number", "markdown.table.header"):
        assert key in theme.styles
