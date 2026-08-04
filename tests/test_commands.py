from pentai.scope import Scope
from pentai.commands import parse_slash, handle_slash

def test_parse_slash():
    assert parse_slash("/scope add 10.0.0.0/24") == ("scope", ["add", "10.0.0.0/24"])
    assert parse_slash("hello") is None

def test_parse_slash_strips_whitespace():
    from pentai.commands import parse_slash
    assert parse_slash("  /scope add workforce-os.app  ") == ("scope", ["add", "workforce-os.app"])
    assert parse_slash("\t/help") == ("help", [])

def test_parse_slash_non_slash_and_blank():
    from pentai.commands import parse_slash
    assert parse_slash("hi there") is None
    assert parse_slash("   ") is None

def test_scope_add_and_list():
    s = Scope([])
    handle_slash("scope", ["add", "10.0.0.0/24"], scope=s)
    assert "10.0.0.0/24" in s.entries
    assert "10.0.0.0/24" in handle_slash("scope", ["list"], scope=s)

def test_quit_and_unknown():
    s = Scope([])
    assert handle_slash("quit", [], scope=s) == "__quit__"
    assert "unknown" in handle_slash("bogus", [], scope=s).lower()

def test_setup_returns_sentinel():
    from pentai.scope import Scope
    from pentai.commands import handle_slash
    assert handle_slash("setup", [], scope=Scope([])) == "__setup__"

def test_help_lists_setup():
    from pentai.scope import Scope
    from pentai.commands import handle_slash
    assert "/setup" in handle_slash("help", [], scope=Scope([]))

def test_new_command_sentinels():
    from pentai.scope import Scope
    from pentai.commands import handle_slash
    s = Scope([])
    assert handle_slash("clear", [], scope=s) == "__clear__"
    assert handle_slash("notes", [], scope=s) == "__notes__"
    assert handle_slash("report", [], scope=s) == "__report__"
    assert handle_slash("tools", [], scope=s) == "__tools__"
    assert handle_slash("playbooks", [], scope=s) == "__playbooks__"

def test_help_lists_new_commands():
    from pentai.scope import Scope
    from pentai.commands import handle_slash
    h = handle_slash("help", [], scope=Scope([]))
    for c in ("/clear", "/notes", "/report", "/tools", "/playbooks"):
        assert c in h

def test_settings_alias_returns_setup_sentinel():
    from pentai.scope import Scope
    from pentai.commands import handle_slash
    assert handle_slash("settings", [], scope=Scope([])) == "__setup__"

def test_settings_in_menu_and_help():
    from pentai.commands import SLASH_COMMANDS, handle_slash
    from pentai.scope import Scope
    names = [c for c, _ in SLASH_COMMANDS]
    assert "/settings" in names
    assert "/settings" in handle_slash("help", [], scope=Scope([]))

def test_model_sentinel_and_help():
    from pentai.scope import Scope
    from pentai.commands import handle_slash, SLASH_COMMANDS
    assert handle_slash("model", ["gpt-oss:20b"], scope=Scope([])) == "__model__"
    assert "/model" in handle_slash("help", [], scope=Scope([]))
    assert "/model" in [c for c, _ in SLASH_COMMANDS]

def test_sessions_and_resume_sentinels_and_help():
    from pentai.scope import Scope
    from pentai.commands import handle_slash, SLASH_COMMANDS
    assert handle_slash("sessions", [], scope=Scope([])) == "__sessions__"
    assert handle_slash("resume", ["20260804_101500"], scope=Scope([])) == "__resume__"
    h = handle_slash("help", [], scope=Scope([]))
    assert "/sessions" in h and "/resume" in h
    names = [c for c, _ in SLASH_COMMANDS]
    assert "/sessions" in names and "/resume" in names

def test_findings_sentinel_and_help():
    from pentai.scope import Scope
    from pentai.commands import handle_slash, SLASH_COMMANDS
    assert handle_slash("findings", [], scope=Scope([])) == "__findings__"
    assert "/findings" in handle_slash("help", [], scope=Scope([]))
    assert "/findings" in [c for c, _ in SLASH_COMMANDS]

def test_slash_commands_metadata():
    from pentai.commands import SLASH_COMMANDS
    names = [c for c, _ in SLASH_COMMANDS]
    assert "/scope" in names and "/quit" in names
    assert all(desc for _, desc in SLASH_COMMANDS)  # every command has a description
