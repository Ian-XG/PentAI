# PentAI MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build PentAI, an open-source terminal AI agent that acts as an ethical pentester/teacher: it proposes and executes hacking commands with per-command confirmation, analyzes output, and teaches methodology via editable playbooks.

**Architecture:** A REPL/TUI sends the user's natural-language prompt to an LLM provider (Anthropic native, or any OpenAI-compatible endpoint). The provider streams back text and tool calls. Tool calls are dispatched by an agent loop: `run_command` runs shell commands after a scope check and confirmation, `save_note` writes findings, `load_playbook` loads a phase skill. Results feed back to the LLM until it returns a final answer. Everything streams to a cyberpunk-styled terminal.

**Tech Stack:** Python 3.11+, `prompt_toolkit` (input), `rich` (rendering), `httpx` (provider HTTP), `pytest` (tests). BYOK; no vendored keys.

## Global Constraints

- Python 3.11+ (use `X | Y` unions, `list[str]`, `match` allowed).
- Package name `pentai`; console script `pentai`; installable via `pip install`.
- Providers (BYOK only, never vendor a key): Anthropic (native adapter) and any OpenAI-compatible endpoint via one adapter (OpenAI, Groq, OpenRouter, DeepSeek, Ollama local/remote, LM Studio).
- Safety: per-command `[y/N]` confirmation; scope warn+confirm on out-of-scope targets; ethical-use banner at startup; no detection-evasion or destructive defaults.
- All visual effects (boot sequence, typing, glitch) gated behind config `fx` / `--no-fx`. Default palette: phosphor green.
- All test/impl HTTP is injectable so no test makes a real network or LLM call.
- Copy/comments/docs: plain hyphens and straight quotes only; no em dashes or smart quotes.
- Every provider adapter and tool takes its side-effecting dependency (HTTP poster, subprocess runner, confirm callback) as an injected parameter for testability.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `pentai/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `pentai` with `pentai.__version__: str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_smoke.py
import pentai

def test_version_present():
    assert isinstance(pentai.__version__, str)
    assert pentai.__version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "pentai"
version = "0.1.0"
description = "Terminal AI agent for ethical hacking and learning"
requires-python = ">=3.11"
dependencies = ["prompt_toolkit>=3.0", "rich>=13.0", "httpx>=0.27", "pyyaml>=6.0"]

[project.scripts]
pentai = "pentai.cli:main"

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["pentai*"]
```

```python
# pentai/__init__.py
__version__ = "0.1.0"
```

```python
# tests/__init__.py
```

```gitignore
# .gitignore
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.venv/
build/
dist/
```

- [ ] **Step 4: Install editable and run the test**

Run: `pip install -e ".[dev]" && python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml pentai/__init__.py tests/__init__.py tests/test_smoke.py .gitignore
git commit -m "feat: project scaffold"
```

---

### Task 2: Config loader

**Files:**
- Create: `pentai/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `@dataclass ProviderConfig(kind: str, model: str, api_key: str | None = None, base_url: str | None = None)` where `kind in {"anthropic", "openai_compat"}`.
  - `@dataclass Config(active: str, providers: dict[str, ProviderConfig], fx: bool = True, palette: str = "green", scope: list[str] = <empty>)`.
  - `load_config(data: dict | None = None, env: dict[str, str] | None = None) -> Config` — merges a config dict with env-var key overrides. `env` defaults to `os.environ`. Env keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`.
  - `default_config() -> Config` — the built-in default (anthropic active, both provider stubs present).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/config.py
import os
from dataclasses import dataclass, field

_ENV_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

@dataclass
class ProviderConfig:
    kind: str            # "anthropic" | "openai_compat"
    model: str
    api_key: str | None = None
    base_url: str | None = None

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
        key_env = _ENV_KEYS.get(name)
        if pc.api_key is None and key_env and env.get(key_env):
            pc.api_key = env[key_env]
    return cfg
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/config.py tests/test_config.py
git commit -m "feat: config loader with env-var key overrides"
```

---

### Task 3: Scope manager

**Files:**
- Create: `pentai/scope.py`
- Test: `tests/test_scope.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `extract_targets(command: str) -> list[str]` — pulls IPv4 addresses and hostnames (including hosts inside URLs) out of a command string.
  - `class Scope` with `__init__(self, entries: list[str])`, `add(self, entry: str) -> None`, `contains(self, target: str) -> bool` (matches exact IP, CIDR membership, and domain globs like `*.example.com`), and `out_of_scope(self, command: str) -> list[str]` (targets in the command not covered by any entry).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scope.py
from pentai.scope import extract_targets, Scope

def test_extract_ip_and_host():
    t = extract_targets("nmap -sV 10.0.0.5 http://juice.local/rest")
    assert "10.0.0.5" in t
    assert "juice.local" in t

def test_cidr_membership():
    s = Scope(["10.0.0.0/24"])
    assert s.contains("10.0.0.5")
    assert not s.contains("10.0.1.5")

def test_domain_glob():
    s = Scope(["*.juice.local"])
    assert s.contains("api.juice.local")
    assert not s.contains("evil.com")

def test_out_of_scope_lists_uncovered():
    s = Scope(["10.0.0.0/24"])
    assert s.out_of_scope("nmap 10.0.0.5 1.2.3.4") == ["1.2.3.4"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scope.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.scope'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/scope.py
import ipaddress
import re
from fnmatch import fnmatch

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HOST_RE = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")

def extract_targets(command: str) -> list[str]:
    found: list[str] = []
    for m in _IP_RE.findall(command):
        if m not in found:
            found.append(m)
    for m in _HOST_RE.findall(command):
        if m not in found:
            found.append(m)
    return found

class Scope:
    def __init__(self, entries: list[str]):
        self.entries = list(entries)

    def add(self, entry: str) -> None:
        if entry not in self.entries:
            self.entries.append(entry)

    def contains(self, target: str) -> bool:
        for entry in self.entries:
            if self._match(entry, target):
                return True
        return False

    def out_of_scope(self, command: str) -> list[str]:
        return [t for t in extract_targets(command) if not self.contains(t)]

    @staticmethod
    def _match(entry: str, target: str) -> bool:
        try:
            net = ipaddress.ip_network(entry, strict=False)
            addr = ipaddress.ip_address(target)
            return addr in net
        except ValueError:
            pass
        return fnmatch(target, entry) or entry == target
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scope.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/scope.py tests/test_scope.py
git commit -m "feat: scope manager with CIDR and domain-glob matching"
```

