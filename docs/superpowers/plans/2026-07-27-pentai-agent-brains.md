# PentAI Agent Brains Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make PentAI act like a real ethical-hacking agent that runs commands and teaches while doing (not one that pastes commands for the user to copy), knows its live scope/mode so it stops re-asking, and handles the common failure paths (a "yes" confirmation, a provider network error, empty input) gracefully.

**Architecture:** A rewritten action-bias system prompt (`prompts/system.md`). The `Agent` gains a per-turn `context_provider` whose output (current scope, mode, cwd) is appended to the system message each turn so the model always sees the authorized scope. `cli.py` fixes the confirm parser (accept y/yes), maps provider connection errors to a clear message, skips empty input, and drops the repeated per-turn status bar (the live bottom toolbar already shows that state).

**Tech Stack:** Python 3.11+, existing rich/prompt_toolkit/httpx, pytest.

## Global Constraints
- Python 3.11+ (`X | Y` unions allowed).
- Do not print a tool call as text - the agent must CALL tools. This is enforced via the system prompt, and verified by content assertions only (the model's behavior itself is not unit-tested).
- Backward compatible: `Agent(..., context_provider=None)` defaults so existing agent tests pass.
- No test may prompt interactively, run a real subprocess, or hit the network.
- Plain hyphens and straight quotes only; no em dashes or smart quotes.

---

### Task 1: Action-bias, self-aware system prompt

**Files:**
- Modify: `pentai/prompts/system.md`
- Test: `tests/test_content.py`

**Interfaces:**
- Produces: a rewritten `system.md` that (a) tells the agent to CALL tools rather than print them, (b) bias to action - on a target/tool/goal, load the playbook then run a concrete first command, (c) states it is told scope+mode each turn and must guide `/scope add` instead of re-asking, (d) teach concisely while doing.

- [ ] **Step 1: Write the failing test (extend tests/test_content.py)**

```python
def test_system_prompt_is_action_biased():
    from pathlib import Path
    import pentai
    text = (Path(pentai.__file__).parent / "prompts" / "system.md").read_text().lower()
    # must push tool use over describing
    assert "call" in text and "tool" in text
    assert "do not print" in text or "never print" in text
    # must know it receives scope/mode context and guide /scope add
    assert "/scope add" in text
    assert "mode" in text
    # still ethical
    assert "authorized" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_content.py -v`
Expected: FAIL (current system.md lacks these).

- [ ] **Step 3: Rewrite `pentai/prompts/system.md` to exactly:**

```markdown
You are PentAI, an autonomous ethical-hacking agent with a real terminal. You DO the work: you run commands yourself and teach while doing. You never hand the user a command to copy - you run it.

# Act, do not describe
- You have tools. USE them by CALLING them. Never print a tool call as text (do not write things like load_playbook{name:"recon"} or paste an nmap command for the user to run) - call the tool.
- When the user names a target, a tool (for example "nmap"), or a goal: load the relevant playbook if useful, then immediately call run_command with a concrete first command. One or two sentences of what and why, then run it, then explain the real output.
- A good turn is: brief intent, then run_command, then interpret the actual result, then the next step. Not a wall of text, not a tutorial the user has to execute.
- Be concise. Lead with the action, not an essay.

# Your tools (call these; do not just describe them)
- run_command(command): runs a shell command on the operator's machine. This is how you scan, enumerate, and exploit.
- save_note(text): record each finding (open port, version, vuln, credential) - this builds the report.
- load_playbook(name): load a methodology playbook (recon, web-owasp, priv-esc, reporting).

# Scope and permission (you are told these every turn)
- Each turn you receive a session-context block with the current authorized scope, the permission mode, and the working directory. Read it.
- If the target the user wants is not in the authorized scope, do not silently refuse and do not re-ask every message. Tell them one line: add it to scope with /scope add <target> - then proceed once it is there.
- Modes: ask (the operator confirms each command), auto (in-scope commands run automatically), bypass (everything runs). Adapt: in ask you propose and run on approval; in auto and bypass you just run.

# Method
recon, then enumeration, then exploitation, then privilege escalation, then reporting. Load the matching playbook when you enter a phase, and save_note every finding so the operator ends with a report.

# Teach while doing
Explain what a command does and what its output means, like mentoring a junior on their first engagement - woven into the action in a line or two, not a lecture before you act.

# Rules of engagement
Operate only against authorized targets (the scope you are given). If something is out of scope, say so. Never help with detection evasion for illegal use, mass targeting, or destructive actions. Keep the work educational and authorized.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_content.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pentai/prompts/system.md tests/test_content.py
git commit -m "feat: action-bias, self-aware system prompt (call tools, run and teach)"
```

---

### Task 2: Live per-turn context injection (scope, mode, cwd)

**Files:**
- Modify: `pentai/agent.py`
- Modify: `pentai/cli.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: provider `chat(messages, tools, system)`.
- Produces:
  - `Agent.__init__(..., context_provider: Callable[[], str] | None = None)` - when set, its return value is appended to the system prompt on EACH `send()` so the model sees fresh scope/mode/cwd.
  - `session_context(scope_entries: list[str], mode: str, cwd: str) -> str` (in cli.py) - the pure text block; cli passes `context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd())` into build_agent (build_agent gains a `context_provider` passthrough with a `None` default).

- [ ] **Step 1: Write the failing test (extend tests/test_agent.py)**

```python
def test_send_appends_context_to_system():
    from pentai.providers.base import Message, TextDelta, Done
    from pentai.agent import Agent
    class CapturingProvider:
        def __init__(self): self.system = None
        def chat(self, messages, tools, system=""):
            self.system = system
            yield TextDelta("ok"); yield Done("end")
    prov = CapturingProvider()
    agent = Agent(prov, "BASE PROMPT", {}, context_provider=lambda: "SCOPE: 10.0.0.0/24")
    list(agent.send("hi"))
    assert "BASE PROMPT" in prov.system
    assert "SCOPE: 10.0.0.0/24" in prov.system
