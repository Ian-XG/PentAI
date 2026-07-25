# tests/test_ui_render.py
from pentai.ui.render import format_tag, status_bar

def test_format_tag_known():
    assert format_tag("EXEC", "nmap 10.0.0.5").startswith("[EXEC]")
    assert format_tag("VULN", "SQLi").startswith("[!] VULN")

def test_format_tag_unknown_falls_back():
    assert format_tag("bogus", "x").startswith("[INFO]")

def test_status_bar_contents():
    s = status_bar("anthropic", "claude-opus-4", 2, 5)
    assert "anthropic:claude-opus-4" in s
    assert "scope:2" in s
    assert "cmds:5" in s
