# PentAI — Design Spec

Date: 2026-07-25
Status: Approved (design), pending implementation plan

## Purpose

PentAI is a terminal-based AI chatbot that acts as an **ethical pentester and teacher**. You prompt it in natural language; it proposes hacking commands, executes them in your shell after confirmation, analyzes the output, and guides you through pentesting methodology. It is BYOK (bring your own API key), multi-provider, and ships with editable ethical-hacking playbooks.

Primary audience: learners of offensive security practicing on authorized targets (Juice Shop, home labs, CTFs). Open source and dual-use; ethical use is left to the user's discretion, stated explicitly in the README and startup banner.

## Core decisions (from brainstorming)

- **Agent model:** Agent executes commands with per-command confirmation (Claude Code style, pentest-oriented). Not advisory-only.
- **Stack:** Python 3.11+. Chosen for ecosystem fit with security tooling and `pip install` distribution.
- **TUI:** `prompt_toolkit` (input) + `rich` (rendering). Cyberpunk / "hacker program" aesthetic (see Aesthetic section).
- **Providers (BYOK):** Anthropic (native SDK), OpenAI (native SDK), and a generic OpenAI-compatible adapter (base_url + key) covering Ollama local/remote, Groq, OpenRouter, DeepSeek, LM Studio, etc.
- **Hacking knowledge:** Expert system prompt + editable markdown **playbooks** loaded per phase.
- **Safety:** Scope + confirmation (balanced). Authorized-target scope, warn+confirm on out-of-scope, per-command confirmation, ethical banner.

## Architecture

```
Terminal (REPL + TUI: prompt_toolkit + rich)
        |  natural-language prompt
        v
   Agent loop  --->  LLM provider (Anthropic | OpenAI | OpenAI-compatible)
        ^              |  returns text or a tool call
        |              v
   tool result   +- Tool: run_command  -> scope check -> confirm [y/N] -> execute in shell
   fed back    --+- Tool: save_note    -> write findings/report to markdown
   to LLM        +- Tool: load_playbook -> load the skill for the current phase
```

Loop: user text -> LLM -> if it requests a command, validate against scope, ask confirmation, execute, feed stdout/stderr back to the LLM, which reasons and continues. Everything streams to the TUI.

## Components (isolated, testable)

- **`config.py`** — loads `~/.pentai/config.yaml` + env vars. Providers, keys, default model, feature flags (`fx`).
- **`providers/`**
  - `base.py` — common interface `chat(messages, tools) -> stream of events (text deltas, tool calls)`.
  - `anthropic.py`, `openai.py` — native SDK adapters.
  - `openai_compat.py` — generic base_url + key adapter (Ollama remote/local, Groq, OpenRouter, etc.).
  - `factory.py` — selects adapter from config.
- **`agent.py`** — agentic loop: builds messages, injects system prompt + loaded playbooks, dispatches tool calls, manages streaming and conversation state.
- **`scope.py`** — holds authorized targets (IPs, CIDRs, domains/globs); extracts targets from a command string (heuristic regex for IPs/hostnames/URLs); returns in-scope / out-of-scope so the agent can warn+confirm.
- **`tools/shell.py`** — `run_command`: confirmation prompt, scope check, subprocess execution, capture stdout/stderr/exit code. Supports "yes to all for this session".
- **`tools/notes.py`** — `save_note`: append findings / write a markdown report under the session dir.
- **`tools/playbooks.py`** — `load_playbook(name)`: reads `skills/<name>.md` into context.
- **`skills/*.md`** — playbooks: `recon.md`, `web-owasp.md`, `priv-esc.md`, `reporting.md`.
- **`prompts/system.md`** — expert "ethical pentester who teaches" system prompt, including safety framing and an index of available playbooks.
- **`ui/`** — `banner.py` (sigil + wordmark + boot sequence), `theme.py` (color palettes), `render.py` (rich rendering of `[AI]`/`[EXEC]`/`[!] VULN` tags, streaming, status bar).
- **`cli.py` / `__main__.py`** — entry point: boot sequence, banner, scope init, REPL, slash-command dispatch (`/scope`, `/provider`, `/model`, `/help`, `/quit`).

