import re

_RESULT_RE = re.compile(r"exit_code=(-?\d+)\n--- stdout ---\n(.*)\n--- stderr ---\n(.*)$", re.DOTALL)

_SCHEMA_MARKERS = ('"type":"function"', '"arguments"', '"parameters"')
_INTERNAL_TOOLS = ("run_command", "load_playbook", "save_note")

def looks_like_tool_schema_dump(text: str) -> bool:
    """True when a (usually too-small) model echoes the tool JSON schema back as
    plain text instead of chatting or emitting a real tool call. Conservative:
    requires both a function-schema marker AND two-plus of our internal tool
    names, so ordinary prose that merely mentions a tool won't trip it. All
    whitespace is stripped first so spacing variants like '"type" : "function"'
    still match."""
    t = text.strip()
    if len(t) < 40:
        return False
    compact = re.sub(r"\s+", "", t.lower())
    if not any(m in compact for m in _SCHEMA_MARKERS):
        return False
    return sum(1 for n in _INTERNAL_TOOLS if n in compact) >= 2

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
