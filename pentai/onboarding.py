import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".pentai" / "config.yaml"

@dataclass
class ProviderChoice:
    name: str
    label: str
    kind: str
    default_model: str
    base_url: str | None = None
    api_key_env: str | None = None
    needs_key: bool = True
    needs_base_url: bool = False
    icon: str = "*"

PROVIDER_CHOICES: list[ProviderChoice] = [
    ProviderChoice("anthropic", "Anthropic (Claude) - powerful, paid API", "anthropic",
                   "claude-opus-4", api_key_env="ANTHROPIC_API_KEY", icon="◆"),
    ProviderChoice("openai", "OpenAI (GPT) - paid API", "openai_compat",
                   "gpt-4o", base_url="https://api.openai.com/v1",
                   api_key_env="OPENAI_API_KEY", icon="●"),
    ProviderChoice("ollama", "Ollama local - free, runs on your machine", "openai_compat",
                   "llama3.1", base_url="http://localhost:11434/v1", needs_key=False, icon="▲"),
    ProviderChoice("ollama-cloud", "Ollama Cloud - hosted large models", "openai_compat",
                   "gpt-oss:120b", base_url="https://ollama.com/v1",
                   api_key_env="OLLAMA_API_KEY", icon="△"),
    ProviderChoice("custom", "Other (OpenAI-compatible: Groq, OpenRouter, ...)",
                   "openai_compat", "", api_key_env="OPENAI_API_KEY", needs_base_url=True, icon="◇"),
]

def build_config(choice: ProviderChoice, *, model: str, api_key: str | None = None,
                 base_url: str | None = None) -> dict:
    pc: dict = {"kind": choice.kind, "model": model}
    url = base_url or choice.base_url
    if url:
        pc["base_url"] = url
    if choice.api_key_env:
        pc["api_key_env"] = choice.api_key_env
    if api_key:
        pc["api_key"] = api_key
    return {"active": choice.name, "palette": "green", "fx": True, "scope": [],
            "providers": {choice.name: pc}}

def run_wizard(prompt_fn: Callable[[str], str], print_fn: Callable[[str], None],
               secret_fn: Callable[[str], str] | None = None, *,
               render_menu: Callable[[], None] | None = None) -> dict:
    """Run the interactive provider wizard. `render_menu`, if given, replaces the
    default plain numbered-list printout (e.g. with a polished rich panel/table) -
    the selection/prompt logic below is unchanged either way, so it stays testable
    with plain prompt_fn/print_fn callbacks regardless of which menu is shown."""
    if render_menu is not None:
        render_menu()
    else:
        print_fn("PentAI setup - choose your AI provider:")
        for i, c in enumerate(PROVIDER_CHOICES, 1):
            print_fn(f"  {i}) {c.label}")
    choice = None
    while choice is None:
        raw = prompt_fn("> ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(PROVIDER_CHOICES):
            choice = PROVIDER_CHOICES[int(raw) - 1]
        else:
            print_fn(f"Enter a number 1-{len(PROVIDER_CHOICES)}.")
    base_url = None
    if choice.needs_base_url:
        base_url = prompt_fn("Base URL (OpenAI-compatible): ").strip() or None
    model = prompt_fn(f"Model [{choice.default_model}]: ").strip() or choice.default_model
    api_key = None
    if choice.needs_key:
        ask_key = secret_fn or prompt_fn
        api_key = ask_key(f"Paste your {choice.api_key_env}: ").strip() or None
    return build_config(choice, model=model, api_key=api_key, base_url=base_url)

def merge_provider(base: dict | None, new: dict) -> dict:
    """Merge a single-provider wizard config `new` into an existing config `base`,
    preserving base's scope/palette/fx and other providers. `active` follows `new`."""
    result: dict = dict(base) if base else {}
    result.setdefault("palette", new.get("palette", "green"))
    result.setdefault("fx", new.get("fx", True))
    result.setdefault("scope", new.get("scope", []))
    providers = dict(result.get("providers", {}))
    providers.update(new.get("providers", {}))
    result["providers"] = providers
    result["active"] = new["active"]
    return result

def read_config_file(path: Path = DEFAULT_CONFIG_PATH) -> dict | None:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text()) or None

def save_config(cfg: dict, path: Path = DEFAULT_CONFIG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(yaml.safe_dump(cfg, sort_keys=False))
    path.chmod(0o600)  # ensure mode even if the file pre-existed
    return path

def needs_onboarding(path: Path = DEFAULT_CONFIG_PATH, env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    if path.exists():
        return False
    if env.get("ANTHROPIC_API_KEY") or env.get("OPENAI_API_KEY"):
        return False
    return True
