from pentai.ui.startup import capability_rows, render_startup
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
