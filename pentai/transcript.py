"""Serialize agent conversation history to/from disk so an engagement can be
resumed exactly where it left off. Kept deliberately dumb: it only knows how to
turn Message objects into JSON and back, safely. Session management (where files
live, metadata, listing) lives in sessions.py."""
import json
import os
from pathlib import Path
from .providers.base import Message, ToolCall

def message_to_dict(m: Message) -> dict:
    d: dict = {"role": m.role, "content": m.content}
    if m.tool_calls:
        d["tool_calls"] = [{"id": c.id, "name": c.name, "arguments": c.arguments}
                           for c in m.tool_calls]
    if m.tool_call_id is not None:
        d["tool_call_id"] = m.tool_call_id
    return d

def message_from_dict(d: dict) -> Message:
    calls = [ToolCall(c["id"], c["name"], c.get("arguments") or {})
             for c in d.get("tool_calls", [])]
    return Message(d["role"], d.get("content", ""),
                   tool_calls=calls, tool_call_id=d.get("tool_call_id"))

def save_transcript(history: list[Message], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([message_to_dict(m) for m in history], indent=1)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload)
    try:
        os.chmod(tmp, 0o600)   # transcripts hold creds/evidence - owner-only
    except OSError:
        pass
    tmp.replace(path)          # atomic: never leaves a half-written transcript

def load_transcript(path: Path) -> list[Message]:
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [message_from_dict(d) for d in data]
