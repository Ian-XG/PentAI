import os
from dataclasses import dataclass, field

_ENV_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

@dataclass
class ProviderConfig:
    kind: str            # "anthropic" | "openai_compat"
    model: str
    api_key: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None

@dataclass
class Config:
    active: str
    providers: dict[str, ProviderConfig]
    fx: bool = True
    palette: str = "green"
    scope: list[str] = field(default_factory=list)

def default_config() -> Config:
    return Config(
        active="anthropic",
        providers={
            "anthropic": ProviderConfig(kind="anthropic", model="claude-opus-4"),
            "openai": ProviderConfig(kind="openai_compat", model="gpt-4o",
                                     base_url="https://api.openai.com/v1"),
        },
    )

def load_config(data: dict | None = None, env: dict[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    if data is None:
        cfg = default_config()
    else:
        providers = {
            name: ProviderConfig(**p) for name, p in data.get("providers", {}).items()
        }
        cfg = Config(active=data["active"], providers=providers,
                     fx=data.get("fx", True), palette=data.get("palette", "green"),
                     scope=list(data.get("scope", [])))
    for name, pc in cfg.providers.items():
        key_env = pc.api_key_env or _ENV_KEYS.get(name)
        if pc.api_key is None and key_env and env.get(key_env):
            pc.api_key = env[key_env]
    return cfg
