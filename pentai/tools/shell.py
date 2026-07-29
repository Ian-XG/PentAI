import subprocess
from dataclasses import dataclass
from typing import Callable
from ..scope import Scope
from ..providers.base import Tool
from ..permissions import should_prompt_exec, should_prompt_oos

@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int

def truncate_output(text: str, *, max_lines: int = 200, head_lines: int = 140,
                    tail_lines: int = 40, max_chars: int = 16000) -> str:
    """Cap huge command output so it neither floods the TUI nor blows the model's
    context (this string is fed back to the model as the tool result on every
    later turn too). Within limits: returned unchanged. Over the line limit:
    keep the first `head_lines` and last `tail_lines`, replace the middle with
    a one-line marker. A hard `max_chars` backstop also applies afterward, in
    case a single line (or the whole thing) is enormous on its own."""
    if not text:
        return text
    lines = text.split("\n")
    if len(lines) > max_lines:
        hidden = len(lines) - head_lines - tail_lines
        marker = f"... [{hidden} lines truncated] ..."
        text = "\n".join(lines[:head_lines] + [marker] + lines[-tail_lines:])
    if len(text) > max_chars:
        half = max_chars // 2
        omitted = len(text) - max_chars
        text = f"{text[:half]}\n... [{omitted} chars truncated] ...\n{text[-half:]}"
    return text

def _subprocess_runner(command: str) -> CommandResult:
    proc = subprocess.run(command, shell=True, capture_output=True, text=True)
    return CommandResult(proc.stdout, proc.stderr, proc.returncode)

def run_command(command: str, *, scope: Scope, confirm: Callable[[str], bool],
                mode: str = "ask", runner: Callable[[str], CommandResult] | None = None) -> str:
    runner = runner or _subprocess_runner
    oos = scope.out_of_scope(command)
    if should_prompt_exec(mode):            # ASK: exactly one prompt, note OOS inline
        if oos:
            label = f"OUT OF SCOPE ({', '.join(oos)}) - run anyway? {command}"
        else:
            label = f"run? {command}"
        if not confirm(label):
            return "[cancelled by user]"
    elif oos and should_prompt_oos(mode):   # AUTO: only out-of-scope needs a prompt
        if not confirm(f"OUT OF SCOPE ({', '.join(oos)}) - authorized? {command}"):
            return "[cancelled: target out of authorized scope]"
    result = runner(command)
    stdout = truncate_output(result.stdout)
    stderr = truncate_output(result.stderr)
    return f"exit_code={result.exit_code}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"

RUN_COMMAND_TOOL = Tool(
    name="run_command",
    description="Run a shell command on the operator's machine and return its output. "
                "Used for recon, scanning, and exploitation against authorized targets only.",
    parameters={
        "type": "object",
        "properties": {"command": {"type": "string", "description": "The shell command to run"}},
        "required": ["command"],
    },
)
