import os
from pathlib import Path
from ..providers.base import Tool

def save_note(text: str, *, session_dir: Path) -> str:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / "notes.md"
    # Create at 0600 from the first byte instead of open()-then-chmod - notes
    # may hold creds/evidence, so there must be no window where a freshly
    # created file has default permissions. Same fix as findings.py and
    # transcript.py. The mode only applies on creation, which is fine here:
    # every write after the first is just an append to an already-0600 file.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (text.rstrip() + "\n\n").encode())
    finally:
        os.close(fd)
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
