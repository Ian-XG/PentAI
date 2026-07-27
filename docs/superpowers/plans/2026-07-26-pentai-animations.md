# PentAI Animations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add hacking-vibe animations: a "working..." spinner while the agent generates/executes (so the user sees it is busy), and a glitch reveal of the Hermes sigil at boot. All behind the existing `fx` flag (`--no-fx` disables).

**Architecture:** A new `pentai/ui/animations.py` holds two pure helpers: `run_once` (invoke a callback only once - used to stop the spinner exactly once before any console input/print) and `glitch_frames` (produce glitched variants of a string for the boot reveal). `cli.py` shows a `console.status` spinner per turn, stored in a holder so the confirm prompt and every render callback stop it before touching the console (avoiding a rich Live vs input/print conflict), and plays a transient glitch of the sigil at boot.

**Tech Stack:** Python 3.11+, rich (status/Live/Text), pytest.

## Global Constraints
- Python 3.11+ (`X | Y` unions allowed).
- Everything is gated behind `fx` (the existing `--no-fx` flag disables all animation).
- The spinner (rich Live) must be stopped before ANY `console.input` or `console.print` - never run two Live displays or a Live + input at once.
- No test may prompt interactively, run a real subprocess, hit the network, or sleep for a noticeable time.
- Plain hyphens and straight quotes only; no em dashes or smart quotes.

---

### Task 1: Animations helpers

**Files:**
- Create: `pentai/ui/animations.py`
- Test: `tests/test_animations.py`

**Interfaces:**
- Produces:
  - `run_once(fn: Callable[[], None]) -> Callable[[], None]` - returns a function that invokes `fn` only on its first call; later calls are no-ops.
  - `glitch_frames(text: str, frames: int = 6, rng=None) -> list[str]` - returns `frames` glitched variants of `text` (random non-space chars replaced with glitch chars) followed by the clean `text` as the final element. Deterministic when a `random.Random` is passed as `rng`. Every frame has the same length as `text`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_animations.py
import random
from pentai.ui.animations import run_once, glitch_frames

def test_run_once_invokes_only_first_time():
    calls = []
    once = run_once(lambda: calls.append(1))
    once(); once(); once()
    assert calls == [1]

def test_glitch_frames_shape_and_final():
    frames = glitch_frames("PENTAI", frames=3, rng=random.Random(0))
    assert len(frames) == 4                 # 3 glitched + 1 clean
    assert frames[-1] == "PENTAI"           # settles on the clean text
    assert all(len(f) == len("PENTAI") for f in frames)  # length preserved

def test_glitch_frames_preserves_whitespace_positions():
    text = "P E N"
    frames = glitch_frames(text, frames=4, rng=random.Random(1))
    for f in frames[:-1]:
        for i, ch in enumerate(text):
            if ch == " ":
                assert f[i] == " "          # spaces never corrupted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_animations.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/ui/animations.py
import random
from typing import Callable

_GLITCH_CHARS = "!@#$%&*/\\|<>=+-_?01"

def run_once(fn: Callable[[], None]) -> Callable[[], None]:
    state = {"done": False}
    def wrapper() -> None:
        if not state["done"]:
            state["done"] = True
            fn()
    return wrapper

