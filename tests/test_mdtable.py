from pentai.ui.mdtable import md, TableMarkdown
from pentai.ui.tui_core import render_to_ansi


def test_markdown_table_has_grid_borders():
    table_md = "| Tool | Purpose |\n|------|---------|\n| dig | DNS |\n| curl | HTTP |"
    out = render_to_ansi(md(table_md), width=80)
    # a real vertical column-separator line must appear (columns are delimited),
    # but a full per-row cross grid is not required (light MINIMAL box style)
    assert chr(9474) in out    # '│' vertical divider between columns
    assert "dig" in out and "curl" in out and "DNS" in out


def test_plain_markdown_still_renders():
    out = render_to_ansi(md("# Title\n\n- one\n- two"), width=80)
    assert "Title" in out and "one" in out and "two" in out
