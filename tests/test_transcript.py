from pathlib import Path
from pentai.providers.base import Message, ToolCall
from pentai.transcript import (message_to_dict, message_from_dict,
                               save_transcript, load_transcript)

def test_roundtrip_plain_message():
    m = Message("user", "scan the box")
    assert message_from_dict(message_to_dict(m)) == m

def test_roundtrip_assistant_with_tool_calls():
    m = Message("assistant", "running",
                tool_calls=[ToolCall("id1", "run_command", {"command": "ls"})])
    back = message_from_dict(message_to_dict(m))
    assert back == m
    assert back.tool_calls[0].arguments == {"command": "ls"}

def test_roundtrip_tool_result():
    m = Message("tool", "file1\nfile2", tool_call_id="id1")
    assert message_from_dict(message_to_dict(m)) == m

def test_save_and_load_transcript(tmp_path: Path):
    history = [Message("user", "hi"),
               Message("assistant", "hello", tool_calls=[ToolCall("i", "t", {"a": 1})]),
               Message("tool", "done", tool_call_id="i")]
    p = tmp_path / "transcript.json"
    save_transcript(history, p)
    assert load_transcript(p) == history

def test_load_missing_returns_empty(tmp_path: Path):
    assert load_transcript(tmp_path / "nope.json") == []

def test_load_corrupt_returns_empty(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert load_transcript(p) == []

def test_load_skips_entry_missing_role(tmp_path: Path):
    # a stale/malformed record must not crash session resume - it's skipped,
    # not fatal, same tolerance already applied to findings.py/assets.py.
    import json
    p = tmp_path / "transcript.json"
    p.write_text(json.dumps([{"content": "no role here"},
                             {"role": "user", "content": "real message"}]))
    assert [m.content for m in load_transcript(p)] == ["real message"]

def test_load_skips_tool_call_missing_id(tmp_path: Path):
    import json
    p = tmp_path / "transcript.json"
    p.write_text(json.dumps([
        {"role": "assistant", "content": "", "tool_calls": [{"name": "run_command"}]},
        {"role": "user", "content": "real message"},
    ]))
    assert [m.content for m in load_transcript(p)] == ["real message"]

def test_load_skips_non_dict_entries(tmp_path: Path):
    import json
    p = tmp_path / "transcript.json"
    p.write_text(json.dumps(["garbage", 42, {"role": "user", "content": "real message"}]))
    assert [m.content for m in load_transcript(p)] == ["real message"]

def test_save_is_atomic_no_partial_on_reserialize(tmp_path: Path):
    p = tmp_path / "t.json"
    save_transcript([Message("user", "one")], p)
    save_transcript([Message("user", "one"), Message("assistant", "two")], p)
    assert [m.content for m in load_transcript(p)] == ["one", "two"]

def test_save_creates_parent_dir(tmp_path: Path):
    p = tmp_path / "sub" / "dir" / "transcript.json"
    save_transcript([Message("user", "hi")], p)
    assert load_transcript(p) == [Message("user", "hi")]

def test_transcript_is_written_0600(tmp_path: Path):
    import os
    p = tmp_path / "transcript.json"
    save_transcript([Message("user", "secret creds: admin:hunter2")], p)
    assert (os.stat(p).st_mode & 0o777) == 0o600
