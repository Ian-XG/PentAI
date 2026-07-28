from pathlib import Path
import yaml
from pentai.onboarding import (ProviderChoice, PROVIDER_CHOICES, build_config,
                               run_wizard, save_config, needs_onboarding)

def test_five_choices_in_order():
    names = [c.name for c in PROVIDER_CHOICES]
    assert names == ["anthropic", "openai", "ollama", "ollama-cloud", "custom"]

def test_every_provider_choice_has_an_icon():
    for c in PROVIDER_CHOICES:
        assert c.icon

def test_build_config_anthropic():
    c = next(c for c in PROVIDER_CHOICES if c.name == "anthropic")
    cfg = build_config(c, model="claude-opus-4", api_key="sk-ant-x")
    assert cfg["active"] == "anthropic"
    p = cfg["providers"]["anthropic"]
    assert p["kind"] == "anthropic" and p["model"] == "claude-opus-4"
    assert p["api_key"] == "sk-ant-x"
    assert p["api_key_env"] == "ANTHROPIC_API_KEY"

def test_build_config_ollama_local_no_key():
    c = next(c for c in PROVIDER_CHOICES if c.name == "ollama")
    cfg = build_config(c, model="llama3.1")
    p = cfg["providers"]["ollama"]
    assert p["base_url"] == "http://localhost:11434/v1"
    assert "api_key" not in p

def test_build_config_custom_base_url():
    c = next(c for c in PROVIDER_CHOICES if c.name == "custom")
    cfg = build_config(c, model="mixtral", api_key="k", base_url="https://api.groq.com/openai/v1")
    p = cfg["providers"]["custom"]
    assert p["base_url"] == "https://api.groq.com/openai/v1"

def test_run_wizard_anthropic_flow():
    answers = iter(["1", "", "sk-ant-abc"])  # choose 1, default model, paste key
    printed = []
    cfg = run_wizard(lambda prompt: next(answers), lambda m: printed.append(m))
    assert cfg["active"] == "anthropic"
    assert cfg["providers"]["anthropic"]["api_key"] == "sk-ant-abc"
    assert any("provider" in m.lower() for m in printed)

def test_run_wizard_reprompts_on_bad_choice():
    answers = iter(["9", "x", "3", ""])  # invalid, invalid, then Ollama local, default model
    cfg = run_wizard(lambda prompt: next(answers), lambda m: None)
    assert cfg["active"] == "ollama"

def test_run_wizard_custom_asks_base_url():
    answers = iter(["5", "https://x/v1", "m", "k"])  # custom, base_url, model, key
    cfg = run_wizard(lambda prompt: next(answers), lambda m: None)
    assert cfg["providers"]["custom"]["base_url"] == "https://x/v1"

def test_save_config_writes_and_chmods(tmp_path: Path):
    p = tmp_path / "config.yaml"
    save_config({"active": "anthropic", "providers": {}}, p)
    assert p.exists()
    assert yaml.safe_load(p.read_text())["active"] == "anthropic"
    assert (p.stat().st_mode & 0o777) == 0o600

def test_needs_onboarding_logic(tmp_path: Path):
    missing = tmp_path / "nope.yaml"
    assert needs_onboarding(missing, env={}) is True
    assert needs_onboarding(missing, env={"ANTHROPIC_API_KEY": "x"}) is False
    existing = tmp_path / "c.yaml"
    existing.write_text("active: anthropic\n")
    assert needs_onboarding(existing, env={}) is False

def test_merge_provider_preserves_scope_and_other_providers():
    from pentai.onboarding import merge_provider
    base = {"active": "anthropic", "palette": "amber", "fx": False,
            "scope": ["10.0.0.0/24"],
            "providers": {"anthropic": {"kind": "anthropic", "model": "claude-opus-4"}}}
    new = {"active": "ollama", "palette": "green", "fx": True, "scope": [],
           "providers": {"ollama": {"kind": "openai_compat", "model": "llama3.1",
                                    "base_url": "http://localhost:11434/v1"}}}
    merged = merge_provider(base, new)
    assert merged["active"] == "ollama"
    assert merged["scope"] == ["10.0.0.0/24"]     # preserved
    assert merged["palette"] == "amber"            # preserved
    assert merged["fx"] is False                   # preserved
    assert set(merged["providers"]) == {"anthropic", "ollama"}  # both kept

def test_merge_provider_none_base_is_new():
    from pentai.onboarding import merge_provider
    new = {"active": "anthropic", "palette": "green", "fx": True, "scope": [],
           "providers": {"anthropic": {"kind": "anthropic", "model": "m"}}}
    assert merge_provider(None, new)["active"] == "anthropic"

def test_read_config_file_missing_returns_none(tmp_path: Path):
    from pentai.onboarding import read_config_file
    assert read_config_file(tmp_path / "nope.yaml") is None

def test_run_wizard_uses_secret_fn_for_key():
    prompts = iter(["1", ""])   # choose anthropic, default model
    secrets = []
    cfg = run_wizard(lambda p: next(prompts),
                     lambda m: None,
                     secret_fn=lambda p: secrets.append(p) or "sk-secret")
    assert cfg["providers"]["anthropic"]["api_key"] == "sk-secret"
    assert secrets and "ANTHROPIC_API_KEY" in secrets[0]

def test_run_wizard_uses_render_menu_instead_of_plain_list():
    # when render_menu is given (the polished rich panel/table), the plain
    # "N) label" printout is skipped - selection logic is unchanged either way
    answers = iter(["1", "", "sk-ant-abc"])   # choose anthropic, default model, key
    printed = []
    rendered = []
    cfg = run_wizard(lambda p: next(answers), lambda m: printed.append(m),
                     render_menu=lambda: rendered.append(1))
    assert rendered == [1]
    assert cfg["active"] == "anthropic"
    assert not any(") " in m for m in printed)   # no plain numbered list lines

def test_run_wizard_default_menu_unchanged_without_render_menu():
    answers = iter(["1", "", "sk-ant-abc"])
    printed = []
    run_wizard(lambda p: next(answers), lambda m: printed.append(m))
    assert any("1)" in m for m in printed)   # plain numbered list still shown by default
