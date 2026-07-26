from pathlib import Path
import pentai
from pentai.tools.playbooks import list_playbooks

PKG = Path(pentai.__file__).parent

def test_system_prompt_mentions_ethics():
    text = (PKG / "prompts" / "system.md").read_text().lower()
    assert "authorized" in text
    assert "teach" in text or "learn" in text

def test_four_playbooks_present():
    names = list_playbooks(PKG / "skills")
    assert set(names) == {"recon", "web-owasp", "priv-esc", "reporting"}
