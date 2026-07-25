from pentai.scope import Scope
from pentai.commands import parse_slash, handle_slash

def test_parse_slash():
    assert parse_slash("/scope add 10.0.0.0/24") == ("scope", ["add", "10.0.0.0/24"])
    assert parse_slash("hello") is None

def test_scope_add_and_list():
    s = Scope([])
    handle_slash("scope", ["add", "10.0.0.0/24"], scope=s)
    assert "10.0.0.0/24" in s.entries
    assert "10.0.0.0/24" in handle_slash("scope", ["list"], scope=s)

def test_quit_and_unknown():
    s = Scope([])
    assert handle_slash("quit", [], scope=s) == "__quit__"
    assert "unknown" in handle_slash("bogus", [], scope=s).lower()
