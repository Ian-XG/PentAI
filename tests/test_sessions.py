from pathlib import Path
from pentai.providers.base import Message, ToolCall
from pentai.sessions import (Session, SessionMeta, new_session, list_sessions,
                             latest_session, load_session, derive_title)

def test_new_session_creates_dir_and_meta(tmp_path: Path):
    s = new_session(tmp_path, provider="ollama", model="gpt-oss:20b",
                    scope=["10.0.0.0/24"], now=lambda: "20260804_101500")
    assert s.id == "20260804_101500"
    assert s.dir.is_dir()
    assert s.meta.provider == "ollama"
    assert s.meta.model == "gpt-oss:20b"
    assert s.meta.scope == ["10.0.0.0/24"]
    assert (s.dir / "meta.json").exists()
    # a freshly created session is discoverable
    assert load_session(tmp_path, "20260804_101500").meta.model == "gpt-oss:20b"

def test_transcript_and_notes_paths_live_in_session_dir(tmp_path: Path):
    s = new_session(tmp_path, now=lambda: "20260804_101500")
    assert s.transcript_path == s.dir / "transcript.json"
    assert s.notes_path == s.dir / "notes.md"

def test_save_history_roundtrips_and_updates_meta(tmp_path: Path):
    s = new_session(tmp_path, now=lambda: "20260804_101500")
    history = [Message("user", "enumerate the target"),
               Message("assistant", "ok", tool_calls=[ToolCall("i", "run_command", {"command": "nmap"})]),
               Message("tool", "22/tcp open", tool_call_id="i")]
    s.save_history(history, now=lambda: "20260804_101600")
    assert s.load_history() == history
    reloaded = load_session(tmp_path, s.id)
    assert reloaded.meta.last_active == "20260804_101600"
    assert reloaded.meta.turns == 1                      # one user turn
    assert reloaded.meta.title == "enumerate the target"  # from first user msg

def test_list_sessions_newest_first(tmp_path: Path):
    new_session(tmp_path, now=lambda: "20260801_090000")
    new_session(tmp_path, now=lambda: "20260803_090000")
    new_session(tmp_path, now=lambda: "20260802_090000")
    ids = [m.id for m in list_sessions(tmp_path)]
    assert ids == ["20260803_090000", "20260802_090000", "20260801_090000"]

def test_latest_session_returns_most_recent(tmp_path: Path):
    new_session(tmp_path, now=lambda: "20260801_090000")
    new_session(tmp_path, model="newest", now=lambda: "20260805_090000")
    assert latest_session(tmp_path).meta.model == "newest"

def test_latest_session_none_when_empty(tmp_path: Path):
    assert latest_session(tmp_path) is None
    assert list_sessions(tmp_path) == []
    assert load_session(tmp_path, "nope") is None

def test_list_sessions_ignores_dirs_without_meta(tmp_path: Path):
    new_session(tmp_path, now=lambda: "20260801_090000")
    (tmp_path / "sessions" / "garbage").mkdir(parents=True)
    (tmp_path / "sessions" / "loose_file.txt").write_text("x")
    ids = [m.id for m in list_sessions(tmp_path)]
    assert ids == ["20260801_090000"]

def test_load_session_tolerates_meta_missing_required_fields(tmp_path: Path):
    # a stale/incompatible meta.json (older schema, hand-edited, partial
    # write) must not crash /sessions, /resume, or the resume-latest
    # startup path - just be skipped like a missing session would be.
    import json
    sdir = tmp_path / "sessions" / "20260813_120000"
    sdir.mkdir(parents=True)
    (sdir / "meta.json").write_text(json.dumps({"id": "20260813_120000"}))
    assert load_session(tmp_path, "20260813_120000") is None

def test_list_sessions_skips_a_malformed_meta_without_crashing(tmp_path: Path):
    import json
    new_session(tmp_path, now=lambda: "20260801_090000")
    bad = tmp_path / "sessions" / "20260802_090000"
    bad.mkdir(parents=True)
    (bad / "meta.json").write_text(json.dumps({"id": "20260802_090000"}))
    ids = [m.id for m in list_sessions(tmp_path)]
    assert ids == ["20260801_090000"]

def test_derive_title_from_first_user_message():
    assert derive_title([Message("assistant", "hi"),
                         Message("user", "pop the DC")]) == "pop the DC"
    assert derive_title([]) == ""

def test_derive_title_truncates_long_and_strips_newlines():
    t = derive_title([Message("user", "line one\nline two " + "x" * 80)])
    assert "\n" not in t and len(t) <= 60

def test_session_files_are_private(tmp_path: Path):
    import os
    s = new_session(tmp_path, now=lambda: "20260804_101500")
    s.save_history([Message("user", "secret creds: admin:hunter2")])
    assert (os.stat(s.dir).st_mode & 0o777) == 0o700          # dir not group/other readable
    assert (os.stat(s.dir / "meta.json").st_mode & 0o777) == 0o600
    assert (os.stat(s.transcript_path).st_mode & 0o777) == 0o600

def test_turns_counts_only_user_messages(tmp_path: Path):
    s = new_session(tmp_path, now=lambda: "20260804_101500")
    history = [Message("user", "a"), Message("assistant", "b"),
               Message("user", "c"), Message("assistant", "d")]
    s.save_history(history)
    assert load_session(tmp_path, s.id).meta.turns == 2
