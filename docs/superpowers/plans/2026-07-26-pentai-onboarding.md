# PentAI Onboarding Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a first-run setup wizard so a new user is guided to pick an AI provider, paste a key, and get a working `~/.pentai/config.yaml` - instead of landing on a silent prompt that never answers.

**Architecture:** A new `pentai/onboarding.py` module holds the 5 provider choices, a pure `build_config`, a `run_wizard(prompt_fn, print_fn)` driven by injected IO (testable), `save_config` (writes yaml, chmod 600), and `needs_onboarding`. `commands.py` gains a `/setup` sentinel. `cli.py` runs the wizard on first launch (no config + no key env) and on `/setup`, and shows a clear hint when the active provider has no key.

**Tech Stack:** Python 3.11+, pyyaml (already a dep), rich/prompt_toolkit (already deps), pytest.

## Global Constraints
- Python 3.11+ (`X | Y` unions allowed).
- No test may prompt interactively or write to the real home dir - inject `prompt_fn`/`print_fn` and use `tmp_path`.
- Keys pasted in the wizard are written into `~/.pentai/config.yaml` with file mode 0600.
- The 5 providers, in order: Anthropic, OpenAI, Ollama local, Ollama Cloud, Other (OpenAI-compatible).
- Plain hyphens and straight quotes only; no em dashes or smart quotes.

---

### Task 1: Onboarding module

**Files:**
- Create: `pentai/onboarding.py`
- Test: `tests/test_onboarding.py`

**Interfaces:**
- Produces:
  - `@dataclass ProviderChoice(name: str, label: str, kind: str, default_model: str, base_url: str | None = None, api_key_env: str | None = None, needs_key: bool = True, needs_base_url: bool = False)`
  - `PROVIDER_CHOICES: list[ProviderChoice]` (the 5, in order).
  - `DEFAULT_CONFIG_PATH: Path` = `~/.pentai/config.yaml`.
  - `build_config(choice: ProviderChoice, *, model: str, api_key: str | None = None, base_url: str | None = None) -> dict`.
  - `run_wizard(prompt_fn: Callable[[str], str], print_fn: Callable[[str], None]) -> dict`.
  - `save_config(cfg: dict, path: Path = DEFAULT_CONFIG_PATH) -> Path`.
  - `needs_onboarding(path: Path = DEFAULT_CONFIG_PATH, env: dict | None = None) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_onboarding.py
from pathlib import Path
import yaml
from pentai.onboarding import (ProviderChoice, PROVIDER_CHOICES, build_config,
                               run_wizard, save_config, needs_onboarding)

def test_five_choices_in_order():
    names = [c.name for c in PROVIDER_CHOICES]
    assert names == ["anthropic", "openai", "ollama", "ollama-cloud", "custom"]

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_onboarding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.onboarding'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/onboarding.py
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

PROVIDER_CHOICES: list[ProviderChoice] = [
    ProviderChoice("anthropic", "Anthropic (Claude) - powerful, paid API", "anthropic",
                   "claude-opus-4", api_key_env="ANTHROPIC_API_KEY"),
    ProviderChoice("openai", "OpenAI (GPT) - paid API", "openai_compat",
                   "gpt-4o", base_url="https://api.openai.com/v1",
                   api_key_env="OPENAI_API_KEY"),
    ProviderChoice("ollama", "Ollama local - free, runs on your machine", "openai_compat",
                   "llama3.1", base_url="http://localhost:11434/v1", needs_key=False),
    ProviderChoice("ollama-cloud", "Ollama Cloud - hosted large models", "openai_compat",
                   "gpt-oss:120b", base_url="https://ollama.com/v1",
                   api_key_env="OLLAMA_API_KEY"),
    ProviderChoice("custom", "Other (OpenAI-compatible: Groq, OpenRouter, ...)",
                   "openai_compat", "", api_key_env="OPENAI_API_KEY", needs_base_url=True),
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

def run_wizard(prompt_fn: Callable[[str], str], print_fn: Callable[[str], None]) -> dict:
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
        api_key = prompt_fn(f"Paste your {choice.api_key_env}: ").strip() or None
    return build_config(choice, model=model, api_key=api_key, base_url=base_url)

def save_config(cfg: dict, path: Path = DEFAULT_CONFIG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    path.chmod(0o600)
    return path

def needs_onboarding(path: Path = DEFAULT_CONFIG_PATH, env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    if path.exists():
        return False
    if env.get("ANTHROPIC_API_KEY") or env.get("OPENAI_API_KEY"):
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_onboarding.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/onboarding.py tests/test_onboarding.py
git commit -m "feat: onboarding wizard module (5 providers)"
```

---

### Task 2: /setup slash command

