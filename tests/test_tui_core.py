from rich.markdown import Markdown
from pentai.ui.tui_core import render_to_ansi, TurnQueue

def test_render_to_ansi_plain_text():
    out = render_to_ansi("hello world")
    assert "hello world" in out

def test_render_to_ansi_markdown():
    out = render_to_ansi(Markdown("# Title\n\n- item one"))
    assert "Title" in out and "item one" in out

def test_render_to_ansi_accepts_theme():
    from pentai.ui.render import markdown_theme
    from pentai.ui.theme import get_palette
    out = render_to_ansi(Markdown("# Title"), theme=markdown_theme(get_palette("green")))
    assert "Title" in out  # renders without error and includes the text

def test_turn_queue_fifo_and_blank():
    q = TurnQueue()
    q.enqueue("first"); q.enqueue("   "); q.enqueue("second")
    assert len(q) == 2
    assert q.pending == ["first", "second"]
    assert q.pop() == "first"
    assert q.pop() == "second"
    assert q.pop() is None
    assert len(q) == 0
