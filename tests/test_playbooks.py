from pathlib import Path
from pentai.tools.playbooks import list_playbooks, load_playbook, LOAD_PLAYBOOK_TOOL

def test_list_and_load(tmp_path: Path):
    (tmp_path / "recon.md").write_text("# Recon")
    assert "recon" in list_playbooks(tmp_path)
    assert "# Recon" in load_playbook("recon", skills_dir=tmp_path)

def test_missing_playbook(tmp_path: Path):
    assert "not found" in load_playbook("ghost", skills_dir=tmp_path)

def test_load_tool_name():
    assert LOAD_PLAYBOOK_TOOL.name == "load_playbook"
