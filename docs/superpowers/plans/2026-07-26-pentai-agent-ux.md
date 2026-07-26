# PentAI Agent UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make PentAI feel like Claude Code for ethical hacking: permission modes (Ask/Auto/Bypass) cyclable with shift+tab, a chat-style TUI with Markdown-rendered responses, and a masked key prompt in the wizard.

**Architecture:** A new `pentai/permissions.py` holds the mode list and the confirm-decision. `run_command` gains a `mode` parameter that decides when to prompt. `status_bar` shows the mode. `cli.py` holds a mutable mode holder, cycles it via a prompt_toolkit shift+tab key binding shown in a live bottom toolbar and via a `/mode` command, and renders AI responses as Markdown with clear framing. The wizard masks the key prompt.

**Tech Stack:** Python 3.11+, rich (Markdown), prompt_toolkit (key bindings + bottom_toolbar), pytest.

## Global Constraints
- Python 3.11+ (`X | Y` unions allowed).
- Modes: exactly `["ask", "auto", "bypass"]`, cycled in that order. ASK confirms every command; AUTO auto-runs in-scope commands but confirms out-of-scope; BYPASS runs everything with no prompt.
- Backward compatible: `run_command(..., mode="ask")` must behave exactly as before (existing tests unchanged and passing).
- No test may prompt interactively, spawn a real subprocess, or make a network call (inject confirm/runner).
- Plain hyphens and straight quotes only; no em dashes or smart quotes.

---

### Task 1: Permissions module

**Files:**
- Create: `pentai/permissions.py`
- Test: `tests/test_permissions.py`

**Interfaces:**
- Produces:
  - `MODES: list[str]` = `["ask", "auto", "bypass"]`.
  - `next_mode(mode: str) -> str` (cycles; unknown -> first).
  - `should_prompt_exec(mode: str) -> bool` (True only for "ask").
  - `should_prompt_oos(mode: str) -> bool` (True unless "bypass").

- [ ] **Step 1: Write the failing test**

```python
# tests/test_permissions.py
from pentai.permissions import MODES, next_mode, should_prompt_exec, should_prompt_oos

def test_modes_order():
    assert MODES == ["ask", "auto", "bypass"]

def test_next_mode_cycles():
    assert next_mode("ask") == "auto"
    assert next_mode("auto") == "bypass"
    assert next_mode("bypass") == "ask"
    assert next_mode("nonsense") == "ask"

def test_should_prompt_exec():
    assert should_prompt_exec("ask") is True
    assert should_prompt_exec("auto") is False
    assert should_prompt_exec("bypass") is False

def test_should_prompt_oos():
    assert should_prompt_oos("ask") is True
    assert should_prompt_oos("auto") is True
    assert should_prompt_oos("bypass") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_permissions.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/permissions.py
MODES: list[str] = ["ask", "auto", "bypass"]

def next_mode(mode: str) -> str:
    if mode not in MODES:
        return MODES[0]
    return MODES[(MODES.index(mode) + 1) % len(MODES)]

def should_prompt_exec(mode: str) -> bool:
    return mode == "ask"

def should_prompt_oos(mode: str) -> bool:
    return mode != "bypass"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_permissions.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/permissions.py tests/test_permissions.py
git commit -m "feat: permission modes (ask/auto/bypass)"
```

---

### Task 2: Mode-aware run_command and status bar

**Files:**
- Modify: `pentai/tools/shell.py`
- Modify: `pentai/ui/render.py`
- Test: `tests/test_shell.py`, `tests/test_ui_render.py`

**Interfaces:**
- Consumes: `should_prompt_exec`, `should_prompt_oos` from `pentai.permissions`.
- Produces:
  - `run_command(command, *, scope, confirm, mode: str = "ask", runner=None) -> str` — out-of-scope prompts unless bypass; per-command prompt only when mode == "ask"; otherwise runs.
  - `status_bar(provider, model, scope_count, cmds, mode: str = "ask") -> str` includes `mode:<MODE>`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_shell.py`:
```python
def test_auto_runs_in_scope_without_confirm():
    calls = []
    def confirm(p):
        calls.append(p)
        return True
    r = run_command("nmap 10.0.0.5", scope=Scope(["10.0.0.0/24"]),
                    confirm=confirm, mode="auto", runner=lambda c: CommandResult("ok", "", 0))
    assert "ok" in r
    assert calls == []  # no prompt in auto for in-scope