## Data flow (one turn)

1. User types a prompt in the REPL.
2. `agent.py` appends it to history, sends history + system prompt + loaded playbooks + tool defs to the active provider.
3. Provider streams back text and/or tool calls.
4. For `run_command`: `scope.py` checks targets -> if out of scope, warn + require explicit confirmation; then per-command `[y/N]` confirm (unless "yes to all"); then `tools/shell.py` executes and captures output.
5. Tool result is appended to history and sent back to the provider.
6. Loop until the provider returns a final text answer; render it.

## Safety model

- Ethical-use banner on startup (authorized targets only).
- Scope defined at start or via `/scope add <target>`; out-of-scope commands trigger a warning + explicit confirmation.
- Per-command `[y/N]` confirmation before execution, with an opt-in "yes to all for this session".
- No detection-evasion or destructive defaults; educational framing (Juice Shop, labs, CTF).
- Session transcript optionally saved for auditing.

## Aesthetic (TUI)

Cyberpunk "hacker program" look, phosphor green on black (configurable palettes: green / amber / red), all effects behind a `--no-fx` flag / config.

- **Boot sequence:** fast-scrolling `[ OK ] ...` init lines before the prompt appears.
- **Sigil (approved):** Hermes winged mark, rendered on a strict monospace grid, axis aligned over the wordmark's center:

```
                  ◈
        ╲╲╲╲     ╱│╲     ╱╱╱╱
      ╲╲╲╲╲╲    ╱ │ ╲    ╱╱╱╱╱╱
    ▚▚▚▚▚▚▚▚   ╱  │  ╲   ▞▞▞▞▞▞▞▞
  ◄═══════════════│═══════════════►
                 ╲│╱
                  │
                  ▼
      P   E   N   T   A   I
```

  A "simple" ASCII fallback sigil is provided for terminals with narrow font support. The mark is verified by real terminal render during implementation.
- **Prompt:** monospace `root@pentai:~#`.
- **Status bar:** active provider/model, loaded scope count, commands executed, e.g. `-[ anthropic:claude-opus-4 ]-[ scope:1 ]-[ cmds:0 ]-`.
- **Output tags:** `[AI]` for reasoning, `[EXEC]` for commands, `[!] VULN` for findings; optional typing effect and banner glitch.

## Repo structure

```
pentai/
  pentai/
    __init__.py  __main__.py  cli.py  agent.py  config.py  scope.py
    providers/{base,anthropic,openai,openai_compat,factory}.py
    tools/{shell,notes,playbooks}.py
    ui/{banner,theme,render}.py
    skills/{recon,web-owasp,priv-esc,reporting}.md
    prompts/system.md
  tests/
  pyproject.toml
  README.md
  LICENSE
  docs/superpowers/specs/2026-07-25-pentai-design.md
```

## Testing strategy

Unit tests with the **LLM mocked** (no real API calls):

- `scope.py`: target extraction from commands, in/out-of-scope matching (IPs, CIDRs, domain globs).
- `config.py`: config + env var loading, provider selection.
- `providers/*`: message/tool formatting per adapter (HTTP mocked); streaming event parsing.
- `tools/shell.py`: command execution and capture (subprocess mocked), confirmation gating, "yes to all".
- `tools/playbooks.py`: playbook loading and missing-file handling.

## Scope

**v1 (MVP):** providers (Anthropic + OpenAI + OpenAI-compatible), agent loop, `run_command` with scope + confirmation, `save_note`, `load_playbook`, 4 playbooks, config, TUI with sigil/banner/boot/status bar, README with ethical-use notice and `pip install`.

**v2 (deferred, out of scope for now):** slash-command workflows (`/recon`, `/enum-web`), automated report generation, additional playbooks, MCP integration.

## Name

**PentAI.** Repo name `pentai`, CLI command `pentai`.
