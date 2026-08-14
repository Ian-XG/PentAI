"""Per-engagement session store. Each session is a directory under
<base>/sessions/<id>/ holding the conversation transcript, the notes file, and a
meta.json describing it (provider, model, scope snapshot, turn count, title).
This is what lets PentAI close and reopen on the same engagement, list past
engagements, and resume any of them - the memory of a long op."""
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from .providers.base import Message
from .transcript import save_transcript, load_transcript

_TITLE_MAX = 60

def _now() -> str:
    return time.strftime("%Y%m%d_%H%M%S")

@dataclass
class SessionMeta:
    id: str
    created_at: str
    last_active: str
    title: str = ""
    provider: str = ""
    model: str = ""
    scope: list[str] = field(default_factory=list)
    turns: int = 0

def derive_title(history: list[Message]) -> str:
    for m in history:
        if m.role == "user" and m.content.strip():
            line = " ".join(m.content.split())
            return line[:_TITLE_MAX]
    return ""

@dataclass
class Session:
    dir: Path
    meta: SessionMeta

    @property
    def id(self) -> str:
        return self.meta.id

    @property
    def transcript_path(self) -> Path:
        return self.dir / "transcript.json"

    @property
    def notes_path(self) -> Path:
        return self.dir / "notes.md"

    def load_history(self) -> list[Message]:
        return load_transcript(self.transcript_path)

    def save_history(self, history: list[Message], now=_now) -> None:
        save_transcript(history, self.transcript_path)
        self.meta.last_active = now()
        self.meta.turns = sum(1 for m in history if m.role == "user")
        if not self.meta.title:
            self.meta.title = derive_title(history)
        self._write_meta()

    def _write_meta(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.dir, 0o700)   # engagement data stays owner-only
        except OSError:
            pass
        meta_path = self.dir / "meta.json"
        meta_path.write_text(json.dumps(asdict(self.meta), indent=1))
        try:
            os.chmod(meta_path, 0o600)
        except OSError:
            pass

def _sessions_root(base: Path) -> Path:
    return base / "sessions"

def new_session(base: Path, *, provider: str = "", model: str = "",
                scope: list[str] | None = None, now=_now) -> Session:
    stamp = now()
    d = _sessions_root(base) / stamp
    meta = SessionMeta(id=stamp, created_at=stamp, last_active=stamp,
                       provider=provider, model=model, scope=list(scope or []))
    s = Session(d, meta)
    s._write_meta()
    return s

def load_session(base: Path, session_id: str) -> Session | None:
    d = _sessions_root(base) / session_id
    meta_path = d / "meta.json"
    try:
        data = json.loads(meta_path.read_text())
        return Session(d, SessionMeta(**data))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        # TypeError: meta.json parsed fine but doesn't match SessionMeta's
        # shape (missing required field, or valid JSON that isn't even an
        # object) - a stale/incompatible session must not crash /sessions,
        # /resume, or the default resume-latest startup path.
        return None

def list_sessions(base: Path) -> list[SessionMeta]:
    root = _sessions_root(base)
    if not root.is_dir():
        return []
    metas: list[SessionMeta] = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        s = load_session(base, d.name)
        if s is not None:
            metas.append(s.meta)
    metas.sort(key=lambda m: m.id, reverse=True)
    return metas

def latest_session(base: Path) -> Session | None:
    metas = list_sessions(base)
    if not metas:
        return None
    return load_session(base, metas[0].id)
