from pentai.ui.theme import get_palette, PALETTES
from pentai.ui.banner import render_banner, boot_lines, SIGIL, SIGIL_SIMPLE

def test_palettes_have_roles():
    for name in ("green", "amber", "red"):
        p = PALETTES[name]
        assert {"primary", "accent", "dim", "alert"} <= set(p)

def test_get_palette_fallback():
    assert get_palette("nonexistent") == PALETTES["green"]

def test_banner_contains_wordmark():
    out = render_banner(get_palette("green"))
    assert "P" in out and "PENTAI" in out.replace(" ", "")

def test_simple_banner_has_no_braille_or_box():
    assert render_banner(get_palette("green"), simple=True).count("◈") == 0

def test_boot_lines_nonempty():
    lines = boot_lines()
    assert lines and all(line.startswith("[") for line in lines)