---

### Task 4: Provider base types

**Files:**
- Create: `pentai/providers/__init__.py`
- Create: `pentai/providers/base.py`
- Test: `tests/test_providers_base.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `@dataclass Tool(name: str, description: str, parameters: dict)` — parameters is a JSON schema.
  - `@dataclass ToolCall(id: str, name: str, arguments: dict)`.
  - `@dataclass Message(role: str, content: str = "", tool_calls: list[ToolCall] = <empty>, tool_call_id: str | None = None)` — role in `{"user","assistant","tool"}`.
  - Streaming events: `@dataclass TextDelta(text: str)`, `@dataclass ToolCallEvent(id: str, name: str, arguments: dict)`, `@dataclass Done(stop_reason: str)` where stop_reason in `{"end","tool_use"}`.
  - `Event = TextDelta | ToolCallEvent | Done`.
  - `class Provider(Protocol): def chat(self, messages: list[Message], tools: list[Tool]) -> Iterator[Event]: ...`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_providers_base.py
from pentai.providers.base import Tool, ToolCall, Message, TextDelta, ToolCallEvent, Done

def test_message_defaults():
    m = Message(role="user", content="hi")
    assert m.tool_calls == []
    assert m.tool_call_id is None

def test_event_shapes():
    assert TextDelta("x").text == "x"
    assert ToolCallEvent("id1", "run_command", {"command": "ls"}).name == "run_command"
    assert Done("tool_use").stop_reason == "tool_use"
    assert ToolCall("id1", "run_command", {}).id == "id1"
    assert Tool("run_command", "run a shell command", {"type": "object"}).name == "run_command"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_providers_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.providers'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/providers/__init__.py
```

```python
# pentai/providers/base.py
from dataclasses import dataclass, field
from typing import Iterator, Protocol

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class Message:
    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None

@dataclass
class TextDelta:
    text: str

@dataclass
class ToolCallEvent:
    id: str
    name: str
    arguments: dict

@dataclass
class Done:
    stop_reason: str

Event = TextDelta | ToolCallEvent | Done

class Provider(Protocol):
    def chat(self, messages: list[Message], tools: list[Tool]) -> Iterator[Event]:
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_providers_base.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/providers/__init__.py pentai/providers/base.py tests/test_providers_base.py
git commit -m "feat: neutral provider types and Provider protocol"
```

---

### Task 5: OpenAI-compatible adapter

**Files:**
- Create: `pentai/providers/openai_compat.py`
- Test: `tests/test_openai_compat.py`

**Interfaces:**
- Consumes: `Message`, `Tool`, `TextDelta`, `ToolCallEvent`, `Done` from `pentai.providers.base`.
- Produces:
  - `build_payload(messages: list[Message], tools: list[Tool], model: str) -> dict` — builds the OpenAI chat-completions request body (`stream=True`, messages, tools).
  - `parse_sse_chunk(data: dict) -> Event | None` — turns one parsed SSE JSON chunk into an event (text delta, tool-call event on finish, or done).
  - `class OpenAICompatProvider` with `__init__(self, base_url: str, api_key: str | None, model: str, poster: Callable | None = None)` implementing `chat(...)`. `poster(url, headers, json) -> Iterator[str]` yields raw SSE lines; defaults to an httpx streaming poster.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_openai_compat.py
from pentai.providers.base import Message, Tool, TextDelta, Done
from pentai.providers.openai_compat import build_payload, parse_sse_chunk, OpenAICompatProvider

def test_build_payload_includes_stream_and_tools():
    tools = [Tool("run_command", "run", {"type": "object"})]
    p = build_payload([Message("user", "hi")], tools, "gpt-4o")
    assert p["stream"] is True
    assert p["model"] == "gpt-4o"
    assert p["tools"][0]["function"]["name"] == "run_command"
    assert p["messages"][0] == {"role": "user", "content": "hi"}

def test_parse_text_delta():
    chunk = {"choices": [{"delta": {"content": "he"}}]}
    ev = parse_sse_chunk(chunk)
    assert isinstance(ev, TextDelta) and ev.text == "he"

def test_parse_done():
    chunk = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
    ev = parse_sse_chunk(chunk)
    assert isinstance(ev, Done) and ev.stop_reason == "end"

