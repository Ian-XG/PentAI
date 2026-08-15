from ..config import Config
from .base import Provider
from .anthropic import AnthropicProvider
from .openai_compat import OpenAICompatProvider

def build_provider(cfg: Config) -> Provider:
    if cfg.active not in cfg.providers:
        raise ValueError(f"active provider {cfg.active!r} has no matching entry in providers")
    pc = cfg.providers[cfg.active]
    if pc.kind == "anthropic":
        return AnthropicProvider(pc.api_key, pc.model)
    if pc.kind == "openai_compat":
        return OpenAICompatProvider(pc.base_url or "https://api.openai.com/v1",
                                    pc.api_key, pc.model)
    raise ValueError(f"unknown provider kind: {pc.kind}")
