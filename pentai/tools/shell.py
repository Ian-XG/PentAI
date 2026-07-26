import subprocess
from dataclasses import dataclass
from typing import Callable
from ..scope import Scope
from ..providers.base import Tool

@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int

def _subprocess_runner(command: str) -> CommandResult:
    proc = subprocess.run(command, shell=True, capture_output=True, text=True)
    return CommandResult(proc.stdout, proc.stderr, proc.returncode)

def run_command(command: str, *, scope: Scope, confirm: Callable[[str], bool],
                runner: Callable[[str], CommandResult] | None = None) -> str:
    runner = runner or _subprocess_runner
    oos = scope.out_of_scope(command)
    if oos and not confirm(f"OUT OF SCOPE: {', '.join(oos)}. You confirm you are authorized?"):
        return "[cancelled: target out of authorized scope]"
    if not confirm(f"execute: {command}"):
        return "[cancelled by user]"
    result = runner(command)
    return f"exit_code={result.exit_code}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"

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