```

(Also confirm the existing `test_send_passes_system_prompt` still passes: with no context_provider, system == base prompt.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent.py -v`
Expected: FAIL (Agent has no context_provider).

- [ ] **Step 3: Implement**

In `pentai/agent.py`, update `Agent.__init__` and `send`:
```python
    def __init__(self, provider: Provider, system_prompt: str,
                 tools: dict[str, ToolSpec], history: list[Message] | None = None,
                 context_provider: Callable[[], str] | None = None):
        self.provider = provider
        self.system_prompt = system_prompt
        self.tools = tools
        self.history: list[Message] = history if history is not None else []
        self._tool_defs: list[Tool] = [s.tool for s in tools.values()]
        self.context_provider = context_provider
```
In `send`, compute the system per turn and pass it to the provider (replace the existing `self.provider.chat(self.history, self._tool_defs, self.system_prompt)` call):
```python
        system = self.system_prompt
        if self.context_provider is not None:
            system = f"{system}\n\n{self.context_provider()}"
        # ... use `system` in the provider.chat(...) call inside the loop
```
(If `send` calls `provider.chat` inside a `while` loop, compute `system` once before the loop and pass it on each call.)

In `pentai/cli.py`:
- add `import os` if not present.
- add the pure helper (module level):
```python
def session_context(scope_entries: list[str], mode: str, cwd: str) -> str:
    scope = ", ".join(scope_entries) if scope_entries else "(empty - tell the user to run /scope add <target>)"
    return (f"--- session context ---\n"
            f"authorized scope: {scope}\n"
            f"permission mode: {mode}\n"
            f"working directory: {cwd}")
```
- change `build_agent` to accept and pass a `context_provider` (default None), forwarding it into `Agent(...)`.
- in `main()`, build the agent with a live context provider:
```python
    agent = build_agent(cfg, scope, confirm, session_dir, mode_getter,
                        context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd()))
```
and do the same at the `/setup` rebuild site.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_agent.py tests/test_cli.py -q` then the full suite `python3 -m pytest -q`.
Expected: PASS. Also `python3 -c "import pentai.cli"`.

- [ ] **Step 5: Commit**

```bash
git add pentai/agent.py pentai/cli.py tests/test_agent.py
git commit -m "feat: inject live scope/mode/cwd context into the agent each turn"
```

---

### Task 3: CLI fixes - accept y/yes, friendly network errors, skip empty input, drop repeated status bar

**Files:**
- Modify: `pentai/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `friendly_error(e: Exception) -> str` (in cli.py) - maps connection/DNS/timeout errors to a clear "cannot reach the AI provider ..." message and auth errors to a "check your API key with /setup" message; otherwise returns `f"error: {e}"`.
  - `confirm` accepts `y` or `yes` (case-insensitive).
  - The REPL skips empty input (no send, no reprint), and no longer prints the `-[ ... ]-` status bar every turn (the live bottom toolbar shows mode/scope/cmds).

