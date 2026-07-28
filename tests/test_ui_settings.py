from rich.console import Console
from pentai.ui.settings import render_provider_menu
from pentai.ui.theme import get_palette
from pentai.onboarding import PROVIDER_CHOICES

def test_render_provider_menu_lists_every_choice_with_icon():
    con = Console(record=True, width=100)
    render_provider_menu(con, get_palette("green"), None)
    out = con.export_text()
    assert "PentAI" in out and "Settings" in out
    for c in PROVIDER_CHOICES:
        assert c.name in out
        assert c.icon in out

def test_render_provider_menu_tags_current_provider():
    con = Console(record=True, width=100)
    render_provider_menu(con, get_palette("green"), "ollama")
    out = con.export_text()
    assert "current" in out.lower()

def test_render_provider_menu_no_current_tag_when_none_active():
    con = Console(record=True, width=100)
    render_provider_menu(con, get_palette("green"), None)
    out = con.export_text()
    assert "current" not in out.lower()

def test_render_provider_menu_shows_ctrl_c_hint():
    con = Console(record=True, width=100)
    render_provider_menu(con, get_palette("green"), None)
    out = con.export_text()
    assert "Ctrl-C" in out

def test_every_provider_choice_has_a_monochrome_glyph_icon():
    # icons must be single glyphs (not colorful multi-codepoint emoji) so they
    # render in the accent color instead of a clashing emoji-color font
    for c in PROVIDER_CHOICES:
        assert c.icon
        assert len(c.icon) == 1
