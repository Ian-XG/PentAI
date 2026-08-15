from pathlib import Path
from pentai.tools.playbooks import list_playbooks, load_playbook, LOAD_PLAYBOOK_TOOL

def test_list_and_load(tmp_path: Path):
    (tmp_path / "recon.md").write_text("# Recon")
    assert "recon" in list_playbooks(tmp_path)
    assert "# Recon" in load_playbook("recon", skills_dir=tmp_path)

def test_missing_playbook(tmp_path: Path):
    assert "not found" in load_playbook("ghost", skills_dir=tmp_path)

def test_load_playbook_blocks_path_traversal(tmp_path: Path):
    # `name` is agent-supplied and this tool's own threat model includes
    # prompt-injected arguments from scanned target content - a traversal
    # must not escape skills_dir to read arbitrary files (e.g. another
    # session's notes.md).
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "recon.md").write_text("# Recon")
    secret = tmp_path / "sessions" / "abc" / "notes.md"
    secret.parent.mkdir(parents=True)
    secret.write_text("SECRET: admin:hunter2")

    result = load_playbook("../sessions/abc/notes", skills_dir=skills_dir)
    assert "SECRET" not in result
    assert "not found" in result

def test_load_playbook_traversal_gives_the_generic_not_found_message(tmp_path: Path):
    # don't let the error message reveal whether the traversal target
    # exists outside skills_dir - same "not found" shape either way.
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (tmp_path / "outside.md").write_text("exists but must stay unreachable")
    assert load_playbook("../outside", skills_dir=skills_dir) == "[playbook not found: ../outside]"

def test_load_tool_name():
    assert LOAD_PLAYBOOK_TOOL.name == "load_playbook"
