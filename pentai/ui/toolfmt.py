import re

_RESULT_RE = re.compile(r"exit_code=(-?\d+)\n--- stdout ---\n(.*)\n--- stderr ---\n(.*)$", re.DOTALL)

def format_command_output(result: str) -> str:
    """Turn run_command's raw 'exit_code=N / --- stdout --- / --- stderr ---' string
    into a clean display: stdout as-is, stderr only if present, exit code only if nonzero."""
    m = _RESULT_RE.match(result)
    if not m:
        return result.strip()
    code = int(m.group(1))
    out = m.group(2).strip()
    err = m.group(3).strip()
    parts = []
    if out:
        parts.append(out)
    if err:
        parts.append("stderr: " + err)
    if code != 0:
        parts.append(f"[exit code {code}]")
    return "\n".join(parts) if parts else "(no output)"
