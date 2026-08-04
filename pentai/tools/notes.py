import os
from pathlib import Path
from ..providers.base import Tool

def save_note(text: str, *, session_dir: Path) -> str:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / "notes.md"
    with path.open("a") as f:
        f.write(text.rstrip() + "\n\n")
    try:
        os.chmod(path, 0o600)   # notes may hold creds/evidence - owner-only
    except OSError:
        pass
    return f"[saved note to {path}]"

SAVE_NOTE_TOOL = Tool(
    name="save_note",
    description="Save a finding, credential, or report note to the session notes file.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string", "description": "Markdown note to append"}},
        "required": ["text"],
    },
)
