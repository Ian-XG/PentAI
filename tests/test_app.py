from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from pentai.ui.app import build_app, OutputBuffer


def test_output_buffer_renders_appended_renderables_at_width():
    from rich.text import Text
    b = OutputBuffer()
    b.append(Text("alpha"))
    b.append(Text("beta"))
    out = b.render(80)
    assert "alpha" in out and "beta" in out


def test_output_buffer_render_reflows_at_different_widths():
    from rich.text import Text
    b = OutputBuffer()
    b.append_full_width(" > hi", "bold black on green")
    narrow = b.render(20)
    wide = b.render(120)
    # the highlight bar pads to the render width, so wider render produces a longer line
    assert len(wide.splitlines()[0]) > len(narrow.splitlines()[0])


def test_output_buffer_visible_tail():
    from rich.text import Text
    b = OutputBuffer()
    for i in range(20):
        b.append(Text(f"line{i}"))
    vis = b.visible(3, 0, 80)     # bottom 3 logical lines
    assert "line19" in vis and "line0" not in vis
    assert b.line_count(80) >= 20


def test_output_buffer_clear():
    from rich.text import Text
    b = OutputBuffer()
    b.append(Text("x"))
    b.clear()
    assert b.render(80) == ""


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


def test_app_pageup_then_end_headless():
    from prompt_toolkit.input.defaults import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from rich.text import Text
    out = OutputBuffer()
    for i in range(200):
        out.append(Text(str(i)))  # long content
    with create_pipe_input() as inp:
        app = build_app(output=out, on_submit=lambda t: None, on_stop=lambda: None,
                        on_cycle_mode=lambda: None, get_status=lambda: "s",
                        pt_input=inp, pt_output=DummyOutput())
        inp.send_text("\x1b[5~")   # PageUp
        inp.send_text("\x1b[F")    # End (jump to bottom)
        inp.send_text("\x03")      # Ctrl-C exit
        app.run()


def test_app_mouse_support_pageup_then_end_headless():
    # mouse_support is on by default now; verify the app still builds and runs
    # cleanly through the same scroll/jump-to-bottom key sequence with it enabled.
    from prompt_toolkit.input.defaults import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from rich.text import Text
    out = OutputBuffer()
    for i in range(200):
        out.append(Text(str(i)))  # long content
    with create_pipe_input() as inp:
        app = build_app(output=out, on_submit=lambda t: None, on_stop=lambda: None,
                        on_cycle_mode=lambda: None, get_status=lambda: "s",
                        pt_input=inp, pt_output=DummyOutput())
        assert app.mouse_support()
        inp.send_text("\x1b[5~")   # PageUp -> offset > 0, jump bar becomes visible
        inp.send_text("\x1b[F")    # End -> back to offset 0
        inp.send_text("\x03")      # Ctrl-C exit
        app.run()
