from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from pentai.ui.select import select, move_index, _render

def test_move_index_down_clamps_at_end():
    assert move_index(0, 1, 3) == 1
    assert move_index(1, 1, 3) == 2
    assert move_index(2, 1, 3) == 2   # clamp, no wrap

def test_move_index_up_clamps_at_start():
    assert move_index(1, -1, 3) == 0
    assert move_index(0, -1, 3) == 0  # clamp, no wrap

def test_move_index_empty_length_returns_idx_unchanged():
    assert move_index(0, 1, 0) == 0

def test_select_enter_confirms_default_index():
    with create_pipe_input() as inp:
        inp.send_text("\r")
        idx = select(["a", "b", "c"], title="pick", render_row=lambda o, sel: o,
                    pt_input=inp, pt_output=DummyOutput())
    assert idx == 0

def test_select_down_down_enter_returns_index_two():
    with create_pipe_input() as inp:
        inp.send_text("\x1b[B\x1b[B\r")  # down, down, enter
        idx = select(["a", "b", "c"], title="pick", render_row=lambda o, sel: o,
                    pt_input=inp, pt_output=DummyOutput())
    assert idx == 2

def test_select_up_from_zero_clamps_then_enter():
    with create_pipe_input() as inp:
        inp.send_text("\x1b[A\r")  # up (already at 0, clamps), enter
        idx = select(["a", "b", "c"], title="pick", render_row=lambda o, sel: o,
                    pt_input=inp, pt_output=DummyOutput())
    assert idx == 0

def test_select_j_k_vim_keys_also_move():
    with create_pipe_input() as inp:
        inp.send_text("jj\r")  # vim-style down, down, enter
        idx = select(["a", "b", "c"], title="pick", render_row=lambda o, sel: o,
                    pt_input=inp, pt_output=DummyOutput())
    assert idx == 2

def test_select_escape_cancels_returns_none():
    with create_pipe_input() as inp:
        inp.send_text("\x1b")
        idx = select(["a", "b", "c"], title="pick", render_row=lambda o, sel: o,
                    pt_input=inp, pt_output=DummyOutput())
    assert idx is None

def test_select_ctrl_c_cancels_returns_none():
    with create_pipe_input() as inp:
        inp.send_text("\x03")
        idx = select(["a", "b", "c"], title="pick", render_row=lambda o, sel: o,
                    pt_input=inp, pt_output=DummyOutput())
    assert idx is None

def test_select_ctrl_d_cancels_returns_none():
    with create_pipe_input() as inp:
        inp.send_text("\x04")
        idx = select(["a", "b", "c"], title="pick", render_row=lambda o, sel: o,
                    pt_input=inp, pt_output=DummyOutput())
    assert idx is None

def test_select_respects_active_index_start():
    with create_pipe_input() as inp:
        inp.send_text("\r")  # confirm immediately - should keep the starting index
        idx = select(["a", "b", "c"], title="pick", render_row=lambda o, sel: o,
                    active_index=1, pt_input=inp, pt_output=DummyOutput())
    assert idx == 1

def test_select_empty_options_returns_none():
    assert select([], title="pick", render_row=lambda o, sel: o) is None

def test_long_row_wraps_beyond_the_old_fixed_height_assumption():
    # Demonstrates the bug this fix addresses: the old Window height was a
    # fixed n+4 (title + 2 blank lines + hint, one line per option), assuming
    # every row renders as exactly one terminal line. A long row on a narrow
    # terminal wraps onto more physical lines than that - which is exactly
    # what let content (including the cancel hint) get clipped.
    from pentai.ui.tui_core import render_to_ansi
    from pentai.ui.theme import get_palette
    options = ["a very long provider description that will not fit on a narrow terminal at all"]
    rendered = render_to_ansi(_render(options, 0, "pick", lambda o, sel: o, get_palette("green")),
                              width=20)
    old_fixed_height = len(options) + 4
    actual_lines = rendered.count("\n") + 1
    assert actual_lines > old_fixed_height

def test_select_window_height_is_dynamic_not_a_fixed_undercount(monkeypatch):
    # the real regression guard: spy on the Window(height=...) argument
    # select() actually constructs. The old code passed a fixed n+4 int that
    # undercounts a wrapped long row; the fix must pass a callable that
    # accounts for the current wrapped line count instead.
    import pentai.ui.select as select_mod
    import os
    captured = {}
    RealWindow = select_mod.Window
    def spy_window(*a, **kw):
        captured["height"] = kw.get("height")
        return RealWindow(*a, **kw)
    monkeypatch.setattr(select_mod, "Window", spy_window)
    monkeypatch.setattr(select_mod.shutil, "get_terminal_size",
                        lambda fallback=(100, 24): os.terminal_size((20, 24)))
    options = ["a very long provider description that will not fit on a narrow terminal at all"]
    with create_pipe_input() as inp:
        inp.send_text("\r")
        select(options, title="pick", render_row=lambda o, sel: o,
              pt_input=inp, pt_output=DummyOutput())
    height = captured["height"]
    assert callable(height)                # not a fixed int like the old n+4
    assert height() > len(options) + 4     # correctly accounts for the wrapped row

def test_select_with_long_rows_on_a_narrow_terminal_still_works(monkeypatch):
    # integration-level: the picker itself must not crash and must still
    # select correctly when a long row wraps on a narrow terminal - this
    # exercises the dynamic height callable actually wired into the Window.
    import pentai.ui.select as select_mod
    import os
    monkeypatch.setattr(select_mod.shutil, "get_terminal_size",
                        lambda fallback=(100, 24): os.terminal_size((20, 24)))
    options = ["a very long provider description that will not fit on a narrow terminal at all",
              "short"]
    with create_pipe_input() as inp:
        inp.send_text("\x1b[B\r")  # down, enter -> selects the 2nd option
        idx = select(options, title="pick", render_row=lambda o, sel: o,
                    pt_input=inp, pt_output=DummyOutput())
    assert idx == 1
