from pathlib import Path
from pentai.config import Config, ProviderConfig
from pentai.scope import Scope
from pentai.cli import build_agent, model_command
from pentai.agent import Agent
from pentai.providers.openai_compat import OpenAICompatProvider
from pentai.providers.anthropic import AnthropicProvider

def test_model_command_switches_and_persists():
    prov = OpenAICompatProvider("http://localhost:11434/v1", None, "old")
    prov._tools_unsupported = True
    saved = {}
    out = model_command(prov, ["gpt-oss:20b"], persist=lambda m: saved.setdefault("m", m))
    assert prov.model == "gpt-oss:20b"
    assert prov._tools_unsupported is False       # set_model reset the latch
    assert saved["m"] == "gpt-oss:20b"            # persisted
    assert "gpt-oss:20b" in out

def test_model_command_lists_for_openai_compat():
    prov = OpenAICompatProvider("http://localhost:11434/v1", None, "llama2")
    out = model_command(prov, [], list_models_fn=lambda base, key: ["llama2", "gpt-oss:20b"])
    assert "llama2" in out and "gpt-oss:20b" in out
    assert "current model: llama2" in out

def test_model_command_handles_list_failure_gracefully():
    prov = OpenAICompatProvider("http://x/v1", None, "m")
    def boom(base, key):
        raise RuntimeError("connection refused")
    out = model_command(prov, [], list_models_fn=boom)
    assert "current model: m" in out and "couldn't list" in out

def test_model_command_anthropic_has_no_list():
    prov = AnthropicProvider("k", "claude-opus-4")
    out = model_command(prov, [], persist=lambda m: None)
    assert "current model: claude-opus-4" in out
    # switching still works on a provider without set_model
    out2 = model_command(prov, ["claude-sonnet-4"], persist=lambda m: None)
    assert prov.model == "claude-sonnet-4" and "claude-sonnet-4" in out2

def test_build_agent_wires_three_tools(tmp_path: Path):
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "claude-opus-4", "k")})
    agent = build_agent(cfg, Scope([]), confirm=lambda p: True, session_dir=tmp_path)
    assert isinstance(agent, Agent)
    assert set(agent.tools) == {"run_command", "save_note", "load_playbook"}

def test_provider_ready_true_with_key():
    from pentai.config import Config, ProviderConfig
    from pentai.cli import provider_ready
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "m", "sk-x")})
    assert provider_ready(cfg) is True

def test_provider_ready_false_without_key():
    from pentai.config import Config, ProviderConfig
    from pentai.cli import provider_ready
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "m")})
    assert provider_ready(cfg) is False

def test_provider_ready_true_for_keyless_local(monkeypatch):
    # ollama local has no api_key and no api_key_env -> considered ready
    from pentai.config import Config, ProviderConfig
    from pentai.cli import provider_ready
    cfg = Config(active="o",
                 providers={"o": ProviderConfig("openai_compat", "llama3.1",
                                                 base_url="http://localhost:11434/v1")})
    assert provider_ready(cfg) is True

def test_apply_mode_command_cycles_and_sets():
    from pentai.cli import apply_mode_command
    assert apply_mode_command("ask", []) == "auto"      # cycle
    assert apply_mode_command("ask", ["bypass"]) == "bypass"  # set
    assert apply_mode_command("ask", ["nonsense"]) == "ask"   # invalid -> unchanged

def test_stream_turn_flushes_buffered_text_on_error():
    from pentai.cli import stream_turn
    from pentai.providers.base import TextDelta
    def events():
        yield TextDelta("partial answer ")
        raise RuntimeError("boom")
    rendered, errors = [], []
    stream_turn(events(), lambda t: rendered.append(t), lambda ev: None,
                lambda e: errors.append(str(e)))
    assert rendered == ["partial answer "]   # buffered text NOT lost
    assert errors and "boom" in errors[0]

