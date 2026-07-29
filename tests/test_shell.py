from pentai.scope import Scope
from pentai.tools.shell import run_command, CommandResult, RUN_COMMAND_TOOL, truncate_output
from pentai.ui.toolfmt import format_command_output

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

def test_ask_out_of_scope_single_confirm_declined():
    calls = []
    r = run_command("nmap 1.2.3.4", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda p: calls.append(p) or False, mode="ask",
                    runner=lambda c: CommandResult("x", "", 0))
    assert len(calls) == 1                      # exactly ONE prompt, not two
    assert "out of scope" in calls[0].lower()
    assert "cancelled" in r.lower()

def test_ask_in_scope_single_confirm_runs():
    calls = []
    r = run_command("nmap 10.0.0.5", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda p: calls.append(p) or True, mode="ask",
                    runner=lambda c: CommandResult("ok", "", 0))
    assert len(calls) == 1 and "ok" in r

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

# --- truncate_output ---------------------------------------------------

def test_truncate_output_short_text_unchanged():
    text = "line1\nline2\nline3"
    assert truncate_output(text) == text

def test_truncate_output_empty_unchanged():
    assert truncate_output("") == ""

def test_truncate_output_typical_nmap_sv_never_truncated():
    # ~30 lines, a dozen ports - realistic nmap -sV output - must pass through untouched
    lines = ["Starting Nmap 7.94", "Nmap scan report for 10.0.0.5"]
    lines += [f"{p}/tcp open  service{p}" for p in range(20, 32)]
    lines += ["Nmap done: 1 IP address (1 host up) scanned in 4.2 seconds"]
    text = "\n".join(lines)
    assert truncate_output(text) == text

def test_truncate_output_large_line_count_keeps_head_and_tail():
    lines = [f"line{i}" for i in range(300)]
    text = "\n".join(lines)
    out = truncate_output(text, max_lines=200, head_lines=140, tail_lines=40)
    out_lines = out.split("\n")
    assert out_lines[:140] == lines[:140]        # head preserved
    assert out_lines[-40:] == lines[-40:]         # tail preserved
    assert "[120 lines truncated]" in out         # 300 - 140 - 40 = 120 hidden

def test_truncate_output_marker_appears_once_between_head_and_tail():
    lines = [f"line{i}" for i in range(500)]
    text = "\n".join(lines)
    out = truncate_output(text)
    marker_lines = [l for l in out.split("\n") if "truncated" in l]
    assert len(marker_lines) == 1

def test_truncate_output_giant_single_line_capped_by_char_backstop():
    text = "x" * 50000   # one enormous line, well under max_lines but over max_chars
    out = truncate_output(text, max_chars=16000)
    assert len(out) < len(text)
    assert "truncated" in out
    assert out.startswith("x" * 100)   # head preserved
    assert out.endswith("x" * 100)     # tail preserved

def test_truncate_output_respects_custom_thresholds():
    lines = [f"l{i}" for i in range(10)]
    text = "\n".join(lines)
    out = truncate_output(text, max_lines=5, head_lines=2, tail_lines=2)
    assert "[6 lines truncated]" in out
    assert out.split("\n")[:2] == lines[:2]
    assert out.split("\n")[-2:] == lines[-2:]

def test_truncated_envelope_still_parses_via_format_command_output():
    big_stdout = "\n".join(f"line{i}" for i in range(500))
    result = run_command("bigcmd", scope=Scope([]), confirm=lambda p: True,
                         runner=lambda c: CommandResult(big_stdout, "", 0))
    formatted = format_command_output(result)
    assert "line0" in formatted
    assert "line499" in formatted
    assert "truncated" in formatted
    assert "exit code" not in formatted   # exit 0 -> no exit-code suffix, still parsed cleanly

def test_truncated_envelope_preserves_nonzero_exit_code():
    big_stdout = "\n".join(f"line{i}" for i in range(500))
    result = run_command("bigcmd", scope=Scope([]), confirm=lambda p: True,
                         runner=lambda c: CommandResult(big_stdout, "", 2))
    formatted = format_command_output(result)
    assert "[exit code 2]" in formatted

def test_run_command_truncates_stdout_and_stderr_individually():
    big = "\n".join(f"l{i}" for i in range(500))
    result = run_command("bigcmd", scope=Scope([]), confirm=lambda p: True,
                         runner=lambda c: CommandResult(big, big, 0))
    stdout_section, stderr_section = result.split("--- stderr ---")
    assert "truncated" in stdout_section
    assert "truncated" in stderr_section
