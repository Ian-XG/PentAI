from pathlib import Path
from ..providers.base import Tool

def list_playbooks(skills_dir: Path) -> list[str]:
    if not skills_dir.exists():
        return []
    return sorted(p.stem for p in skills_dir.glob("*.md"))

def load_playbook(name: str, *, skills_dir: Path) -> str:
    path = skills_dir / f"{name}.md"
    if not path.exists():
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