def test_auto_still_confirms_out_of_scope():
    seen = []
    r = run_command("nmap 1.2.3.4", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda p: seen.append(p) or False, mode="auto",
                    runner=lambda c: CommandResult("x", "", 0))
    assert seen and "cancelled" in r.lower()

def test_bypass_runs_everything_without_confirm():
    calls = []
    r = run_command("nmap 1.2.3.4", scope=Scope(["10.0.0.0/24"]),
                    confirm=lambda p: calls.append(p) or True, mode="bypass",
                    runner=lambda c: CommandResult("done", "", 0))
    assert "done" in r
    assert calls == []  # bypass never prompts, even out of scope
```

Append to `tests/test_ui_render.py`:
```python
def test_status_bar_includes_mode():
    s = status_bar("anthropic", "claude-opus-4", 2, 5, "bypass")
    assert "mode:BYPASS" in s
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_shell.py tests/test_ui_render.py -v`
Expected: FAIL (run_command has no mode kwarg / status_bar has no mode)

- [ ] **Step 3: Implement**

In `pentai/tools/shell.py`, add the import and rewrite `run_command`:
```python
from ..permissions import should_prompt_exec, should_prompt_oos
```
```python
def run_command(command: str, *, scope: Scope, confirm: Callable[[str], bool],
                mode: str = "ask", runner: Callable[[str], CommandResult] | None = None) -> str:
    runner = runner or _subprocess_runner
    oos = scope.out_of_scope(command)
    if oos and should_prompt_oos(mode):
        if not confirm(f"OUT OF SCOPE: {', '.join(oos)}. You confirm you are authorized?"):
            return "[cancelled: target out of authorized scope]"
    if should_prompt_exec(mode):
        if not confirm(f"execute: {command}"):
            return "[cancelled by user]"
    result = runner(command)
    return f"exit_code={result.exit_code}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
```
(Keep `CommandResult`, `_subprocess_runner`, and `RUN_COMMAND_TOOL` unchanged.)

In `pentai/ui/render.py`, update `status_bar`:
```python
def status_bar(provider: str, model: str, scope_count: int, cmds: int, mode: str = "ask") -> str:
    return f"-[ {provider}:{model} ]-[ scope:{scope_count} ]-[ mode:{mode.upper()} ]-[ cmds:{cmds} ]-"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_shell.py tests/test_ui_render.py -v`
Expected: PASS (existing + new)

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pentai/tools/shell.py pentai/ui/render.py tests/test_shell.py tests/test_ui_render.py
git commit -m "feat: mode-aware run_command and mode in status bar"
```

---

### Task 3: Mask the key prompt in the wizard

**Files:**
- Modify: `pentai/onboarding.py`
- Modify: `pentai/cli.py`
- Test: `tests/test_onboarding.py`

