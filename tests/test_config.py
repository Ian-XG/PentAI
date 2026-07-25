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
