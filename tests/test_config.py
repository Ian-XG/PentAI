from pentai.config import load_config, default_config, Config, ProviderConfig

def test_default_has_anthropic_active():
    cfg = default_config()
    assert cfg.active == "anthropic"
    assert "anthropic" in cfg.providers

def test_env_overrides_api_key():
    data = {"active": "anthropic",
            "providers": {"anthropic": {"kind": "anthropic", "model": "claude-opus-4"}}}
    cfg = load_config(data, env={"ANTHROPIC_API_KEY": "sk-test"})
    assert cfg.providers["anthropic"].api_key == "sk-test"

def test_openai_compat_reads_base_url():
    data = {"active": "ollama",
            "providers": {"ollama": {"kind": "openai_compat", "model": "llama3",
                                     "base_url": "http://localhost:11434/v1"}}}
    cfg = load_config(data)
    assert cfg.providers["ollama"].base_url == "http://localhost:11434/v1"
    assert cfg.providers["ollama"].kind == "openai_compat"

def test_api_key_env_field_overrides_by_name():
    data = {"active": "groq",
            "providers": {"groq": {"kind": "openai_compat", "model": "llama-3.1-70b",
                                   "api_key_env": "GROQ_API_KEY",
                                   "base_url": "https://api.groq.com/openai/v1"}}}
    cfg = load_config(data, env={"GROQ_API_KEY": "gsk-test"})
    assert cfg.providers["groq"].api_key == "gsk-test"

def test_command_timeout_defaults_to_900():
    assert default_config().command_timeout == 900
    data = {"active": "anthropic",
            "providers": {"anthropic": {"kind": "anthropic", "model": "claude-opus-4"}}}
    assert load_config(data).command_timeout == 900

def test_command_timeout_read_from_config():
    data = {"active": "anthropic", "command_timeout": 60,
            "providers": {"anthropic": {"kind": "anthropic", "model": "claude-opus-4"}}}
    assert load_config(data).command_timeout == 60

def test_load_config_file_reads_yaml(tmp_path):
    from pathlib import Path
    from pentai.config import load_config_file
    p = tmp_path / "config.yaml"
    p.write_text(
        "active: ollama\n"
        "providers:\n"
        "  ollama:\n"
        "    kind: openai_compat\n"
        "    model: llama3\n"
        "    base_url: http://localhost:11434/v1\n"
    )
    cfg = load_config_file(p, env={})
    assert cfg.active == "ollama"
    assert cfg.providers["ollama"].base_url == "http://localhost:11434/v1"

def test_load_config_file_missing_returns_default(tmp_path):
    from pentai.config import load_config_file
    cfg = load_config_file(tmp_path / "nope.yaml", env={})
    assert cfg.active == "anthropic"

def test_load_config_file_empty_returns_default(tmp_path):
    from pentai.config import load_config_file
    p = tmp_path / "config.yaml"
    p.write_text("")
    cfg = load_config_file(p, env={})
    assert cfg.active == "anthropic"

def test_load_config_raises_on_missing_active_key():
    # documents the exact failure a malformed/hand-edited config.yaml can
    # produce - callers (cli.py's startup and /setup reload) must catch this
    # and fall back to default_config() rather than crash the session.
    import pytest
    data = {"providers": {"anthropic": {"kind": "anthropic", "model": "x"}}}
    with pytest.raises(KeyError):
        load_config(data)

def test_load_config_raises_on_bad_command_timeout():
    import pytest
    data = {"active": "anthropic", "command_timeout": "none",
            "providers": {"anthropic": {"kind": "anthropic", "model": "x"}}}
    with pytest.raises(ValueError):
        load_config(data)

def test_load_config_raises_on_provider_missing_required_field():
    import pytest
    data = {"active": "anthropic", "providers": {"anthropic": {"kind": "anthropic"}}}  # no model
    with pytest.raises(TypeError):
        load_config(data)
