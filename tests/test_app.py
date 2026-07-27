from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from pentai.ui.app import build_app, OutputBuffer


def test_output_buffer_accumulates():
    b = OutputBuffer()
    b.append("a"); b.append("b")
    assert b.text() == "ab"
    b.clear()
    assert b.text() == ""


def test_app_submit_then_exit_headless():
    submitted = []
    out = OutputBuffer()
    with create_pipe_input() as inp:
        app = build_app(output=out,
                        on_submit=lambda t: submitted.append(t),
                        on_stop=lambda: None,
                        on_cycle_mode=lambda: None,
                        get_status=lambda: "mode:ASK",
                        pt_input=inp, pt_output=DummyOutput())
        inp.send_text("hello there\r")  # type + Enter -> submit
        inp.send_text("\x03")           # Ctrl-C -> exit
        app.run()
    assert submitted == ["hello there"]


def test_app_cycle_mode_key_headless():
    cycles = []
    with create_pipe_input() as inp:
        app = build_app(output=OutputBuffer(),
                        on_submit=lambda t: None,
                        on_stop=lambda: None,
                        on_cycle_mode=lambda: cycles.append(1),
                        get_status=lambda: "s",
                        pt_input=inp, pt_output=DummyOutput())
        inp.send_text("\x1b[Z")  # shift-tab
        inp.send_text("\x03")    # Ctrl-C -> exit
        app.run()
    assert cycles == [1]


def test_output_buffer_visible_tail_and_offset():
    b = OutputBuffer()
    b.append("\n".join(str(i) for i in range(10)))  # lines "0".."9"
    assert b.visible(3, 0) == "7\n8\n9"       # bottom 3 (follow)
    assert b.visible(3, 3) == "4\n5\n6"       # scrolled up 3
    assert b.visible(100, 0) == b.text()      # fits -> full text
    assert b.line_count() == 10


def test_app_pageup_then_end_headless():
    from prompt_toolkit.input.defaults import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    out = OutputBuffer()
    out.append("\n".join(str(i) for i in range(200)))  # long content
    with create_pipe_input() as inp:
        app = build_app(output=out, on_submit=lambda t: None, on_stop=lambda: None,
                        on_cycle_mode=lambda: None, get_status=lambda: "s",
                        pt_input=inp, pt_output=DummyOutput())
        inp.send_text("\x1b[5~")   # PageUp
        inp.send_text("\x1b[F")    # End (jump to bottom)
        inp.send_text("\x03")      # Ctrl-C exit
        app.run()
