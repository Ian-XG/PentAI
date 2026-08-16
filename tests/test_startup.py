from pentai.ui.startup import capability_rows, render_startup, render_toolcheck
from pentai.ui.theme import get_palette
from rich.console import Console

def test_capability_rows_shape():
    rows = capability_rows(["recon", "web-owasp"], ["run_command"], ["ask", "bypass"])
    assert rows[0] == ("playbooks", "recon, web-owasp")
    assert rows[1] == ("tools", "run_command")
    assert rows[2] == ("modes", "ask, bypass")

def test_capability_rows_empty_playbooks():
    rows = capability_rows([], ["run_command"], ["ask"])
    assert rows[0] == ("playbooks", "(none)")

def test_render_startup_outputs_key_fields():
    con = Console(record=True, width=100)
    render_startup(con, palette=get_palette("green"), provider="ollama-cloud",
                   model="gpt-oss:120b", playbooks=["recon"], tools=["run_command"],
                   modes=["ask", "auto", "bypass"], scope_count=1, session_id="20260726_x")
    out = con.export_text()
    assert "PentAI" in out
    assert "recon" in out
    assert "ollama-cloud" in out and "gpt-oss:120b" in out
    assert "20260726_x" in out

def test_render_startup_shows_settings_hint():
    con = Console(record=True, width=100)
    render_startup(con, palette=get_palette("green"), provider="ollama-cloud",
                   model="gpt-oss:120b", playbooks=["recon"], tools=["run_command"],
                   modes=["ask", "auto", "bypass"], scope_count=1, session_id="20260728_x")
    out = con.export_text()
    assert "settings" in out
    assert "pentai --settings" in out

def test_render_startup_narrow_terminal_has_fields():
    con = Console(record=True, width=48)
    render_startup(con, palette=get_palette("green"), provider="ollama",
                   model="llama3.1", playbooks=["recon"], tools=["run_command"],
                   modes=["ask", "auto", "bypass"], scope_count=0, session_id="20260727_x")
    out = con.export_text()
    assert "PentAI" in out and "recon" in out and "20260727_x" in out

def test_render_startup_80col_stacks_without_overflow():
    from pentai.ui.startup import render_startup
    from pentai.ui.theme import get_palette
    from rich.console import Console
    con = Console(record=True, width=80)
    render_startup(con, palette=get_palette("green"), provider="ollama-cloud",
                   model="gpt-oss:120b", playbooks=["recon", "web-owasp"], tools=["run_command"],
                   modes=["ask", "auto", "bypass"], scope_count=0, session_id="20260727_x")
    out = con.export_text()
    assert "PentAI" in out and "recon" in out and "gpt-oss:120b" in out
    # no line should exceed the console width (no overflow)
    assert all(len(line) <= 80 for line in out.splitlines())

def test_render_toolcheck_shows_a_found_over_total_count():
    con = Console(record=True, width=200)
    render_toolcheck(con, get_palette("green"),
                     [("nmap", True), ("masscan", False), ("curl", True)])
    out = con.export_text()
    assert "2/3" in out
    assert "nmap" in out and "masscan" in out and "curl" in out