def test_stream_turn_flushes_before_tool_and_at_end():
    from pentai.cli import stream_turn
    from pentai.providers.base import TextDelta
    from pentai.agent import ToolInvocation
    def events():
        yield TextDelta("thinking ")
        yield ToolInvocation("run_command", {"command": "ls"}, "ok")
        yield TextDelta("done")
    rendered, tools = [], []
    stream_turn(events(), lambda t: rendered.append(t), lambda ev: tools.append(ev), lambda e: None)
    assert rendered == ["thinking ", "done"]   # flushed before tool and at end
    assert len(tools) == 1

def test_build_agent_tools_match_startup_list(tmp_path):
    from pentai.config import Config, ProviderConfig
    from pentai.scope import Scope
    from pentai.cli import build_agent, AGENT_TOOL_NAMES
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "m", "k")})
    agent = build_agent(cfg, Scope([]), confirm=lambda p: True, session_dir=tmp_path)
    assert set(agent.tools) == set(AGENT_TOOL_NAMES)

def test_friendly_error_connection():
    import socket
    from pentai.cli import friendly_error
    msg = friendly_error(socket.gaierror(8, "nodename nor servname provided, or not known"))
    assert "provider" in msg.lower()
    assert "8" not in msg or "provider" in msg.lower()  # not a raw errno dump

def test_friendly_error_auth():
    from pentai.cli import friendly_error
    assert "api key" in friendly_error(Exception("HTTP 401 Unauthorized")).lower()

def test_friendly_error_generic():
    from pentai.cli import friendly_error
    assert "boom" in friendly_error(Exception("boom"))

def test_session_context_includes_installed_tools():
    from pentai.cli import session_context
    ctx = session_context(["10.0.0.0/24"], "ask", "/home/x", tools=["nmap", "curl"])
    assert "nmap, curl" in ctx
    assert "10.0.0.0/24" in ctx and "ask" in ctx

def test_session_context_without_tools_omits_line():
    from pentai.cli import session_context
    ctx = session_context([], "ask", "/home/x")
    assert "installed tools" not in ctx.lower()

def test_session_context_empty_scope_is_neutral():
    from pentai.cli import session_context
    ctx = session_context([], "ask", "/home/x")
    assert "(none set)" in ctx
    assert "/scope add" not in ctx           # no imperative in the context
    assert "tell the user" not in ctx.lower()

def test_main_defaults_to_tui(monkeypatch):
    import pentai.cli as cli
    calls = {}
    monkeypatch.setattr(cli, "main_classic", lambda argv=None: calls.setdefault("classic", argv) or 0)
    monkeypatch.setattr(cli, "main_tui", lambda argv: calls.setdefault("tui", argv) or 0)
    cli.main([])
    assert "tui" in calls and "classic" not in calls

def test_restore_terminal_disables_mouse_tracking(capsys):
    from pentai.cli import _restore_terminal
    _restore_terminal()
    out = capsys.readouterr().out
    for seq in ("\x1b[?1000l", "\x1b[?1003l", "\x1b[?1006l", "\x1b[?1015l", "\x1b[?25h"):
        assert seq in out          # every mouse mode disabled + cursor shown

def test_main_settings_flag_dispatches(monkeypatch):
    import pentai.cli as cli
    calls = {}
    monkeypatch.setattr(cli, "main_settings", lambda argv=None: calls.setdefault("settings", argv) or 0)
    monkeypatch.setattr(cli, "main_tui", lambda argv: calls.setdefault("tui", argv) or 0)
    monkeypatch.setattr(cli, "main_classic", lambda argv=None: calls.setdefault("classic", argv) or 0)
    cli.main(["--settings"])
    assert "settings" in calls and "tui" not in calls and "classic" not in calls

def test_run_settings_merges_into_existing_config():
    from pentai.cli import run_settings
    current = {"active": "anthropic",
               "providers": {"anthropic": {"kind": "anthropic", "model": "claude-opus-4"}},
               "scope": ["10.0.0.0/24"], "palette": "green", "fx": True}
    answers = iter(["3", ""])  # choose ollama (3), accept default model
    printed = []
    merged = run_settings(lambda p: next(answers), lambda m: printed.append(str(m)), current=current)
    assert merged["active"] == "ollama"                     # switched provider
    assert merged["scope"] == ["10.0.0.0/24"]               # existing scope preserved
    assert "ollama" in merged["providers"]                  # new provider added
    assert "anthropic" in merged["providers"]               # old provider kept
    assert any("claude-opus-4" in p for p in printed)       # showed current provider

