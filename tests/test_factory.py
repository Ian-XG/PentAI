import pytest
from pentai.config import Config, ProviderConfig
from pentai.providers.factory import build_provider
from pentai.providers.anthropic import AnthropicProvider
from pentai.providers.openai_compat import OpenAICompatProvider

def test_builds_anthropic():
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "claude-opus-4", "k")})
    assert isinstance(build_provider(cfg), AnthropicProvider)

def test_builds_openai_compat():
    cfg = Config(active="o",
                 providers={"o": ProviderConfig("openai_compat", "gpt-4o", "k",
                                                "https://api.openai.com/v1")})
    assert isinstance(build_provider(cfg), OpenAICompatProvider)

def test_unknown_kind_raises():
    cfg = Config(active="x", providers={"x": ProviderConfig("bogus", "m")})
    with pytest.raises(ValueError):
        build_provider(cfg)
