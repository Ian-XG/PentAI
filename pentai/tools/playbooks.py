from pathlib import Path
from ..providers.base import Tool

def list_playbooks(skills_dir: Path) -> list[str]:
    if not skills_dir.exists():
        return []
    return sorted(p.stem for p in skills_dir.glob("*.md"))

def load_playbook(name: str, *, skills_dir: Path) -> str:
    # `name` comes from the agent, which can be steered by prompt injection
    # in scanned target content (this tool's whole threat model) - confine
    # the resolved path to skills_dir so "../../sessions/<id>/notes" can't
    # read anything outside the playbook directory. Same failure message
    # either way, so a traversal attempt learns nothing about what's there.
    skills_dir = skills_dir.resolve()
    path = (skills_dir / f"{name}.md").resolve()
    if not path.is_relative_to(skills_dir) or not path.exists():
        return f"[playbook not found: {name}]"
    return path.read_text()

LOAD_PLAYBOOK_TOOL = Tool(
    name="load_playbook",
    description="Load a methodology playbook for the current phase "
                "(recon, web-owasp, priv-esc, reporting).",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Playbook name without .md"}},
        "required": ["name"],
    },
)