- [ ] **Step 1: Write the failing test (extend tests/test_cli.py)**

```python
def test_friendly_error_connection():
    import socket
    from pentai.cli import friendly_error
    msg = friendly_error(socket.gaierror(8, "nodename nor servname provided, or not known"))
    assert "provider" in msg.lower()
    assert "8" not in msg or "provider" in msg.lower()  # not a raw errno dump

def test_friendly_error_auth():
    from pentai.cli import friendly_error
    assert "api key" in friendly_error(Exception("HTTP 401 Unauthorized")).lower()

def test_friendly_error_generic():
    from pentai.cli import friendly_error
    assert "boom" in friendly_error(Exception("boom"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: FAIL (no friendly_error).

- [ ] **Step 3: Implement in `pentai/cli.py`**

Add imports and the helper:
```python
import socket
import httpx

def friendly_error(e: Exception) -> str:
    conn_types = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, socket.gaierror)
    msg = str(e)
    if isinstance(e, conn_types) or "nodename nor servname" in msg or "Name or service not known" in msg or "Temporary failure in name resolution" in msg:
        return ("cannot reach the AI provider (network / DNS). Check your internet connection, "
                "the provider base_url, and your API key with /setup.")
    if "401" in msg or "403" in msg or "unauthorized" in msg.lower() or "invalid api key" in msg.lower():
        return "the AI provider rejected the request (auth). Check your API key with /setup."
    return f"error: {msg}"
```
Use it in `render_error`:
```python
        def render_error(e):
            stop()
            console.print(f"\n[!] {friendly_error(e)}", style=palette["alert"])
```
Make `confirm` accept y/yes:
```python
    def confirm(prompt: str) -> bool:
        spinner_stop["fn"]()
        return console.input(
            f"[{palette['accent']}]{escape(prompt)} [y/N] [/]"
        ).strip().lower() in ("y", "yes")
```
Skip empty input and drop the per-turn status bar: at the top of the `while True:` loop, REMOVE the `console.print(status_bar(...))` block (the bottom toolbar already shows mode/scope/cmds live). After reading `line`, add:
```python
        if not line.strip():
            continue
```
(Place this right after the `try: line = session.prompt(...) except (EOFError, KeyboardInterrupt): break` block, before `parse_slash`.)

- [ ] **Step 4: Run tests + smoke**

Run: `python3 -m pytest -q` (PASS) and `python3 -c "import pentai.cli"`.
Run both smoke checks:
```bash
printf '\n\n/quit\n' | env HOME=$(mktemp -d) ANTHROPIC_API_KEY=sk-test python3 -m pentai --no-fx
```
Expected: empty lines are ignored (no error, no agent call), banner shows once, clean exit. Paste output in the report.

- [ ] **Step 5: Commit**

```bash
git add pentai/cli.py tests/test_cli.py
git commit -m "fix: accept y/yes, friendly provider-network errors, skip empty input, drop repeated status bar"
```

---

## Self-Review
- Agent acts (calls tools) and teaches concisely: Task 1 (prompt). Behavior depends on the model; prompt asserts the guidance is present.
- Agent knows live scope/mode/cwd and stops re-asking / guides /scope add: Tasks 1 + 2. Covered.
- "yes" authorizes; network errors are legible; empty input ignored; status-bar noise removed: Task 3. Covered.
- Backward compatible: context_provider defaults None; confirm/friendly_error additive. Existing tests pass.