**Interfaces:**
- Produces:
  - `run_wizard(prompt_fn, print_fn, secret_fn: Callable[[str], str] | None = None) -> dict` — uses `secret_fn` for the API key prompt when provided, else falls back to `prompt_fn` (so existing tests keep working). `cli.py` passes a masked `secret_fn` (`console.input(p, password=True)`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_onboarding.py`:
```python
def test_run_wizard_uses_secret_fn_for_key():
    prompts = iter(["1", ""])   # choose anthropic, default model
    secrets = []
    cfg = run_wizard(lambda p: next(prompts),
                     lambda m: None,
                     secret_fn=lambda p: secrets.append(p) or "sk-secret")
    assert cfg["providers"]["anthropic"]["api_key"] == "sk-secret"
    assert secrets and "ANTHROPIC_API_KEY" in secrets[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_onboarding.py::test_run_wizard_uses_secret_fn_for_key -v`
Expected: FAIL (run_wizard has no secret_fn)

- [ ] **Step 3: Implement**

In `pentai/onboarding.py`, change `run_wizard` signature and the key prompt:
```python
def run_wizard(prompt_fn: Callable[[str], str], print_fn: Callable[[str], None],
               secret_fn: Callable[[str], str] | None = None) -> dict:
```
Replace the key-prompt line so it uses `secret_fn` when available:
```python
    api_key = None
    if choice.needs_key:
        ask_key = secret_fn or prompt_fn
        api_key = ask_key(f"Paste your {choice.api_key_env}: ").strip() or None
```
(Everything else in `run_wizard` unchanged.)

In `pentai/cli.py`, both `run_wizard(...)` call sites (first-run block and `__setup__` handler) pass a masked secret_fn:
```python
        wiz = run_wizard(lambda p: console.input(p, markup=False),
                         lambda m: console.print(m, style=palette["accent"]),
                         secret_fn=lambda p: console.input(p, markup=False, password=True))
```
(For the first-run block, keep its existing print lambda; just add the `secret_fn=` kwarg. Palette may not exist yet in the first-run block — if so use `console.print(m)` for print_fn as before and still pass the password secret_fn.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_onboarding.py -v`
Expected: PASS (existing + new); existing wizard tests still pass because secret_fn defaults to None and falls back to prompt_fn.

- [ ] **Step 5: Commit**

```bash
git add pentai/onboarding.py pentai/cli.py tests/test_onboarding.py
git commit -m "feat: mask API key input in the setup wizard"
```

---

### Task 4: CLI chat UX - mode toggle (shift+tab + /mode), live toolbar, themed Markdown rendering

**Files:**
- Modify: `pentai/cli.py`
- Modify: `pentai/ui/render.py`
- Test: `tests/test_cli.py`, `tests/test_ui_render.py`

**Interfaces:**
- Consumes: `MODES`, `next_mode` from `pentai.permissions`; `rich.markdown.Markdown`; `rich.theme.Theme`; prompt_toolkit `KeyBindings`.
- Produces:
  - `apply_mode_command(current: str, args: list[str]) -> str` (in cli.py) - pure helper: with no args cycles to the next mode; with `args[0]` in MODES sets it; otherwise returns current unchanged.
  - `markdown_theme(palette: dict[str, str]) -> Theme` (in ui/render.py) - a rich Theme mapping markdown elements (headings, list bullets/numbers, table header/border, hr, code) to the phosphor palette so rendered responses and tables adopt the hacker look.
  - main() uses `apply_mode_command` for `/mode`, holds the mode in a mutable holder cycled by a shift+tab key binding shown in a bottom toolbar, threads the mode into run_command, pushes `markdown_theme(palette)` onto the console, and renders assistant text as themed Markdown (so `#`/`*`/tables/lists/rules become styled headers, bold, boxed tables, numbered lists, and divider lines) with an AI header and clear EXEC blocks.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:
```python
def test_apply_mode_command_cycles_and_sets():
    from pentai.cli import apply_mode_command
    assert apply_mode_command("ask", []) == "auto"      # cycle
    assert apply_mode_command("ask", ["bypass"]) == "bypass"  # set
    assert apply_mode_command("ask", ["nonsense"]) == "ask"   # invalid -> unchanged
```

Append to `tests/test_ui_render.py`:
```python
def test_markdown_theme_has_markdown_styles():
    from pentai.ui.render import markdown_theme
    from pentai.ui.theme import get_palette
    theme = markdown_theme(get_palette("green"))
    for key in ("markdown.h1", "markdown.item.number", "markdown.table.header"):
        assert key in theme.styles
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py::test_apply_mode_command_cycles_and_sets tests/test_ui_render.py::test_markdown_theme_has_markdown_styles -v`
Expected: FAIL (no apply_mode_command / no markdown_theme)

- [ ] **Step 3: Implement**

In `pentai/ui/render.py`, add the themed-markdown helper:
```python
from rich.theme import Theme

def markdown_theme(palette: dict[str, str]) -> Theme:
    accent = palette["accent"]
    dim = palette["dim"]
    return Theme({
        "markdown.h1": f"bold {accent}",
        "markdown.h2": f"bold {accent}",
        "markdown.h3": accent,
        "markdown.h4": accent,
        "markdown.item.number": accent,
        "markdown.item.bullet": accent,
        "markdown.table.header": f"bold {accent}",
        "markdown.hr": dim,
        "markdown.code": accent,
        "markdown.link": accent,
    })
```

In `pentai/cli.py`:

Add imports:
```python
from prompt_toolkit.key_binding import KeyBindings
from rich.markdown import Markdown
from .permissions import MODES, next_mode
from .ui.render import markdown_theme
```
(The file already imports `status_bar` from `.ui.render`; extend that import or add this line.)

After `palette = get_palette(cfg.palette)` in `main()`, theme the console so Markdown adopts the palette:
```python
    console.push_theme(markdown_theme(palette))
```

Add the pure helper (module level):
```python
def apply_mode_command(current: str, args: list[str]) -> str:
    if not args:
        return next_mode(current)
    if args[0] in MODES:
        return args[0]
    return current
```

In `main()`, after `scope = Scope(cfg.scope)` and before the REPL loop:
```python
    mode_ref = {"mode": "ask"}

    kb = KeyBindings()

    @kb.add("s-tab")
    def _(event):
        mode_ref["mode"] = next_mode(mode_ref["mode"])
        event.app.invalidate()

    def bottom_toolbar():
        return (f" mode: {mode_ref['mode'].upper()}  (shift+tab to cycle)"
                f"   scope: {len(scope.entries)}   cmds: {cmds}")

    session = PromptSession(key_bindings=kb, bottom_toolbar=bottom_toolbar)
```
(Replace the existing bare `session = PromptSession()` with the above.)

Thread the mode into the run_command ToolSpec. Because the agent's tools are built once, `build_agent` must read the current mode at call time. Change the `run_command` ToolSpec lambda in `build_agent` to accept a mode getter. Update `build_agent`'s signature to `build_agent(cfg, scope, confirm, session_dir, mode_getter=lambda: "ask")` and the run_command binding to:
```python
        "run_command": ToolSpec(
            RUN_COMMAND_TOOL,
            lambda args: run_command(args.get("command", ""), scope=scope,
                                     confirm=confirm, mode=mode_getter())),
```
and in `main()` build the agent with `build_agent(cfg, scope, confirm, session_dir, lambda: mode_ref["mode"])`. (The existing test `test_build_agent_wires_three_tools` calls `build_agent(cfg, Scope([]), confirm=..., session_dir=...)` - keep `mode_getter` defaulted so that test still passes.)

Handle `/mode` in the slash dispatch (before the generic result print), and include mode in the printed status bar:
```python
        if slash is not None and slash[0] == "mode":
            mode_ref["mode"] = apply_mode_command(mode_ref["mode"], slash[1])
            console.print(f"[ mode: {mode_ref['mode'].upper()} ]", style=palette["accent"])
            continue
```
Update the printed status bar call to pass the mode:
```python
        console.print(status_bar(cfg.active, cfg.providers[cfg.active].model,
                                 len(scope.entries), cmds, mode_ref["mode"]),
                      style=palette["dim"])
```

Render AI responses as Markdown with framing and clear EXEC blocks. Replace the agent.send rendering block with:
```python
        buf: list[str] = []
        def flush_ai():
            if buf:
                console.print("AI", style=palette["accent"])
                console.print(Markdown("".join(buf)))
                buf.clear()
        try:
            for ev in agent.send(line):
                if isinstance(ev, TextDelta):
                    buf.append(ev.text)
                elif isinstance(ev, ToolInvocation):
                    flush_ai()
                    cmds += 1
                    cmd = ev.arguments.get("command", ev.arguments)
                    console.print(f"[EXEC] {cmd}", style=palette["accent"], markup=False)
                    console.print(ev.result, style=palette["dim"], markup=False)
            flush_ai()
        except Exception as e:
            console.print(f"\n[!] error: {e}", style=palette["alert"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py tests/test_ui_render.py -v`
Expected: PASS (existing + new). Then confirm imports resolve: `python3 -c "import pentai.cli"`.

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pentai/cli.py pentai/ui/render.py tests/test_cli.py tests/test_ui_render.py
git commit -m "feat: chat-style TUI - mode toggle (shift+tab and /mode), live toolbar, themed Markdown rendering"
```

---

## Self-Review
- Modes ask/auto/bypass, cycled in order: Task 1. Covered.
- run_command respects mode (ask confirms, auto runs in-scope + confirms oos, bypass runs all): Task 2. Covered and backward compatible (mode default "ask").
- Mode in status bar + live toolbar + shift+tab + /mode: Tasks 2, 4. Covered.
- Key masking in wizard: Task 3. secret_fn defaults to None so existing wizard tests unaffected.
- Chat feel (Markdown render + AI header + EXEC blocks): Task 4. Covered.
- build_agent gains mode_getter with a default so the existing wiring test still passes; run_command mode kwarg defaults to "ask". Type consistency preserved.
