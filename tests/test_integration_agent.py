"""End-to-end tests of the real agent tool loop wired by build_agent: the
scripted provider drives tool calls, but the tools themselves run for real -
real subprocess, real nmap auto-ingest, real timeout, real findings/assets
persistence. This guards the production path that ScriptedProvider unit tests
in test_agent.py never touch."""
import os
import stat
from pathlib import Path

from pentai.config import default_config
from pentai.scope import Scope
from pentai.agent import Agent, ToolInvocation
from pentai.cli import build_agent
from pentai.assets import load_assets
from pentai.findings import load_findings
from pentai.providers.base import Message, Tool, TextDelta, ToolCallEvent, Done


class ScriptedProvider:
    """Yields one scripted event-list per chat() call."""
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = 0

    def chat(self, messages, tools, system=""):
        script = self.scripts[self.calls]
        self.calls += 1
        yield from script


def _make_agent(session_dir, scripts, *, scope=None, timeout=None):
    cfg = default_config()
    if timeout is not None:
        cfg.command_timeout = timeout
    agent = build_agent(cfg, Scope(scope or []), lambda prompt: True,
                        session_dir, mode_getter=lambda: "bypass")
    agent.provider = ScriptedProvider(scripts)   # swap in the fake provider
    return agent


def _fake_nmap(tmp_path: Path) -> Path:
    """An executable named 'nmap' that prints canned normal-format output, so
    is_nmap_command() fires and the real subprocess produces parseable text."""
    script = tmp_path / "nmap"
    script.write_text(
        "#!/bin/sh\n"
        "cat <<'EOF'\n"
        "Nmap scan report for 10.0.0.5\n"
        "PORT   STATE SERVICE\n"
        "22/tcp open  ssh\n"
        "80/tcp open  http\n"
        "EOF\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_run_command_auto_ingests_nmap_into_asset_map(tmp_path):
    session_dir = tmp_path / "sess"
    nmap = _fake_nmap(tmp_path)
    agent = _make_agent(session_dir, [
        [ToolCallEvent("t1", "run_command", {"command": f"{nmap} 10.0.0.5"}),
         Done("tool_use")],
        [TextDelta("scan done"), Done("end")],
    ], scope=["10.0.0.0/24"])

    out = list(agent.send("scan 10.0.0.5"))
    inv = next(e for e in out if isinstance(e, ToolInvocation))

    assert "22/tcp" in inv.result                      # real command output
    assert "auto-mapped 2 service(s)" in inv.result    # ingest note appended
    hosts = load_assets(session_dir)                   # persisted to the map
    assert len(hosts) == 1 and hosts[0].address == "10.0.0.5"
    assert {s.port for s in hosts[0].services} == {22, 80}


def test_non_nmap_command_does_not_touch_asset_map(tmp_path):
    session_dir = tmp_path / "sess"
    agent = _make_agent(session_dir, [
        [ToolCallEvent("t1", "run_command", {"command": "echo hello"}), Done("tool_use")],
        [TextDelta("ok"), Done("end")],
    ])
    out = list(agent.send("say hi"))
    inv = next(e for e in out if isinstance(e, ToolInvocation))
    assert "hello" in inv.result
    assert "auto-mapped" not in inv.result
    assert load_assets(session_dir) == []


def test_record_finding_tool_persists_through_agent(tmp_path):
    session_dir = tmp_path / "sess"
    agent = _make_agent(session_dir, [
        [ToolCallEvent("t1", "record_finding",
                       {"title": "SQLi in /login", "severity": "high",
                        "target": "10.0.0.5"}), Done("tool_use")],
        [TextDelta("logged"), Done("end")],
    ])
    list(agent.send("record it"))
    saved = load_findings(session_dir)
    assert len(saved) == 1
    assert saved[0].title == "SQLi in /login" and saved[0].severity == "high"


def test_command_timeout_flows_through_agent(tmp_path):
    session_dir = tmp_path / "sess"
    agent = _make_agent(session_dir, [
        [ToolCallEvent("t1", "run_command", {"command": "sleep 30"}), Done("tool_use")],
        [TextDelta("moved on"), Done("end")],
    ], timeout=1)
    import time
    start = time.time()
    out = list(agent.send("hang"))
    assert time.time() - start < 10                    # killed, not waited out
    inv = next(e for e in out if isinstance(e, ToolInvocation))
    assert "timed out" in inv.result
    assert any(isinstance(e, TextDelta) and e.text == "moved on" for e in out)
