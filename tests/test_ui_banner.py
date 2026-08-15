from pentai.ui.theme import get_palette, PALETTES
from pentai.ui.banner import render_banner, boot_lines, render_sigil_rich, SIGIL, SIGIL_SIMPLE

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

def test_render_sigil_rich_preserves_the_plain_text():
    # every visible non-whitespace character of SIGIL must survive, just
    # restyled - the two-tone treatment can't drop or reorder anything.
    styled = render_sigil_rich("bright_green", "green dim")
    assert styled.plain == SIGIL.strip("\n")

def test_render_sigil_rich_gives_the_wordmark_and_core_a_distinct_style():
    styled = render_sigil_rich("bright_green", "green dim")
    spans_by_text = {styled.plain[s.start:s.end]: s.style for s in styled.spans}
    # the apex glyph and the wordmark's first letter must not share the dim
    # style used for the surrounding struts - that's the whole point.
    assert "bright_green" in str(spans_by_text.get("◈", ""))
    assert "bright_green" in str(spans_by_text.get("P", ""))
