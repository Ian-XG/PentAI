from pathlib import Path
from pentai.config import Config, ProviderConfig
from pentai.scope import Scope
from pentai.cli import build_agent
from pentai.agent import Agent

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

def test_main_classic_flag_dispatches_to_classic(monkeypatch):
    import pentai.cli as cli
    calls = {}
    monkeypatch.setattr(cli, "main_classic", lambda argv=None: calls.setdefault("classic", argv) or 0)
    monkeypatch.setattr(cli, "main_tui", lambda argv: calls.setdefault("tui", argv) or 0)
    cli.main(["--classic"])
    assert "classic" in calls and "tui" not in calls
