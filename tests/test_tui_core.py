from rich.markdown import Markdown
from pentai.ui.tui_core import render_to_ansi, TurnQueue, output_rows

def test_output_rows_no_bars_visible():
    assert output_rows(24, scrolled=False, thinking=False) == 20   # 24 - 4

def test_output_rows_one_bar_visible():
    assert output_rows(24, scrolled=True, thinking=False) == 19
    assert output_rows(24, scrolled=False, thinking=True) == 19

def test_output_rows_both_bars_visible_at_once():
    # the bug: a fixed "-5" margin only ever budgeted for ONE extra bar, so
    # scrolling up while a turn streams (both jump_bar and thinking_bar
    # visible) overcounted available rows by 1.
    assert output_rows(24, scrolled=True, thinking=True) == 18

def test_output_rows_never_goes_below_one():
    assert output_rows(2, scrolled=True, thinking=True) == 1

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

def test_render_to_ansi_none_width_uses_terminal():
    out = render_to_ansi("hello sizing")  # width=None -> real terminal width, must still render
    assert "hello sizing" in out

def test_format_thinking():
    from pentai.ui.tui_core import format_thinking
    assert format_thinking(0, 3) == "Thinking... (0 tokens - 3s)"
    assert format_thinking(10800, 78) == "Thinking... (2.7k tokens - 1m 18s)"   # 10800//4=2700
    assert format_thinking(40, 5) == "Thinking... (10 tokens - 5s)"

def test_turn_queue_fifo_and_blank():
    q = TurnQueue()
    q.enqueue("first"); q.enqueue("   "); q.enqueue("second")
    assert len(q) == 2
    assert q.pending == ["first", "second"]
    assert q.pop() == "first"
    assert q.pop() == "second"
    assert q.pop() is None
    assert len(q) == 0