def test_main_settings_keyboard_interrupt_exits_cleanly(monkeypatch, capsys):
    # Ctrl-C during the wizard must not dump a traceback: catch it, print a
    # calm cancellation message, and return 0.
    import pentai.cli as cli
    from rich.console import Console
    monkeypatch.setattr(cli, "read_config_file", lambda: None)
    monkeypatch.setattr(Console, "input", lambda self, *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    rc = cli.main_settings([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "cancelled" in out.lower()
    assert "traceback" not in out.lower()

def test_main_settings_eof_exits_cleanly(monkeypatch, capsys):
    import pentai.cli as cli
    from rich.console import Console
    monkeypatch.setattr(cli, "read_config_file", lambda: None)
    monkeypatch.setattr(Console, "input", lambda self, *a, **k: (_ for _ in ()).throw(EOFError()))
    rc = cli.main_settings([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "cancelled" in out.lower()

def test_main_settings_shows_polished_menu_with_icons(monkeypatch, capsys):
    # main_settings wires render_menu through to render_provider_menu (the
    # polished panel/table), not the plain numbered list.
    import pentai.cli as cli
    from rich.console import Console
    answers = iter(["1", "", "sk-ant-abc"])   # choose anthropic, default model, key
    monkeypatch.setattr(cli, "read_config_file", lambda: None)
    monkeypatch.setattr(cli, "save_config", lambda cfg: __import__("pathlib").Path("/tmp/x"))
    monkeypatch.setattr(Console, "input", lambda self, *a, **k: next(answers))
    rc = cli.main_settings([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Settings" in out
    assert "◆" in out   # anthropic's icon

def test_provider_row_tags_current_provider():
    from pentai.cli import _provider_row
    from pentai.onboarding import PROVIDER_CHOICES
    ollama = next(c for c in PROVIDER_CHOICES if c.name == "ollama")
    row = _provider_row(ollama, "ollama")
    assert "current" in row
    assert ollama.icon in row
    assert ollama.name in row

def test_provider_row_no_tag_when_not_current():
    from pentai.cli import _provider_row
    from pentai.onboarding import PROVIDER_CHOICES
    ollama = next(c for c in PROVIDER_CHOICES if c.name == "ollama")
    row = _provider_row(ollama, "anthropic")
    assert "current" not in row

def test_provider_start_index_finds_active():
    from pentai.cli import _provider_start_index
    assert _provider_start_index("ollama") == 2
    assert _provider_start_index("nonexistent") == 0
    assert _provider_start_index(None) == 0

def test_main_settings_uses_interactive_select_when_tty(monkeypatch, capsys):
    # when stdout IS a tty, main_settings must use the arrow-key select() picker,
    # not the plain/rich text menu - stub select() to avoid a real interactive app.
    import sys
    import pentai.cli as cli
    from rich.console import Console
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    calls = {}
    def fake_select(options, **kw):
        calls["options"] = options
        calls["kw"] = kw
        return 2   # ollama - needs no base_url and no api key
    monkeypatch.setattr(cli, "select", fake_select)
    monkeypatch.setattr(cli, "read_config_file", lambda: None)
    monkeypatch.setattr(cli, "save_config", lambda cfg: __import__("pathlib").Path("/tmp/x"))
    answers = iter([""])  # accept default model
    monkeypatch.setattr(Console, "input", lambda self, *a, **k: next(answers))
    rc = cli.main_settings([])
    assert rc == 0
    assert calls["options"] == cli.PROVIDER_CHOICES
    out = capsys.readouterr().out
    assert "OK" in out

def test_main_settings_tty_select_cancelled_returns_zero_no_save(monkeypatch, capsys):
    import sys
    import pentai.cli as cli
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(cli, "select", lambda options, **kw: None)
    monkeypatch.setattr(cli, "read_config_file", lambda: None)
    saved = []
    monkeypatch.setattr(cli, "save_config", lambda cfg: saved.append(cfg))
    rc = cli.main_settings([])
    assert rc == 0
    assert saved == []   # nothing persisted on cancel
    out = capsys.readouterr().out
    assert "cancelled" in out.lower()

def test_parse_session_arg_new_by_default():
    from pentai.cli import parse_session_arg
    assert parse_session_arg([]) == ("new", None)
    assert parse_session_arg(["--tui"]) == ("new", None)

def test_parse_session_arg_continue_latest():
    from pentai.cli import parse_session_arg
    assert parse_session_arg(["-c"]) == ("latest", None)
    assert parse_session_arg(["--continue"]) == ("latest", None)
    assert parse_session_arg(["--resume"]) == ("latest", None)

def test_parse_session_arg_resume_specific_id():
    from pentai.cli import parse_session_arg
    assert parse_session_arg(["--resume", "20260804_101500"]) == ("id", "20260804_101500")
    assert parse_session_arg(["--resume=20260804_101500"]) == ("id", "20260804_101500")

def test_resolve_session_new_creates_and_snapshots(tmp_path):
    from pentai.cli import resolve_session
    s = resolve_session(tmp_path, [], provider="ollama", model="m",
                        scope=["10.0.0.0/24"], now=lambda: "20260804_101500")
    assert s.id == "20260804_101500"
    assert s.meta.provider == "ollama" and s.meta.scope == ["10.0.0.0/24"]

def test_resolve_session_latest_resumes_prior(tmp_path):
    from pentai.cli import resolve_session
    from pentai.sessions import new_session
    from pentai.providers.base import Message
    old = new_session(tmp_path, model="old", now=lambda: "20260801_090000")
    old.save_history([Message("user", "prior work")])
    s = resolve_session(tmp_path, ["-c"], provider="x", model="new", scope=[])
    assert s.id == "20260801_090000"
    assert s.load_history()[0].content == "prior work"

def test_resolve_session_latest_falls_back_to_new_when_none(tmp_path):
    from pentai.cli import resolve_session
    s = resolve_session(tmp_path, ["-c"], provider="x", model="new", scope=[],
                        now=lambda: "20260804_101500")
    assert s.id == "20260804_101500"        # nothing to resume -> fresh session

def test_resolve_session_bad_id_falls_back_to_new(tmp_path):
    from pentai.cli import resolve_session
    s = resolve_session(tmp_path, ["--resume", "does_not_exist"], provider="x",
                        model="m", scope=[], now=lambda: "20260804_101500")
    assert s.id == "20260804_101500"

def test_format_sessions_lists_newest_with_metadata(tmp_path):
    from pentai.cli import format_sessions
    from pentai.sessions import new_session
    from pentai.providers.base import Message
    a = new_session(tmp_path, model="gpt-oss:20b", now=lambda: "20260801_090000")
    a.save_history([Message("user", "enumerate the DC")], now=lambda: "20260801_091000")
    out = format_sessions(tmp_path)
    assert "20260801_090000" in out
    assert "enumerate the DC" in out
    assert "gpt-oss:20b" in out

def test_format_sessions_empty():
    import tempfile, pathlib
    from pentai.cli import format_sessions
    with tempfile.TemporaryDirectory() as d:
        out = format_sessions(pathlib.Path(d))
    assert "no" in out.lower()

def test_build_agent_seeds_history(tmp_path):
    from pentai.config import Config, ProviderConfig
    from pentai.scope import Scope
    from pentai.cli import build_agent
    from pentai.providers.base import Message
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "m", "k")})
    hist = [Message("user", "earlier")]
    agent = build_agent(cfg, Scope([]), confirm=lambda p: True, session_dir=tmp_path,
                        history=hist)
    assert agent.history == hist

def test_main_classic_flag_dispatches_to_classic(monkeypatch):
    import pentai.cli as cli
    calls = {}
    monkeypatch.setattr(cli, "main_classic", lambda argv=None: calls.setdefault("classic", argv) or 0)
    monkeypatch.setattr(cli, "main_tui", lambda argv: calls.setdefault("tui", argv) or 0)
    cli.main(["--classic"])
    assert "classic" in calls and "tui" not in calls
