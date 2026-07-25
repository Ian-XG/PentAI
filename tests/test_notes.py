from pathlib import Path
from pentai.tools.notes import save_note, SAVE_NOTE_TOOL

def test_save_note_appends(tmp_path: Path):
    save_note("finding one", session_dir=tmp_path)
    save_note("finding two", session_dir=tmp_path)
    content = (tmp_path / "notes.md").read_text()
    assert "finding one" in content and "finding two" in content

def test_note_tool_name():
    assert SAVE_NOTE_TOOL.name == "save_note"