def glitch_frames(text: str, frames: int = 6, rng=None) -> list[str]:
    rng = rng or random.Random()
    positions = [i for i, c in enumerate(text) if not c.isspace()]
    out: list[str] = []
    for _ in range(frames):
        chars = list(text)
        if positions:
            k = max(1, (len(positions) * 2) // 5)
            for i in rng.sample(positions, min(k, len(positions))):
                chars[i] = rng.choice(_GLITCH_CHARS)
        out.append("".join(chars))
    out.append(text)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_animations.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pentai/ui/animations.py tests/test_animations.py
git commit -m "feat: animation helpers (run_once, glitch_frames)"
```

---

### Task 2: Wire the spinner and boot glitch into the CLI

**Files:**
- Modify: `pentai/cli.py`
- Test: (no new unit test - interactive rendering; a non-interactive smoke run is the check)

**Interfaces:**
- Consumes: `run_once`, `glitch_frames` from `pentai.ui.animations`; `SIGIL` from `pentai.ui.banner`; `rich.live.Live`, `rich.text.Text`.
- Produces: a per-turn "working..." spinner (fx only) stopped before any input/print via a shared holder; a transient sigil glitch at boot (fx only). No behavior change when `--no-fx`.

- [ ] **Step 1: Add imports**

In `pentai/cli.py`, add:
```python
import time
from rich.live import Live
from rich.text import Text
from .ui.animations import run_once, glitch_frames
from .ui.banner import render_banner, boot_lines, SIGIL
```
(The existing `from .ui.banner import render_banner, boot_lines` line already exists - extend it to also import `SIGIL`.)

- [ ] **Step 2: Add the boot-glitch helper (module level)**

```python
def _play_sigil_glitch(console, palette) -> None:
    try:
        with Live(console=console, refresh_per_second=20, transient=True) as live:
            for frame in glitch_frames(SIGIL, frames=6):
                live.update(Text(frame, style=palette["accent"]))
                time.sleep(0.05)
    except Exception:
        pass
```

- [ ] **Step 3: Play the glitch at boot**

In `main()`, replace the boot/banner block:
```python
    if fx:
        for line in boot_lines():
            console.print(line, style=palette["dim"])
    console.print(render_banner(palette, simple=not fx), style=palette["primary"])
```
with:
```python
    if fx:
        for line in boot_lines():
            console.print(line, style=palette["dim"])
        _play_sigil_glitch(console, palette)
    console.print(render_banner(palette, simple=not fx), style=palette["primary"])
```

- [ ] **Step 4: Add the spinner holder and make confirm stop it**

In `main()`, right before the existing `def confirm(prompt: str) -> bool:` add:
```python
    spinner_stop: dict = {"fn": lambda: None}
```
Change `confirm` to stop the spinner before prompting:
```python
    def confirm(prompt: str) -> bool:
        spinner_stop["fn"]()
        return console.input(
            f"[{palette['accent']}]{escape(prompt)} [y/N] [/]"
        ).strip().lower() == "y"
```

- [ ] **Step 5: Show the per-turn spinner and stop it in every render path**

Replace the final render block (the `def render_text/render_tool/render_error` block and the `stream_turn(...)` call) with:
```python
        if fx:
            status = console.status("working...", spinner="dots")
            status.start()
            stop = run_once(status.stop)
        else:
            stop = run_once(lambda: None)
        spinner_stop["fn"] = stop

        def render_text(text):
            stop()
            console.print("AI", style=palette["accent"])
            console.print(Markdown(text))

        def render_tool(ev):
            nonlocal cmds
            stop()
            cmds += 1
            cmd = ev.arguments.get("command", ev.arguments)
            console.print(f"[EXEC] {cmd}", style=palette["accent"], markup=False)
            console.print(ev.result, style=palette["dim"], markup=False)

        def render_error(e):
            stop()
            console.print(f"\n[!] error: {e}", style=palette["alert"])

        stream_turn(agent.send(line), render_text, render_tool, render_error)
        stop()
        spinner_stop["fn"] = lambda: None
```
Why this is correct: the spinner is a rich Live; `stop()` (idempotent via `run_once`) runs before any `console.input` (in `confirm`) or `console.print` (in the render callbacks), so a Live display is never active at the same time as input or other output. In ASK mode the confirm prompt stops it; in AUTO/BYPASS it keeps spinning through command execution until the first render. For a pure-text answer, buffering in `stream_turn` means the spinner covers the whole generation and stops when the answer flushes.

- [ ] **Step 6: Verify - full suite + import + non-interactive smoke**

Run: `python3 -m pytest -q`
Expected: PASS (all existing tests; no new unit tests in this task).

Run: `python3 -c "import pentai.cli"`
Expected: no error.

Run (fx path, but piped so non-interactive - the glitch/spinner must not crash when stdout is not a TTY):
```bash
printf '/quit\n' | env HOME=$(mktemp -d) ANTHROPIC_API_KEY=sk-test python3 -m pentai
```
Expected: boot lines, banner, prompt, exits cleanly (the Live glitch degrades gracefully under a non-TTY; the `try/except` in `_play_sigil_glitch` guards it). Also run with `--no-fx` and confirm no animation path is taken:
```bash
printf '/quit\n' | env HOME=$(mktemp -d) ANTHROPIC_API_KEY=sk-test python3 -m pentai --no-fx
```
Paste both outputs in the report. If either crashes, fix before reporting DONE.

- [ ] **Step 7: Commit**

```bash
git add pentai/cli.py
git commit -m "feat: working spinner while the agent runs and a boot sigil glitch (fx-gated)"
```

---

### Task 3: Startup capabilities screen (Hermes-inspired two-column layout)

**Files:**
- Create: `pentai/ui/startup.py`
- Modify: `pentai/cli.py`
- Test: `tests/test_startup.py`

**Interfaces:**
- Consumes: `SIGIL` from `pentai.ui.banner`; `list_playbooks` from `pentai.tools.playbooks`; rich `Panel`/`Table`/`Text`.
- Produces:
  - `capability_rows(playbooks: list[str], tools: list[str], modes: list[str]) -> list[tuple[str, str]]` - pure: returns `[("playbooks", "a, b"), ("tools", "..."), ("modes", "...")]` (each value is a comma-joined list, "(none)" when empty).
  - `render_startup(console, *, palette, provider, model, playbooks, tools, modes, scope_count, session_id) -> None` - prints a bordered two-column panel: the sigil on the left, and on the right a "PentAI vX" header, the capability rows, and a `provider:model` / `scope` / `session` footer, all styled from the palette.
  - `cli.py` generates a `session_id` and calls `render_startup(...)` at boot in place of the plain banner (the fx glitch still flashes first).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_startup.py
from pentai.ui.startup import capability_rows, render_startup
from pentai.ui.theme import get_palette
from rich.console import Console

def test_capability_rows_shape():
    rows = capability_rows(["recon", "web-owasp"], ["run_command"], ["ask", "bypass"])
    assert rows[0] == ("playbooks", "recon, web-owasp")
    assert rows[1] == ("tools", "run_command")
    assert rows[2] == ("modes", "ask, bypass")

def test_capability_rows_empty_playbooks():
    rows = capability_rows([], ["run_command"], ["ask"])
    assert rows[0] == ("playbooks", "(none)")

def test_render_startup_outputs_key_fields():
    con = Console(record=True, width=100)
    render_startup(con, palette=get_palette("green"), provider="ollama-cloud",
                   model="gpt-oss:120b", playbooks=["recon"], tools=["run_command"],
                   modes=["ask", "auto", "bypass"], scope_count=1, session_id="20260726_x")
    out = con.export_text()
    assert "PentAI" in out
    assert "recon" in out
    assert "ollama-cloud" in out and "gpt-oss:120b" in out
    assert "20260726_x" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_startup.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/ui/startup.py
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from .banner import SIGIL

def capability_rows(playbooks: list[str], tools: list[str], modes: list[str]) -> list[tuple[str, str]]:
    def join(xs: list[str]) -> str:
        return ", ".join(xs) if xs else "(none)"
    return [("playbooks", join(playbooks)), ("tools", join(tools)), ("modes", join(modes))]

def render_startup(console, *, palette, provider, model, playbooks, tools, modes,
                   scope_count, session_id) -> None:
    accent = palette["accent"]
    dim = palette["dim"]
    primary = palette["primary"]
    body = Table.grid(padding=(0, 2))
    body.add_column()
    body.add_column()
    body.add_row(Text("PentAI", style=f"bold {accent}"), Text("v0.1.0", style=dim))
    body.add_row(Text("", style=dim), Text("", style=dim))
    for label, value in capability_rows(playbooks, tools, modes):
        body.add_row(Text(label, style=dim), Text(value, style=primary))
    body.add_row(Text("", style=dim), Text("", style=dim))
    body.add_row(Text("provider", style=dim), Text(f"{provider}:{model}", style=accent))
    body.add_row(Text("scope", style=dim), Text(str(scope_count), style=primary))
    body.add_row(Text("session", style=dim), Text(session_id, style=dim))
    layout = Table.grid(padding=(0, 3))
    layout.add_column()
    layout.add_column()
    layout.add_row(Text(SIGIL, style=accent), body)
    console.print(Panel(layout, border_style=accent,
                        title="[ authorized use only ]", title_align="left"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_startup.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Wire into the CLI**

In `pentai/cli.py`:
- Add imports:
```python
from .ui.startup import render_startup
from .tools.playbooks import load_playbook, LOAD_PLAYBOOK_TOOL, list_playbooks
```
(The `load_playbook, LOAD_PLAYBOOK_TOOL` import already exists - extend it to also import `list_playbooks`.)
- Generate a session id near the top of `main()` (after `console = Console()`):
```python
    session_id = time.strftime("%Y%m%d_%H%M%S")
```
- Replace the banner line
```python
    console.print(render_banner(palette, simple=not fx), style=palette["primary"])
```
with the startup screen (the fx glitch above it stays):
```python
    render_startup(console, palette=palette, provider=cfg.active,
                   model=cfg.providers[cfg.active].model,
                   playbooks=list_playbooks(_SKILLS_DIR),
                   tools=["run_command", "save_note", "load_playbook"],
                   modes=MODES, scope_count=len(cfg.scope), session_id=session_id)
```
(`time` is imported in Task 2; `MODES` and `_SKILLS_DIR` are already available in cli.py.)

- [ ] **Step 6: Verify - full suite + import + smoke**

Run: `python3 -m pytest -q` (PASS), `python3 -c "import pentai.cli"` (no error), and:
```bash
printf '/quit\n' | env HOME=$(mktemp -d) ANTHROPIC_API_KEY=sk-test python3 -m pentai --no-fx
```
Expected: the bordered startup panel with the sigil, the playbooks/tools/modes listing, the provider:model and session footer, then the prompt, exits cleanly. Paste the output in the report.

- [ ] **Step 7: Commit**

```bash
git add pentai/ui/startup.py pentai/cli.py tests/test_startup.py
git commit -m "feat: Hermes-inspired startup screen (sigil + capabilities panel + session footer)"
```

---

## Self-Review
- Startup capabilities screen (two-column sigil + categorized playbooks/tools/modes + provider/scope/session footer): Task 3. Covered.
- Spinner shows while busy, stops before any input/print (no Live conflict): Task 2, Steps 4-5. Covered.
- Boot glitch reveal of the sigil, fx-gated, guarded against non-TTY crash: Task 2, Steps 2-3. Covered.
- Pure helpers unit-tested; interactive parts covered by a non-interactive smoke run: Tasks 1, 2. Covered.
- `--no-fx` takes no animation path (spinner is a no-op run_once, glitch skipped): Task 2. Covered.
- Types: `run_once`/`glitch_frames` signatures consistent between Task 1 definition and Task 2 use. Covered.