**Files:**
- Modify: `pentai/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Consumes: existing `handle_slash(command, args, *, scope)`.
- Produces: `handle_slash("setup", [], scope=...)` returns `"__setup__"`; `/help` text lists `/setup`.

- [ ] **Step 1: Write the failing test (append to tests/test_commands.py)**

```python
def test_setup_returns_sentinel():
    from pentai.scope import Scope
    from pentai.commands import handle_slash
    assert handle_slash("setup", [], scope=Scope([])) == "__setup__"

def test_help_lists_setup():
    from pentai.scope import Scope
    from pentai.commands import handle_slash
    assert "/setup" in handle_slash("help", [], scope=Scope([]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py -v`
Expected: FAIL (setup returns unknown-command string; help lacks /setup)

- [ ] **Step 3: Implement**

In `pentai/commands.py`: update `_HELP` to include `/setup`, and add a `setup` branch in `handle_slash` returning `"__setup__"`:

```python
_HELP = ("commands: /scope add <target>, /scope list, /setup, /help, /quit")
```
Add before the `if command == "help":` line:
```python
    if command == "setup":
        return "__setup__"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_commands.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pentai/commands.py tests/test_commands.py
git commit -m "feat: /setup slash command"
```

---

### Task 3: CLI wiring - first-run wizard, /setup, missing-key hint

**Files:**
- Modify: `pentai/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `needs_onboarding`, `run_wizard`, `save_config` from `pentai.onboarding`; `load_config_file`; existing `build_agent`.
- Produces: `provider_ready(cfg) -> bool` (False when the active provider needs a key and none is set via api_key or its api_key_env). main() runs the wizard on first run and on `/setup`, and prints a hint when not ready.

- [ ] **Step 1: Write the failing test (append to tests/test_cli.py)**

```python
def test_provider_ready_true_with_key():
    from pentai.config import Config, ProviderConfig
    from pentai.cli import provider_ready
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "m", "sk-x")})
    assert provider_ready(cfg) is True

def test_provider_ready_false_without_key():
    from pentai.config import Config, ProviderConfig
    from pentai.cli import provider_ready
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "m")})
    assert provider_ready(cfg) is False

def test_provider_ready_true_for_keyless_local(monkeypatch):
    # ollama local has no api_key and no api_key_env -> considered ready
    from pentai.config import Config, ProviderConfig
    from pentai.cli import provider_ready
    cfg = Config(active="o",
                 providers={"o": ProviderConfig("openai_compat", "llama3.1",
                                                 base_url="http://localhost:11434/v1")})
    assert provider_ready(cfg) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'provider_ready'`

- [ ] **Step 3: Implement**

In `pentai/cli.py`:
- Extend the `.config` import to also import nothing new (config unchanged); add:
```python
from .onboarding import needs_onboarding, run_wizard, save_config
```
- Add the helper (module level):
```python
def provider_ready(cfg) -> bool:
    pc = cfg.providers[cfg.active]
    if pc.api_key:
        return True
    if pc.api_key_env is None:
        return True
    return False
```
- In `main()`, right after `console = Console()` and before loading config, run first-run onboarding:
```python
    if needs_onboarding():
        cfg_dict = run_wizard(lambda p: console.input(p),
                              lambda m: console.print(m))
        save_config(cfg_dict)
```
  (Then the existing `load_config_file()` call picks up the new file.)
- After `palette = get_palette(cfg.palette)` and banner, add a not-ready hint:
```python
    if not provider_ready(cfg):
        pc = cfg.providers[cfg.active]
        console.print(f"[!] no API key for '{cfg.active}'. Run /setup, "
                      f"or set {pc.api_key_env}.", style=palette["alert"])
```
- In the slash-command handling block, handle the setup sentinel (before printing the result):
```python
        if result == "__setup__":
            cfg_dict = run_wizard(lambda p: console.input(p),
                                  lambda m: console.print(m, style=palette["accent"]))
            save_config(cfg_dict)
            cfg = load_config_file()
            agent = build_agent(cfg, scope, confirm, session_dir)
            console.print("[ OK ] saved ~/.pentai/config.yaml", style=palette["accent"])
            continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest -q`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add pentai/cli.py tests/test_cli.py
git commit -m "feat: first-run onboarding wizard, /setup, and missing-key hint in CLI"
```

---

## Self-Review
- 5 providers in order (anthropic, openai, ollama, ollama-cloud, custom): Task 1. Covered.
- First-run trigger + /setup + missing-key hint: Tasks 2, 3. Covered.
- Keys written to config with 0600: Task 1 save_config. Covered.
- Injected IO for testability (no real prompts/home writes): Tasks 1, 3 use prompt_fn/print_fn and tmp_path. Covered.
- Types: `ProviderChoice`, `build_config`, `run_wizard`, `save_config`, `needs_onboarding`, `provider_ready` consistent across tasks. `provider_ready` reads `ProviderConfig.api_key`/`api_key_env` (exist since config task). Consistent.
