from pentai.scope import Scope
from pentai.tools.shell import run_command, CommandResult, RUN_COMMAND_TOOL

def _fixed_runner(out):
    return lambda cmd: CommandResult(out, "", 0)

def test_runs_when_in_scope_and_confirmed():
    r = run_command("nmap 10.0.0.5", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda prompt: True, runner=_fixed_runner("open ports"))
    assert "open ports" in r

def test_cancelled_when_declined():
    r = run_command("nmap 10.0.0.5", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda prompt: False, runner=_fixed_runner("x"))
    assert "cancelled" in r.lower()

def test_out_of_scope_requires_confirm():
    seen = []
    def confirm(prompt):
        seen.append(prompt)
        return False
    r = run_command("nmap 1.2.3.4", scope=Scope(["10.0.0.0/24"]),
                    confirm=confirm, runner=_fixed_runner("x"))
    assert any("scope" in p.lower() for p in seen)
    assert "cancelled" in r.lower()

def test_out_of_scope_confirmed_then_execute_declined():
    calls = []
    def runner(cmd):
        calls.append(cmd)
        return CommandResult("x", "", 0)
    answers = iter([True, False])
    r = run_command("nmap 1.2.3.4", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda prompt: next(answers), runner=runner)
    assert "cancelled" in r.lower()
    assert calls == []

def test_tool_schema_name():
    assert RUN_COMMAND_TOOL.name == "run_command"
    assert "command" in RUN_COMMAND_TOOL.parameters["properties"]

def test_auto_runs_in_scope_without_confirm():
    calls = []
    def confirm(p):
        calls.append(p)
        return True
    r = run_command("nmap 10.0.0.5", scope=Scope(["10.0.0.0/24"]),
                    confirm=confirm, mode="auto", runner=lambda c: CommandResult("ok", "", 0))
    assert "ok" in r
    assert calls == []  # no prompt in auto for in-scope

def test_auto_still_confirms_out_of_scope():
    seen = []
    r = run_command("nmap 1.2.3.4", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda p: seen.append(p) or False, mode="auto",
                    runner=lambda c: CommandResult("x", "", 0))
    assert seen and "cancelled" in r.lower()

def test_bypass_runs_everything_without_confirm():
    calls = []
    r = run_command("nmap 1.2.3.4", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda p: calls.append(p) or True, mode="bypass",
                    runner=lambda c: CommandResult("done", "", 0))
    assert "done" in r
    assert calls == []  # bypass never prompts, even out of scope
