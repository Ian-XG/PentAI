# tests/test_ui_render.py
def test_markdown_theme_has_markdown_styles():
    from pentai.ui.render import markdown_theme
    from pentai.ui.theme import get_palette
    theme = markdown_theme(get_palette("green"))
    for key in ("markdown.h1", "markdown.item.number", "markdown.table.header"):
        assert key in theme.styles