def test_chat_streams_from_injected_poster():
    lines = [
        'data: {"choices":[{"delta":{"content":"hi"}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
        'data: [DONE]',
    ]
    prov = OpenAICompatProvider("http://x/v1", "k", "gpt-4o",
                                poster=lambda url, headers, json: iter(lines))
    events = list(prov.chat([Message("user", "hi")], []))
    assert any(isinstance(e, TextDelta) and e.text == "hi" for e in events)
    assert any(isinstance(e, Done) for e in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_openai_compat.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.providers.openai_compat'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/providers/openai_compat.py
import json as _json
from typing import Callable, Iterator
import httpx
from .base import Message, Tool, TextDelta, ToolCallEvent, Done, Event

def _message_to_dict(m: Message) -> dict:
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
    d: dict = {"role": m.role, "content": m.content}
    if m.tool_calls:
        d["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name, "arguments": _json.dumps(tc.arguments)}}
            for tc in m.tool_calls
        ]
    return d

def build_payload(messages: list[Message], tools: list[Tool], model: str) -> dict:
    payload: dict = {
        "model": model,
        "stream": True,
        "messages": [_message_to_dict(m) for m in messages],
    }
    if tools:
        payload["tools"] = [
            {"type": "function",
             "function": {"name": t.name, "description": t.description,
                          "parameters": t.parameters}}
            for t in tools
        ]
    return payload

def parse_sse_chunk(data: dict) -> Event | None:
    choice = (data.get("choices") or [{}])[0]
    delta = choice.get("delta", {})
    if delta.get("tool_calls"):
        tc = delta["tool_calls"][0]
        args = tc.get("function", {}).get("arguments") or "{}"
        try:
            parsed = _json.loads(args)
        except _json.JSONDecodeError:
            parsed = {}
        return ToolCallEvent(tc.get("id", ""), tc.get("function", {}).get("name", ""), parsed)
    if delta.get("content"):
        return TextDelta(delta["content"])
    if choice.get("finish_reason"):
        reason = "tool_use" if choice["finish_reason"] == "tool_calls" else "end"
        return Done(reason)
    return None

def _httpx_poster(url: str, headers: dict, json: dict) -> Iterator[str]:
    with httpx.stream("POST", url, headers=headers, json=json, timeout=None) as resp:
        for line in resp.iter_lines():
            yield line

class OpenAICompatProvider:
    def __init__(self, base_url: str, api_key: str | None, model: str,
                 poster: Callable | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._poster = poster or _httpx_poster

    def chat(self, messages: list[Message], tools: list[Tool]) -> Iterator[Event]:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = build_payload(messages, tools, self.model)
        for line in self._poster(url, headers, payload):
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            ev = parse_sse_chunk(_json.loads(data))
            if ev is not None:
                yield ev
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_openai_compat.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/providers/openai_compat.py tests/test_openai_compat.py
git commit -m "feat: OpenAI-compatible streaming adapter (covers OpenAI, Ollama, Groq, etc.)"
```

---

### Task 6: Anthropic adapter

**Files:**
- Create: `pentai/providers/anthropic.py`
- Test: `tests/test_anthropic.py`

**Interfaces:**
- Consumes: `Message`, `Tool`, `TextDelta`, `ToolCallEvent`, `Done` from `pentai.providers.base`.
- Produces:
  - `build_payload(messages: list[Message], tools: list[Tool], model: str) -> dict` — Anthropic Messages API body (`stream=True`, `max_tokens`, `tools` in Anthropic schema, `tool_result` blocks for tool messages).
  - `parse_sse_event(event_type: str, data: dict) -> Event | None` — maps an Anthropic SSE event to a neutral event.
  - `class AnthropicProvider` with `__init__(self, api_key: str | None, model: str, poster: Callable | None = None)` implementing `chat(...)`. `poster(url, headers, json) -> Iterator[tuple[str, dict]]` yields `(event_type, data)` pairs; defaults to an httpx SSE poster.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_anthropic.py
from pentai.providers.base import Message, Tool, TextDelta, ToolCallEvent, Done
from pentai.providers.anthropic import build_payload, parse_sse_event, AnthropicProvider

def test_build_payload_shape():
    p = build_payload([Message("user", "hi")], [Tool("run_command", "run", {"type": "object"})],
                      "claude-opus-4")
    assert p["stream"] is True
    assert p["model"] == "claude-opus-4"
    assert p["tools"][0]["name"] == "run_command"
    assert "max_tokens" in p

def test_parse_text_delta():
    ev = parse_sse_event("content_block_delta",
                         {"delta": {"type": "text_delta", "text": "hi"}})
    assert isinstance(ev, TextDelta) and ev.text == "hi"

def test_parse_tool_use_start():
    ev = parse_sse_event("content_block_start",
                         {"content_block": {"type": "tool_use", "id": "t1",
                                            "name": "run_command", "input": {}}})
    assert isinstance(ev, ToolCallEvent) and ev.name == "run_command"

def test_chat_streams_from_injected_poster():
    events_in = [
        ("content_block_delta", {"delta": {"type": "text_delta", "text": "hi"}}),
        ("message_stop", {}),
    ]
    prov = AnthropicProvider("k", "claude-opus-4",
                             poster=lambda url, headers, json: iter(events_in))
    out = list(prov.chat([Message("user", "hi")], []))
    assert any(isinstance(e, TextDelta) for e in out)
    assert any(isinstance(e, Done) for e in out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_anthropic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.providers.anthropic'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/providers/anthropic.py
import json as _json
from typing import Callable, Iterator
import httpx
from .base import Message, Tool, TextDelta, ToolCallEvent, Done, Event

_API = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"

def _message_to_dict(m: Message) -> dict:
    if m.role == "tool":
        return {"role": "user",
                "content": [{"type": "tool_result", "tool_use_id": m.tool_call_id,
                             "content": m.content}]}
    if m.role == "assistant" and m.tool_calls:
        blocks: list[dict] = []
        if m.content:
            blocks.append({"type": "text", "text": m.content})
        for tc in m.tool_calls:
            blocks.append({"type": "tool_use", "id": tc.id, "name": tc.name,
                           "input": tc.arguments})
        return {"role": "assistant", "content": blocks}
    return {"role": m.role, "content": m.content}

def build_payload(messages: list[Message], tools: list[Tool], model: str) -> dict:
    payload: dict = {
        "model": model,
        "stream": True,
        "max_tokens": 4096,
        "messages": [_message_to_dict(m) for m in messages],
    }
    if tools:
        payload["tools"] = [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]
    return payload

def parse_sse_event(event_type: str, data: dict) -> Event | None:
    if event_type == "content_block_delta":
        delta = data.get("delta", {})
        if delta.get("type") == "text_delta":
            return TextDelta(delta.get("text", ""))
        return None
    if event_type == "content_block_start":
        block = data.get("content_block", {})
        if block.get("type") == "tool_use":
            return ToolCallEvent(block.get("id", ""), block.get("name", ""),
                                 block.get("input", {}))
        return None
    if event_type == "message_stop":
        return Done("end")
    return None

def _httpx_poster(url: str, headers: dict, json: dict) -> Iterator[tuple[str, dict]]:
    with httpx.stream("POST", url, headers=headers, json=json, timeout=None) as resp:
        event_type = ""
        for line in resp.iter_lines():
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                yield event_type, _json.loads(line[len("data:"):].strip())

class AnthropicProvider:
    def __init__(self, api_key: str | None, model: str, poster: Callable | None = None):
        self.api_key = api_key
        self.model = model
        self._poster = poster or _httpx_poster

    def chat(self, messages: list[Message], tools: list[Tool]) -> Iterator[Event]:
        headers = {"Content-Type": "application/json",
                   "anthropic-version": _VERSION,
                   "x-api-key": self.api_key or ""}
        payload = build_payload(messages, tools, self.model)
        for event_type, data in self._poster(_API, headers, payload):
            ev = parse_sse_event(event_type, data)
            if ev is not None:
                yield ev
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_anthropic.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/providers/anthropic.py tests/test_anthropic.py
git commit -m "feat: Anthropic Messages API streaming adapter"
```

---

### Task 7: Provider factory

**Files:**
- Create: `pentai/providers/factory.py`
- Test: `tests/test_factory.py`

**Interfaces:**
- Consumes: `Config`, `ProviderConfig` from `pentai.config`; `AnthropicProvider`; `OpenAICompatProvider`.
- Produces: `build_provider(cfg: Config) -> Provider` — instantiates the adapter for `cfg.active` based on its `kind`. Raises `ValueError` for unknown kinds.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_factory.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_factory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.providers.factory'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/providers/factory.py
from ..config import Config
from .base import Provider
from .anthropic import AnthropicProvider
from .openai_compat import OpenAICompatProvider

def build_provider(cfg: Config) -> Provider:
    pc = cfg.providers[cfg.active]
    if pc.kind == "anthropic":
        return AnthropicProvider(pc.api_key, pc.model)
    if pc.kind == "openai_compat":
        return OpenAICompatProvider(pc.base_url or "https://api.openai.com/v1",
                                    pc.api_key, pc.model)
    raise ValueError(f"unknown provider kind: {pc.kind}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_factory.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/providers/factory.py tests/test_factory.py
git commit -m "feat: provider factory"
```

---

### Task 8: Shell tool with scope + confirmation

**Files:**
- Create: `pentai/tools/__init__.py`
- Create: `pentai/tools/shell.py`
- Test: `tests/test_shell.py`

**Interfaces:**
- Consumes: `Scope` from `pentai.scope`.
- Produces:
  - `@dataclass CommandResult(stdout: str, stderr: str, exit_code: int)`.
  - `run_command(command: str, *, scope: Scope, confirm: Callable[[str], bool], runner: Callable[[str], CommandResult] | None = None) -> str` — checks scope (out-of-scope targets require a confirm), then a per-command confirm, then executes via `runner` (defaults to a real subprocess runner) and returns a formatted result string. Returns a `[cancelled ...]` string when a confirm is declined.
  - `RUN_COMMAND_TOOL: Tool` — the JSON-schema tool definition for the agent.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_shell.py
from pentai.scope import Scope
from pentai.tools.shell import run_command, CommandResult, RUN_COMMAND_TOOL

def _fixed_runner(out):
    return lambda cmd: CommandResult(out, "", 0)

def test_runs_when_in_scope_and_confirmed():
    r = run_command("nmap 10.0.0.5", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda prompt: True, runner=_fixed_runner("open ports"))
    assert "open ports" in r

def test_cancelled_when_declined():
    r = run_command("nmap 10.0.0.5", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda prompt: False, runner=_fixed_runner("x"))
    assert "cancelled" in r.lower()

def test_out_of_scope_requires_confirm():
    seen = []
    def confirm(prompt):
        seen.append(prompt)
        return False
    r = run_command("nmap 1.2.3.4", scope=Scope(["10.0.0.0/24"]),
                    confirm=confirm, runner=_fixed_runner("x"))
    assert any("scope" in p.lower() for p in seen)
    assert "cancelled" in r.lower()

def test_tool_schema_name():
    assert RUN_COMMAND_TOOL.name == "run_command"
    assert "command" in RUN_COMMAND_TOOL.parameters["properties"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_shell.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.tools'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/tools/__init__.py
```

```python
# pentai/tools/shell.py
import subprocess
from dataclasses import dataclass
from typing import Callable
from ..scope import Scope
from ..providers.base import Tool

@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int

def _subprocess_runner(command: str) -> CommandResult:
    proc = subprocess.run(command, shell=True, capture_output=True, text=True)
    return CommandResult(proc.stdout, proc.stderr, proc.returncode)

def run_command(command: str, *, scope: Scope, confirm: Callable[[str], bool],
                runner: Callable[[str], CommandResult] | None = None) -> str:
    runner = runner or _subprocess_runner
    oos = scope.out_of_scope(command)
    if oos and not confirm(f"OUT OF SCOPE: {', '.join(oos)}. You confirm you are authorized?"):
        return "[cancelled: target out of authorized scope]"
    if not confirm(f"execute: {command}"):
        return "[cancelled by user]"
    result = runner(command)
    return f"exit_code={result.exit_code}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"

RUN_COMMAND_TOOL = Tool(
    name="run_command",
    description="Run a shell command on the operator's machine and return its output. "
                "Used for recon, scanning, and exploitation against authorized targets only.",
    parameters={
        "type": "object",
        "properties": {"command": {"type": "string", "description": "The shell command to run"}},
        "required": ["command"],
    },
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_shell.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/tools/__init__.py pentai/tools/shell.py tests/test_shell.py
git commit -m "feat: run_command tool with scope check and confirmation"
```

---

### Task 9: Notes and playbook tools

**Files:**
- Create: `pentai/tools/notes.py`
- Create: `pentai/tools/playbooks.py`
- Test: `tests/test_notes.py`
- Test: `tests/test_playbooks.py`

**Interfaces:**
- Consumes: `Tool` from `pentai.providers.base`.
- Produces:
  - `save_note(text: str, *, session_dir: Path) -> str` — appends `text` to `session_dir/notes.md`, returns a confirmation string. `SAVE_NOTE_TOOL: Tool`.
  - `list_playbooks(skills_dir: Path) -> list[str]` — playbook names (filenames without `.md`).
  - `load_playbook(name: str, *, skills_dir: Path) -> str` — returns file contents, or `"[playbook not found: <name>]"` if missing. `LOAD_PLAYBOOK_TOOL: Tool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_notes.py
from pathlib import Path
from pentai.tools.notes import save_note, SAVE_NOTE_TOOL

def test_save_note_appends(tmp_path: Path):
    save_note("finding one", session_dir=tmp_path)
    save_note("finding two", session_dir=tmp_path)
    content = (tmp_path / "notes.md").read_text()
    assert "finding one" in content and "finding two" in content

def test_note_tool_name():
    assert SAVE_NOTE_TOOL.name == "save_note"
```

```python
# tests/test_playbooks.py
from pathlib import Path
from pentai.tools.playbooks import list_playbooks, load_playbook, LOAD_PLAYBOOK_TOOL

def test_list_and_load(tmp_path: Path):
    (tmp_path / "recon.md").write_text("# Recon")
    assert "recon" in list_playbooks(tmp_path)
    assert "# Recon" in load_playbook("recon", skills_dir=tmp_path)

def test_missing_playbook(tmp_path: Path):
    assert "not found" in load_playbook("ghost", skills_dir=tmp_path)

def test_load_tool_name():
    assert LOAD_PLAYBOOK_TOOL.name == "load_playbook"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_notes.py tests/test_playbooks.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/tools/notes.py
from pathlib import Path
from ..providers.base import Tool

def save_note(text: str, *, session_dir: Path) -> str:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / "notes.md"
    with path.open("a") as f:
        f.write(text.rstrip() + "\n\n")
    return f"[saved note to {path}]"

SAVE_NOTE_TOOL = Tool(
    name="save_note",
    description="Save a finding, credential, or report note to the session notes file.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string", "description": "Markdown note to append"}},
        "required": ["text"],
    },
)
```

```python
# pentai/tools/playbooks.py
from pathlib import Path
from ..providers.base import Tool

def list_playbooks(skills_dir: Path) -> list[str]:
    if not skills_dir.exists():
        return []
    return sorted(p.stem for p in skills_dir.glob("*.md"))

def load_playbook(name: str, *, skills_dir: Path) -> str:
    path = skills_dir / f"{name}.md"
    if not path.exists():
        return f"[playbook not found: {name}]"
    return path.read_text()

LOAD_PLAYBOOK_TOOL = Tool(
    name="load_playbook",
    description="Load a methodology playbook for the current phase "
                "(recon, web-owasp, priv-esc, reporting).",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Playbook name without .md"}},
        "required": ["name"],
    },
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_notes.py tests/test_playbooks.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/tools/notes.py pentai/tools/playbooks.py tests/test_notes.py tests/test_playbooks.py
git commit -m "feat: save_note and playbook tools"
```

---

### Task 10: Agent loop

**Files:**
- Create: `pentai/agent.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: `Provider`, `Message`, `Tool`, `ToolCall`, `TextDelta`, `ToolCallEvent`, `Done` from `pentai.providers.base`.
- Produces:
  - `@dataclass ToolSpec(tool: Tool, run: Callable[[dict], str])`.
  - `@dataclass ToolInvocation(name: str, arguments: dict, result: str)`.
  - `AgentEvent = TextDelta | ToolInvocation`.
  - `class Agent` with `__init__(self, provider: Provider, system_prompt: str, tools: dict[str, ToolSpec], history: list[Message] | None = None)` and `send(self, user_text: str) -> Iterator[AgentEvent]`. It appends the user message, calls the provider, streams `TextDelta`s, and on a `ToolCallEvent` runs the matching `ToolSpec.run`, appends assistant + tool messages, and re-invokes the provider until a `Done("end")` with no pending tool call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent.py
from pentai.providers.base import Message, Tool, TextDelta, ToolCallEvent, Done
from pentai.agent import Agent, ToolSpec, ToolInvocation

class ScriptedProvider:
    """Yields a scripted list of event-lists, one per chat() call."""
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = 0
    def chat(self, messages, tools):
        script = self.scripts[self.calls]
        self.calls += 1
        yield from script

def test_plain_text_turn():
    prov = ScriptedProvider([[TextDelta("hello"), Done("end")]])
    agent = Agent(prov, "sys", {})
    out = list(agent.send("hi"))
    assert any(isinstance(e, TextDelta) and e.text == "hello" for e in out)

def test_tool_call_then_final_answer():
    tool = Tool("run_command", "run", {"type": "object"})
    calls = []
    spec = ToolSpec(tool, lambda args: calls.append(args) or "exit=0")
    prov = ScriptedProvider([
        [ToolCallEvent("t1", "run_command", {"command": "ls"}), Done("tool_use")],
        [TextDelta("done"), Done("end")],
    ])
    agent = Agent(prov, "sys", {"run_command": spec})
    out = list(agent.send("scan"))
    assert calls == [{"command": "ls"}]
    assert any(isinstance(e, ToolInvocation) and e.result == "exit=0" for e in out)
    assert any(isinstance(e, TextDelta) and e.text == "done" for e in out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.agent'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/agent.py
from dataclasses import dataclass, field
from typing import Callable, Iterator
from .providers.base import (Provider, Message, Tool, ToolCall,
                             TextDelta, ToolCallEvent, Done)

@dataclass
class ToolSpec:
    tool: Tool
    run: Callable[[dict], str]

@dataclass
class ToolInvocation:
    name: str
    arguments: dict
    result: str

AgentEvent = TextDelta | ToolInvocation

class Agent:
    def __init__(self, provider: Provider, system_prompt: str,
                 tools: dict[str, ToolSpec], history: list[Message] | None = None):
        self.provider = provider
        self.system_prompt = system_prompt
        self.tools = tools
        self.history: list[Message] = history if history is not None else []
        self._tool_defs: list[Tool] = [s.tool for s in tools.values()]

    def send(self, user_text: str) -> Iterator[AgentEvent]:
        self.history.append(Message("user", user_text))
        while True:
            text_parts: list[str] = []
            pending: list[ToolCall] = []
            for ev in self.provider.chat(self.history, self._tool_defs):
                if isinstance(ev, TextDelta):
                    text_parts.append(ev.text)
                    yield ev
                elif isinstance(ev, ToolCallEvent):
                    pending.append(ToolCall(ev.id, ev.name, ev.arguments))
                elif isinstance(ev, Done):
                    pass
            assistant_text = "".join(text_parts)
            self.history.append(Message("assistant", assistant_text, tool_calls=pending))
            if not pending:
                return
            for call in pending:
                spec = self.tools.get(call.name)
                result = spec.run(call.arguments) if spec else f"[unknown tool: {call.name}]"
                self.history.append(Message("tool", result, tool_call_id=call.id))
                yield ToolInvocation(call.name, call.arguments, result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agent.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/agent.py tests/test_agent.py
git commit -m "feat: agent loop with tool dispatch"
```

---

### Task 11: UI theme and banner

**Files:**
- Create: `pentai/ui/__init__.py`
- Create: `pentai/ui/theme.py`
- Create: `pentai/ui/banner.py`
- Test: `tests/test_ui_banner.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `theme.py`: `PALETTES: dict[str, dict[str, str]]` with keys `green`, `amber`, `red`, each mapping style roles (`primary`, `accent`, `dim`, `alert`) to rich style strings. `get_palette(name: str) -> dict[str, str]` (falls back to `green`).
  - `banner.py`: `SIGIL: str` (the approved Hermes mark), `SIGIL_SIMPLE: str` (ASCII fallback), `render_banner(palette: dict[str, str], simple: bool = False) -> str`, `boot_lines() -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_banner.py
from pentai.ui.theme import get_palette, PALETTES
from pentai.ui.banner import render_banner, boot_lines, SIGIL, SIGIL_SIMPLE

def test_palettes_have_roles():
    for name in ("green", "amber", "red"):
        p = PALETTES[name]
        assert {"primary", "accent", "dim", "alert"} <= set(p)

def test_get_palette_fallback():
    assert get_palette("nonexistent") == PALETTES["green"]

def test_banner_contains_wordmark():
    out = render_banner(get_palette("green"))
    assert "P" in out and "PENTAI" in out.replace(" ", "")

def test_simple_banner_has_no_braille_or_box():
    assert render_banner(get_palette("green"), simple=True).count("◈") == 0

def test_boot_lines_nonempty():
    lines = boot_lines()
    assert lines and all(line.startswith("[") for line in lines)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ui_banner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.ui'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/ui/__init__.py
```

```python
# pentai/ui/theme.py
PALETTES: dict[str, dict[str, str]] = {
    "green": {"primary": "bold green", "accent": "bright_green", "dim": "green dim", "alert": "bold red"},
    "amber": {"primary": "bold yellow", "accent": "bright_yellow", "dim": "yellow dim", "alert": "bold red"},
    "red":   {"primary": "bold red", "accent": "bright_red", "dim": "red dim", "alert": "bold white on red"},
}

def get_palette(name: str) -> dict[str, str]:
    return PALETTES.get(name, PALETTES["green"])
```

```python
# pentai/ui/banner.py
SIGIL = r"""
                  ◈
        ╲╲╲╲     ╱│╲     ╱╱╱╱
      ╲╲╲╲╲╲    ╱ │ ╲    ╱╱╱╱╱╱
    ▚▚▚▚▚▚▚▚   ╱  │  ╲   ▞▞▞▞▞▞▞▞
  ◄═══════════════│═══════════════►
                 ╲│╱
                  │
                  ▼
      P   E   N   T   A   I
"""

SIGIL_SIMPLE = r"""
        /|\
   <----+---->
        |
        v
    P E N T A I
"""

def render_banner(palette: dict[str, str], simple: bool = False) -> str:
    art = SIGIL_SIMPLE if simple else SIGIL
    tagline = "[ authorized use only ]"
    return f"{art}\n      {tagline}\n"

def boot_lines() -> list[str]:
    return [
        "[ OK ] initializing modules",
        "[ OK ] loading playbooks",
        "[ OK ] provider adapters online",
        "[ OK ] scope guard armed",
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ui_banner.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/ui/__init__.py pentai/ui/theme.py pentai/ui/banner.py tests/test_ui_banner.py
git commit -m "feat: UI theme palettes and Hermes banner"
```

---

### Task 12: UI render helpers

**Files:**
- Create: `pentai/ui/render.py`
- Test: `tests/test_ui_render.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `format_tag(kind: str, text: str) -> str` — prefixes a line with a bracket tag. `kind in {"AI","EXEC","VULN","INFO"}`; unknown kind falls back to `INFO`.
  - `status_bar(provider: str, model: str, scope_count: int, cmds: int) -> str` — returns a one-line status string like `-[ provider:model ]-[ scope:N ]-[ cmds:N ]-`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_render.py
from pentai.ui.render import format_tag, status_bar

def test_format_tag_known():
    assert format_tag("EXEC", "nmap 10.0.0.5").startswith("[EXEC]")
    assert format_tag("VULN", "SQLi").startswith("[!] VULN")

def test_format_tag_unknown_falls_back():
    assert format_tag("bogus", "x").startswith("[INFO]")

def test_status_bar_contents():
    s = status_bar("anthropic", "claude-opus-4", 2, 5)
    assert "anthropic:claude-opus-4" in s
    assert "scope:2" in s
    assert "cmds:5" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.ui.render'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/ui/render.py
_TAGS = {"AI": "[AI]", "EXEC": "[EXEC]", "VULN": "[!] VULN", "INFO": "[INFO]"}

def format_tag(kind: str, text: str) -> str:
    tag = _TAGS.get(kind, _TAGS["INFO"])
    return f"{tag} {text}"

def status_bar(provider: str, model: str, scope_count: int, cmds: int) -> str:
    return f"-[ {provider}:{model} ]-[ scope:{scope_count} ]-[ cmds:{cmds} ]-"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/ui/render.py tests/test_ui_render.py
git commit -m "feat: UI tag and status-bar helpers"
```

---

### Task 13: Slash-command parsing

**Files:**
- Create: `pentai/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Consumes: `Scope` from `pentai.scope`.
- Produces:
  - `parse_slash(line: str) -> tuple[str, list[str]] | None` — returns `(command, args)` for lines starting with `/`, else `None`.
  - `handle_slash(command: str, args: list[str], *, scope: Scope) -> str` — mutates scope for `/scope add|list`, returns a help string for `/help`, `"__quit__"` for `/quit`, and `"[unknown command]"` otherwise.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commands.py
from pentai.scope import Scope
from pentai.commands import parse_slash, handle_slash

def test_parse_slash():
    assert parse_slash("/scope add 10.0.0.0/24") == ("scope", ["add", "10.0.0.0/24"])
    assert parse_slash("hello") is None

def test_scope_add_and_list():
    s = Scope([])
    handle_slash("scope", ["add", "10.0.0.0/24"], scope=s)
    assert "10.0.0.0/24" in s.entries
    assert "10.0.0.0/24" in handle_slash("scope", ["list"], scope=s)

def test_quit_and_unknown():
    s = Scope([])
    assert handle_slash("quit", [], scope=s) == "__quit__"
    assert "unknown" in handle_slash("bogus", [], scope=s).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_commands.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.commands'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/commands.py
from .scope import Scope

_HELP = ("commands: /scope add <target>, /scope list, /help, /quit")

def parse_slash(line: str) -> tuple[str, list[str]] | None:
    if not line.startswith("/"):
        return None
    parts = line[1:].split()
    if not parts:
        return None
    return parts[0], parts[1:]

def handle_slash(command: str, args: list[str], *, scope: Scope) -> str:
    if command == "scope":
        if args and args[0] == "add" and len(args) > 1:
            scope.add(args[1])
            return f"[scope +] {args[1]}"
        if args and args[0] == "list":
            return "scope: " + (", ".join(scope.entries) or "(empty)")
        return "usage: /scope add <target> | /scope list"
    if command == "help":
        return _HELP
    if command == "quit":
        return "__quit__"
    return "[unknown command] " + command
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_commands.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/commands.py tests/test_commands.py
git commit -m "feat: slash-command parsing and handling"
```

---

### Task 14: Playbook and system-prompt content

**Files:**
- Create: `pentai/prompts/system.md`
- Create: `pentai/skills/recon.md`
- Create: `pentai/skills/web-owasp.md`
- Create: `pentai/skills/priv-esc.md`
- Create: `pentai/skills/reporting.md`
- Modify: `pyproject.toml` (package-data so `.md` files ship in the wheel)
- Test: `tests/test_content.py`

**Interfaces:**
- Consumes: `list_playbooks` from `pentai.tools.playbooks`.
- Produces: shipped markdown content resolvable at `pentai/skills/` and `pentai/prompts/system.md`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_content.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_content.py -v`
Expected: FAIL (files missing / assertion error)

- [ ] **Step 3: Write the content**

`pentai/prompts/system.md`:

```markdown
You are PentAI, an expert ethical penetration tester and patient teacher.

Rules of engagement:
- Operate only against targets the operator is authorized to test. If a target
  looks out of scope, say so and ask before proceeding.
- You may propose and run reconnaissance, scanning, and exploitation commands via
  the run_command tool. Every command is confirmed by the operator before it runs.
- Teach as you go: explain what each command does, why you chose it, and what the
  output means, as if mentoring a junior on their first engagement.
- Follow a methodical process: recon, then enumeration, then exploitation, then
  privilege escalation, then reporting. Load the matching playbook with
  load_playbook when you enter a phase.
- Record findings with save_note so the operator ends with a usable report.
- Never help with detection evasion for illegal use, mass targeting, or
  destructive actions. Keep the work educational and authorized.

Available playbooks: recon, web-owasp, priv-esc, reporting.
```

`pentai/skills/recon.md`:

```markdown
# Recon Playbook

Goal: map the attack surface before touching anything loud.

1. Host discovery: `nmap -sn <cidr>` to find live hosts.
2. Port and service scan: `nmap -sV -sC <target>` for versions and default scripts.
3. Full TCP sweep when time allows: `nmap -p- <target>`.
4. Web fingerprint: `whatweb <url>`, `curl -sI <url>`.
5. DNS and subdomains (authorized scope only): `dig`, `subfinder -d <domain>`.

Teach: explain why service versions matter (they map to known CVEs) and why you
start quiet before going loud.
```

`pentai/skills/web-owasp.md`:

```markdown
# Web / OWASP Playbook

Focus areas (OWASP Top 10) for authorized web targets like Juice Shop:

- Injection (SQLi): test inputs with `'`, observe errors; `sqlmap -u <url> --batch`.
- XSS: reflect `<script>alert(1)</script>` in parameters; check output encoding.
- Broken access control / IDOR: change object ids, replay another user's request.
- Auth: weak passwords, JWT `alg:none`, session fixation.
- Directory and content discovery: `gobuster dir -u <url> -w <wordlist>`.

Teach: describe the vulnerability class, the impact, and the remediation for each.
```

`pentai/skills/priv-esc.md`:

```markdown
# Privilege Escalation Playbook

After a foothold on an authorized host:

- Enumerate: `id`, `sudo -l`, `uname -a`, running services.
- Automated checks: `linpeas.sh` (Linux), `winPEAS` (Windows).
- SUID binaries: `find / -perm -4000 -type f 2>/dev/null`.
- Cron jobs and writable paths, kernel exploits matched to `uname -a`.

Teach: explain the difference between horizontal and vertical escalation and why
enumeration beats guessing.
```

`pentai/skills/reporting.md`:

```markdown
# Reporting Playbook

Turn findings into a report the owner can act on. For each finding record:

- Title and severity (CVSS-style: low / medium / high / critical).
- Affected asset and how it was found (steps to reproduce).
- Impact in plain language.
- Remediation.

Use save_note to append each finding as you confirm it, then summarize at the end.
```

`pyproject.toml` add (after the `packages.find` block):

```toml
[tool.setuptools.package-data]
pentai = ["skills/*.md", "prompts/*.md"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_content.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/prompts/system.md pentai/skills/*.md pyproject.toml tests/test_content.py
git commit -m "feat: system prompt and four methodology playbooks"
```

---

### Task 15: CLI wiring and REPL

**Files:**
- Create: `pentai/cli.py`
- Create: `pentai/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above — `load_config`, `default_config`, `build_provider`, `Agent`, `ToolSpec`, `Scope`, the three tools, `render`/`banner`/`theme`, `parse_slash`/`handle_slash`.
- Produces:
  - `build_agent(cfg: Config, scope: Scope, confirm: Callable[[str], bool], session_dir: Path) -> Agent` — wires provider + system prompt + the three `ToolSpec`s (run_command bound to scope+confirm, save_note bound to session_dir, load_playbook bound to skills dir).
  - `main(argv: list[str] | None = None) -> int` — parses `--no-fx`, prints banner, runs the REPL. Returns an exit code. REPL internals live behind small helpers so `build_agent` is unit-testable without a terminal.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from pathlib import Path
from pentai.config import Config, ProviderConfig
from pentai.scope import Scope
from pentai.cli import build_agent
from pentai.agent import Agent

def test_build_agent_wires_three_tools(tmp_path: Path):
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "claude-opus-4", "k")})
    agent = build_agent(cfg, Scope([]), confirm=lambda p: True, session_dir=tmp_path)
    assert isinstance(agent, Agent)
    assert set(agent.tools) == {"run_command", "save_note", "load_playbook"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pentai.cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/cli.py
import sys
from pathlib import Path
from typing import Callable
from prompt_toolkit import PromptSession
from rich.console import Console
from .config import Config, load_config, default_config
from .scope import Scope
from .providers.factory import build_provider
from .agent import Agent, ToolSpec, ToolInvocation
from .providers.base import TextDelta
from .tools.shell import run_command, RUN_COMMAND_TOOL
from .tools.notes import save_note, SAVE_NOTE_TOOL
from .tools.playbooks import load_playbook, LOAD_PLAYBOOK_TOOL
from .commands import parse_slash, handle_slash
from .ui.theme import get_palette
from .ui.banner import render_banner, boot_lines
from .ui.render import status_bar

_SKILLS_DIR = Path(__file__).parent / "skills"
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text()

def build_agent(cfg: Config, scope: Scope, confirm: Callable[[str], bool],
                session_dir: Path) -> Agent:
    provider = build_provider(cfg)
    tools = {
        "run_command": ToolSpec(
            RUN_COMMAND_TOOL,
            lambda args: run_command(args.get("command", ""), scope=scope, confirm=confirm)),
        "save_note": ToolSpec(
            SAVE_NOTE_TOOL,
            lambda args: save_note(args.get("text", ""), session_dir=session_dir)),
        "load_playbook": ToolSpec(
            LOAD_PLAYBOOK_TOOL,
            lambda args: load_playbook(args.get("name", ""), skills_dir=_SKILLS_DIR)),
    }
    return Agent(provider, _SYSTEM_PROMPT, tools)

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    fx = "--no-fx" not in argv
    console = Console()
    try:
        cfg = load_config()
    except Exception:
        cfg = default_config()
    palette = get_palette(cfg.palette)
    if fx:
        for line in boot_lines():
            console.print(line, style=palette["dim"])
    console.print(render_banner(palette, simple=not fx), style=palette["primary"])

    scope = Scope(cfg.scope)
    session_dir = Path.home() / ".pentai" / "session"
    cmds = 0

    def confirm(prompt: str) -> bool:
        return console.input(f"[{palette['accent']}]{prompt} [y/N] [/]").strip().lower() == "y"

    agent = build_agent(cfg, scope, confirm, session_dir)
    session: PromptSession = PromptSession()
    while True:
        console.print(status_bar(cfg.active, cfg.providers[cfg.active].model,
                                 len(scope.entries), cmds), style=palette["dim"])
        try:
            line = session.prompt("root@pentai:~# ")
        except (EOFError, KeyboardInterrupt):
            break
        slash = parse_slash(line)
        if slash is not None:
            result = handle_slash(*slash, scope=scope)
            if result == "__quit__":
                break
            console.print(result, style=palette["accent"])
            continue
        for ev in agent.send(line):
            if isinstance(ev, TextDelta):
                console.print(ev.text, style=palette["primary"], end="")
            elif isinstance(ev, ToolInvocation):
                cmds += 1
                console.print(f"\n[EXEC] {ev.arguments}\n{ev.result}", style=palette["accent"])
        console.print()
    console.print("bye", style=palette["dim"])
    return 0
```

```python
# pentai/__main__.py
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v`
Expected: PASS (all tests across all files)

- [ ] **Step 6: Commit**

```bash
git add pentai/cli.py pentai/__main__.py tests/test_cli.py
git commit -m "feat: CLI wiring and REPL"
```

---

### Task 16: README, license, and manual smoke check

**Files:**
- Create: `README.md`
- Create: `LICENSE` (MIT)
- Create: `pentai/config.example.yaml`

**Interfaces:**
- Consumes: nothing.
- Produces: user-facing docs, an MIT license, and an example config users copy to `~/.pentai/config.yaml`.

- [ ] **Step 1: Write README**

`README.md` must include: one-line description, an ethical-use notice (authorized targets only; the user is responsible for how they use it), `pip install -e .` install, `pentai` run instructions, provider setup (env vars `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, and `config.example.yaml` for Ollama/others), the `/scope`, `/help`, `/quit` commands, and `--no-fx`. Use plain hyphens and straight quotes only.

- [ ] **Step 2: Write LICENSE**

Standard MIT license text, copyright holder "PentAI contributors", year 2026.

- [ ] **Step 3: Write example config**

```yaml
# ~/.pentai/config.yaml  (copy from config.example.yaml)
active: anthropic
palette: green
fx: true
scope: []
providers:
  anthropic:
    kind: anthropic
    model: claude-opus-4
  openai:
    kind: openai_compat
    model: gpt-4o
    base_url: https://api.openai.com/v1
  ollama:
    kind: openai_compat
    model: llama3
    base_url: http://localhost:11434/v1
```

- [ ] **Step 4: Manual smoke check**

Run: `pentai --no-fx`
Expected: banner prints, `root@pentai:~#` prompt appears, `/help` lists commands, `/quit` exits. (No provider call needed to verify the shell.)

- [ ] **Step 5: Commit**

```bash
git add README.md LICENSE pentai/config.example.yaml
git commit -m "docs: README, MIT license, example config"
```

---

## Self-Review

**Spec coverage:**
- Agent-executes-with-confirmation: Tasks 8 (run_command), 10 (agent loop), 15 (confirm wiring). Covered.
- Python 3.11+ / pip / CLI `pentai`: Tasks 1, 15. Covered.
- Providers (Anthropic native + OpenAI-compatible covering Ollama/Groq/etc.): Tasks 5, 6, 7. OpenAI native is the compat adapter with the OpenAI base_url (DRY, noted). Covered.
- Playbooks + expert system prompt loaded per phase: Tasks 9 (load_playbook), 14 (content). Covered.
- Scope + confirmation + ethical banner: Tasks 3, 8, 11, 14. Covered.
- TUI aesthetic (boot, sigil, status bar, tags, fx flag): Tasks 11, 12, 15. Covered.
- save_note: Task 9. Covered.
- Testing with mocked LLM/HTTP/subprocess: injected `poster`/`runner`/`confirm` throughout. Covered.
- v2 items (slash workflows /recon, auto reports, MCP): intentionally excluded.

**Placeholder scan:** No TBD/TODO; all code steps contain real code. README/LICENSE (Task 16) are described by exact required contents rather than pre-written prose, which is appropriate for boilerplate.

**Type consistency:** `Message`, `ToolCall`, `Tool`, `TextDelta`, `ToolCallEvent`, `Done` defined in Task 4 and used unchanged in Tasks 5, 6, 10. `ToolSpec(tool, run)` and `ToolInvocation(name, arguments, result)` defined in Task 10 and consumed in Task 15. `Scope.out_of_scope`/`contains`/`add`/`entries` consistent across Tasks 3, 8, 13, 15. `build_provider`, `build_agent`, `run_command`, `save_note`, `load_playbook` signatures match between definition and call sites.
