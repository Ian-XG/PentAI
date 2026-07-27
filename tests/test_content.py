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

def test_system_prompt_is_action_biased():
    text = (PKG / "prompts" / "system.md").read_text().lower()
    # must push tool use over describing
    assert "call" in text and "tool" in text
    assert "do not print" in text or "never print" in text
    # must know it receives scope/mode context and guide /scope add
    assert "/scope add" in text
    assert "mode" in text
    # still ethical
    assert "authorized" in text

def test_system_prompt_is_terse_and_non_repeating():
    from pathlib import Path
    import pentai
    text = (Path(pentai.__file__).parent / "prompts" / "system.md").read_text().lower()
    assert "terse" in text
    assert "do not repeat" in text
    assert "one sentence" in text
