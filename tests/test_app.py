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


def test_output_buffer_caches_and_invalidates():
    calls = {"n": 0}
    b = OutputBuffer()
    def counting_renderer(w):
        calls["n"] += 1
        return "x\n"
    b.append_renderer(counting_renderer)
    b.render(80); b.render(80)               # same width + no new content -> render fn called once
    assert calls["n"] == 1
    b.render(100)                             # width changed -> full recompute of every renderer
    assert calls["n"] == 2
    b.append_renderer(counting_renderer)      # appending computes the NEW renderer immediately...
    assert calls["n"] == 3
    b.render(100)                             # ...so rendering at the same width recomputes nothing
    assert calls["n"] == 3

def test_output_buffer_appends_are_incremental_not_quadratic():
    # a renderer must be computed exactly once, not re-invoked on every later
    # append+render - cli.py appends one per text delta/tool event during a
    # turn, so re-rendering everything on each append was O(n) per chunk and
    # O(n^2) over a whole session.
    calls = {"n": 0}
    b = OutputBuffer()
    def counting_renderer(w):
        calls["n"] += 1
        return "x\n"
    b.render(80)                              # establish a cached width first
    for _ in range(5):
        b.append_renderer(counting_renderer)
        b.render(80)
    assert calls["n"] == 5                    # not 1+2+3+4+5=15


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


def test_slash_completer_offers_matching_commands():
    from pentai.ui.app import SlashCompleter
    from prompt_toolkit.document import Document
    comps = list(SlashCompleter().get_completions(Document("/sc"), None))
    assert any(c.text == "/scope" for c in comps)
    scope = next(c for c in comps if c.text == "/scope")
    assert "authorized targets" in scope.display_meta_text


def test_slash_completer_ignores_non_slash():
    from pentai.ui.app import SlashCompleter
    from prompt_toolkit.document import Document
    assert list(SlashCompleter().get_completions(Document("hello there"), None)) == []


def test_slash_completer_every_command_has_a_description():
    from pentai.ui.app import SlashCompleter
    from prompt_toolkit.document import Document
    comps = list(SlashCompleter().get_completions(Document("/"), None))
    assert len(comps) >= 10  # every SLASH_COMMANDS entry matches a bare "/"
    assert all(c.display_meta_text for c in comps)


def test_slash_completer_stops_after_first_token():
    # once a command name + space is typed, we're into argument territory - stop suggesting commands
    from pentai.ui.app import SlashCompleter
    from prompt_toolkit.document import Document
    doc = Document("/scope add ", cursor_position=len("/scope add "))
    assert list(SlashCompleter().get_completions(doc, None)) == []


def test_slash_completer_wired_into_input_area():
    from pentai.ui.app import SlashCompleter
    out = OutputBuffer()
    with create_pipe_input() as inp:
        app = build_app(output=out, on_submit=lambda t: None, on_stop=lambda: None,
                        on_cycle_mode=lambda: None, get_status=lambda: "s",
                        pt_input=inp, pt_output=DummyOutput())
        # TextArea wraps the completer in a DynamicCompleter; unwrap to check identity
        wrapped = app.current_buffer.completer.get_completer()
        assert isinstance(wrapped, SlashCompleter)


def test_completion_menu_is_themed_phosphor_green():
    # the "/" dropdown must not fall back to prompt_toolkit's default gray box
    from pentai.ui.app import MENU_STYLE
    sel = MENU_STYLE.get_attrs_for_style_str("class:completion-menu.completion.current")
    assert sel.bgcolor == "46e08a"          # selected row highlighted in accent green
    item = MENU_STYLE.get_attrs_for_style_str("class:completion-menu.completion")
    assert item.color == "46e08a"           # command names in green
    assert item.bgcolor == "0a0f0a"         # dark menu background, not gray


def test_app_wires_menu_style():
    out = OutputBuffer()
    with create_pipe_input() as inp:
        app = build_app(output=out, on_submit=lambda t: None, on_stop=lambda: None,
                        on_cycle_mode=lambda: None, get_status=lambda: "s",
                        pt_input=inp, pt_output=DummyOutput())
        assert app.style is not None


def test_app_layout_has_completions_menu_float():
    # without a CompletionsMenu float the "/" dropdown never renders, even though
    # the completer computes matches - this is the piece that was missing.
    from prompt_toolkit.layout.containers import FloatContainer
    from prompt_toolkit.layout.menus import CompletionsMenu
    out = OutputBuffer()
    with create_pipe_input() as inp:
        app = build_app(output=out, on_submit=lambda t: None, on_stop=lambda: None,
                        on_cycle_mode=lambda: None, get_status=lambda: "s",
                        pt_input=inp, pt_output=DummyOutput())
        root = app.layout.container
        assert isinstance(root, FloatContainer)
        assert any(isinstance(f.content, CompletionsMenu) for f in root.floats)


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
