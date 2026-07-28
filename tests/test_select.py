from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from pentai.ui.select import select, move_index

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
