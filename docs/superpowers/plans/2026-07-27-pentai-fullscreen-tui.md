# PentAI Full-Screen TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A Codex/Claude-Code-style full-screen TUI: a scrollable output region on top, a bordered input box fixed at the bottom, queued messages while the agent works, ESC to stop a turn, and no resize artifacts. Keep the classic line REPL available under `pentai --classic` until the new UI is solid.

**Architecture:** A prompt_toolkit `Application` owns the screen. rich renderables (Markdown, panels, exec blocks) are captured to ANSI strings and appended to a scrolling output buffer. The agent turn runs in a background worker (asyncio task / executor) so the bordered input stays live for queuing; ESC cancels the current turn; shift+tab cycles the mode. Confirmations (ASK mode) are surfaced in the UI. All the existing pieces (onboarding, config, scope, modes, toolcheck, playbooks, agent) are reused unchanged; only the front-end loop changes.

**Tech Stack:** Python 3.11+, prompt_toolkit 3.0.x, rich, pytest.

## Global Constraints
- Python 3.11+ (`X | Y` unions allowed).
- Do NOT modify or break the classic REPL (`main`); the new UI is additive and selected by default, with `--classic` falling back to the current loop. All existing tests keep passing.
- Pure pieces are unit-tested; the interactive Application is verified by construction/import and non-interactive smoke (feeding piped input), never by a real TTY test.
- Plain hyphens and straight quotes only; no em dashes or smart quotes (box-drawing glyphs in the UI are intentional assets).

---

### Task 1: TUI core - ANSI capture + turn queue (pure, testable)

**Files:**
- Create: `pentai/ui/tui_core.py`
- Test: `tests/test_tui_core.py`

**Interfaces:**
- Produces:
  - `render_to_ansi(renderable, width: int = 100) -> str` - renders a rich renderable (str, Text, Markdown, Panel, ...) to an ANSI-escaped string via a StringIO Console (force_terminal, truecolor). Used to push rich content into the prompt_toolkit output buffer.
  - `class TurnQueue` - FIFO of pending user messages: `enqueue(msg)` (ignores blank), `pop() -> str | None`, `__len__`, `pending -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tui_core.py
from rich.markdown import Markdown
from pentai.ui.tui_core import render_to_ansi, TurnQueue

def test_render_to_ansi_plain_text():
    out = render_to_ansi("hello world")
    assert "hello world" in out

def test_render_to_ansi_markdown():
    out = render_to_ansi(Markdown("# Title\n\n- item one"))
    assert "Title" in out and "item one" in out

def test_turn_queue_fifo_and_blank():
    q = TurnQueue()
    q.enqueue("first"); q.enqueue("   "); q.enqueue("second")
    assert len(q) == 2
    assert q.pending == ["first", "second"]
    assert q.pop() == "first"
    assert q.pop() == "second"
    assert q.pop() is None
    assert len(q) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_tui_core.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/ui/tui_core.py
from io import StringIO
from rich.console import Console

def render_to_ansi(renderable, width: int = 100) -> str:
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor",
                      width=width, soft_wrap=False)
    console.print(renderable)
    return buf.getvalue()

class TurnQueue:
    def __init__(self) -> None:
        self._items: list[str] = []

    def enqueue(self, msg: str) -> None:
        if msg.strip():
            self._items.append(msg)

    def pop(self) -> str | None:
        return self._items.pop(0) if self._items else None

    def __len__(self) -> int:
        return len(self._items)

    @property
    def pending(self) -> list[str]:
        return list(self._items)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_tui_core.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add pentai/ui/tui_core.py tests/test_tui_core.py
git commit -m "feat: TUI core - rich-to-ANSI capture and turn queue"
```

---

### Task 2: The full-screen app shell (layout + key bindings), headless-tested

**Files:**
- Create: `pentai/ui/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces:
  - `class OutputBuffer` - holds accumulated ANSI text: `append(ansi: str)`, `text() -> str`, `clear()`.
  - `build_app(*, output: OutputBuffer, on_submit: Callable[[str], None], on_stop: Callable[[], None], on_cycle_mode: Callable[[], None], get_status: Callable[[], str], pt_input=None, pt_output=None) -> Application` - a full-screen prompt_toolkit Application: a scrollable output `Window` showing `ANSI(output.text())`, a bordered input `Frame(TextArea(prompt="> ", multiline=False))` whose accept-handler calls `on_submit(text)` then clears the input, and a one-line status `Window` from `get_status()`. Key bindings: Enter submits (via the TextArea accept-handler); `s-tab` -> `on_cycle_mode()` + invalidate; `escape` (eager) -> `on_stop()`; `c-c`/`c-d` -> exit. `pt_input`/`pt_output` are passed to `Application(input=, output=)` for headless testing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app.py
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from pentai.ui.app import build_app, OutputBuffer

def test_output_buffer_accumulates():
    b = OutputBuffer()
    b.append("a"); b.append("b")
    assert b.text() == "ab"
    b.clear()
    assert b.text() == ""

def test_app_submit_then_exit_headless():
    submitted = []
    out = OutputBuffer()
    with create_pipe_input() as inp:
        app = build_app(output=out,
                        on_submit=lambda t: submitted.append(t),
                        on_stop=lambda: None,
                        on_cycle_mode=lambda: None,
                        get_status=lambda: "mode:ASK",
                        pt_input=inp, pt_output=DummyOutput())
        inp.send_text("hello there\r")  # type + Enter -> submit
        inp.send_text("\x03")           # Ctrl-C -> exit
        app.run()
    assert submitted == ["hello there"]

def test_app_cycle_mode_key_headless():
    cycles = []
    with create_pipe_input() as inp:
        app = build_app(output=OutputBuffer(),
                        on_submit=lambda t: None,
                        on_stop=lambda: None,
                        on_cycle_mode=lambda: cycles.append(1),
                        get_status=lambda: "s",
                        pt_input=inp, pt_output=DummyOutput())
        inp.send_text("\x1b[Z")  # shift-tab
        inp.send_text("\x03")    # Ctrl-C -> exit
        app.run()
    assert cycles == [1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_app.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Implement `pentai/ui/app.py`**

```python
from typing import Callable
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import Frame, TextArea


class OutputBuffer:
    def __init__(self) -> None:
        self._text = ""

    def append(self, ansi: str) -> None:
        self._text += ansi

    def text(self) -> str:
        return self._text

    def clear(self) -> None:
        self._text = ""


def build_app(*, output: OutputBuffer,
              on_submit: Callable[[str], None],
              on_stop: Callable[[], None],
              on_cycle_mode: Callable[[], None],
              get_status: Callable[[], str],
              pt_input=None, pt_output=None) -> Application:

    def accept(buff: Buffer) -> bool:
        text = buff.text
        on_submit(text)
        return False  # clear the input after submit

    input_area = TextArea(prompt="> ", multiline=False, accept_handler=accept)
    input_frame = Frame(input_area, title="message")

    output_window = Window(
        content=FormattedTextControl(lambda: ANSI(output.text()), focusable=False),
        wrap_lines=True,
    )
    status_window = Window(
        content=FormattedTextControl(lambda: get_status()),
        height=1,
    )

    root = HSplit([output_window, input_frame, status_window])

    kb = KeyBindings()

    @kb.add("c-c")
    @kb.add("c-d")
    def _(event) -> None:
        event.app.exit()

    @kb.add("s-tab")
    def _(event) -> None:
        on_cycle_mode()
        event.app.invalidate()

    @kb.add("escape", eager=True)
    def _(event) -> None:
        on_stop()

    return Application(
        layout=Layout(root, focused_element=input_area),
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
        input=pt_input,
        output=pt_output,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_app.py -v` then full `python3 -m pytest -q`.
Expected: PASS. If a prompt_toolkit API detail differs in 3.0.52 (e.g. accept_handler return semantics, shift-tab escape sequence, or Application input/output kwargs), adjust minimally to make the headless tests pass - the tests are the contract. Also `python3 -c "import pentai.ui.app"`.

- [ ] **Step 5: Commit**

```bash
git add pentai/ui/app.py tests/test_app.py
git commit -m "feat: full-screen app shell (bordered input, output region, key bindings)"
```

---

### Task 3: Turn controller state machine (queue + stop + confirm routing)

**Files:**
- Create: `pentai/ui/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Produces `class TurnController(start_turn: Callable[[str], None])` - a synchronous, testable state machine (the actual background execution is injected via `start_turn`, wired in Task 4):
  - `submit(text)`: strip; ignore blank; if a confirm is awaiting, interpret this input as the yes/no answer and deliver it; else if busy, enqueue; else begin a turn (`start_turn(text)`, sets `busy=True`).
  - `finish()`: mark idle; if the queue has a next message, begin it.
  - `stop()`: set the cooperative `stopped` flag (only while busy).
  - `request_confirm(on_answer)`: register a callback that the next `submit` answers (y/yes -> True).
  - properties: `busy`, `stopped`, `awaiting_confirm`, `queue` (a TurnQueue).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner.py
from pentai.ui.runner import TurnController

def test_submit_idle_begins_turn():
    started = []
    c = TurnController(start_turn=started.append)
    c.submit("scan 10.0.0.5")
    assert started == ["scan 10.0.0.5"] and c.busy is True

def test_submit_while_busy_enqueues():
    started = []
    c = TurnController(start_turn=started.append)
    c.submit("first")
    c.submit("second")
    assert started == ["first"]            # second not started yet
    assert c.queue.pending == ["second"]

def test_finish_drains_next():
    started = []
    c = TurnController(start_turn=started.append)
    c.submit("first"); c.submit("second")
    c.finish()
    assert started == ["first", "second"]  # finish began the queued one
    assert c.busy is True

def test_finish_when_empty_goes_idle():
    c = TurnController(start_turn=lambda t: None)
    c.submit("only"); c.finish()
    assert c.busy is False and c.queue.pending == []

def test_confirm_routing():
    answers = []
    c = TurnController(start_turn=lambda t: None)
    c.submit("scan")                       # busy now
    c.request_confirm(answers.append)
    assert c.awaiting_confirm is True
    c.submit("yes")                        # this is the answer, not a new turn/queue item
    assert answers == [True]
    assert c.awaiting_confirm is False
    assert c.queue.pending == []           # not enqueued

def test_confirm_no_variant():
    answers = []
    c = TurnController(start_turn=lambda t: None)
    c.submit("scan"); c.request_confirm(answers.append)
    c.submit("n")
    assert answers == [False]

def test_stop_only_when_busy():
    c = TurnController(start_turn=lambda t: None)
    c.stop()
    assert c.stopped is False
    c.submit("scan")
    c.stop()
    assert c.stopped is True

def test_blank_submit_ignored():
    started = []
    c = TurnController(start_turn=started.append)
    c.submit("   ")
    assert started == [] and c.busy is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_runner.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write minimal implementation**

```python
# pentai/ui/runner.py
from typing import Callable, Optional
from .tui_core import TurnQueue

class TurnController:
    def __init__(self, start_turn: Callable[[str], None]) -> None:
        self._start_turn = start_turn
        self.queue = TurnQueue()
        self.busy = False
        self.stopped = False
        self._awaiting_confirm: Optional[Callable[[bool], None]] = None

    @property
    def awaiting_confirm(self) -> bool:
        return self._awaiting_confirm is not None

    def submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self._awaiting_confirm is not None:
            cb, self._awaiting_confirm = self._awaiting_confirm, None
            cb(text.lower() in ("y", "yes"))
            return
        if self.busy:
            self.queue.enqueue(text)
            return
        self._begin(text)

    def _begin(self, text: str) -> None:
        self.busy = True
        self.stopped = False
        self._start_turn(text)

    def finish(self) -> None:
        self.busy = False
        nxt = self.queue.pop()
        if nxt is not None:
            self._begin(nxt)

    def stop(self) -> None:
        if self.busy:
            self.stopped = True

    def request_confirm(self, on_answer: Callable[[bool], None]) -> None:
        self._awaiting_confirm = on_answer
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_runner.py -v` then full `python3 -m pytest -q`.
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add pentai/ui/runner.py tests/test_runner.py
git commit -m "feat: turn controller state machine (queue, stop, confirm routing)"
```

---

### Task 4: Wire the full-screen app into the CLI (--tui opt-in; classic stays default)

**Files:**
- Modify: `pentai/cli.py`
- Test: `tests/test_cli.py`

**Interfaces / behavior:**
- Rename the current `main()` body to `main_classic(argv=None) -> int` (UNCHANGED behavior).
- New `main(argv=None) -> int`: `argv = sys.argv[1:] if argv is None else argv`; if `"--tui"` in argv -> `return main_tui(argv)`; else `return main_classic(argv)`. So the DEFAULT `pentai` stays the classic REPL; `pentai --tui` opts into the full-screen app.
- `main_tui(argv) -> int`: builds the full-screen app reusing the existing setup (onboarding via needs_onboarding/run_wizard/save_config; load_config_file/default_config; get_palette; Scope(cfg.scope); check_tools; build_agent with mode_getter + context_provider). It wires:
  - `mode_ref = {"mode": "ask"}`, `cmds = counter`.
  - `output = OutputBuffer()`; seed it with the startup panel + toolcheck rendered via `render_to_ansi(...)`.
  - `controller = TurnController(start_turn=_start_turn)`.
  - `app = build_app(output=output, on_submit=_on_submit, on_stop=controller.stop, on_cycle_mode=_cycle, get_status=_status)`.
  - `_on_submit(text)`: if `text` starts with "/", handle it as a slash command (parse_slash/handle_slash): `/quit` -> `app.exit()`; `/mode` -> cycle/set via apply_mode_command; `__setup__`/`__clear__`/`__notes__`/`__report__`/`__tools__`/`__playbooks__` and `/scope` -> perform the action and append the rendered result to `output`; then `app.invalidate()`. Otherwise -> `controller.submit(text)`.
  - `_start_turn(text)`: run `agent.send(text)` in a background thread (`threading.Thread`). For each event, marshal a UI update onto the app event loop with `app.loop.call_soon_threadsafe(...)`: append `render_to_ansi(...)` of the AI markdown / EXEC block to `output` and `app.invalidate()`. Stop iterating if `controller.stopped`. On completion, marshal `controller.finish()`.
  - confirm (passed into build_agent's run_command): in ASK mode it must block the worker thread until the user answers in the box. Implement with a `threading.Event`: append a "[confirm] <prompt> [y/N]" line to output, `controller.request_confirm(cb)` (marshaled onto the loop), then `event.wait()`; the user's next `_on_submit` is routed by the controller as the yes/no answer, which sets the result and the event. AUTO/BYPASS never call confirm (run_command gates it).
  - `_status()`: `f" mode:{mode_ref['mode'].upper()}  scope:{len(scope.entries)}  cmds:{cmds}  queued:{len(controller.queue)}  (shift+tab mode, esc stop, /quit)"`.
  - Guard the whole `app.run()` so a non-TTY raises cleanly (catch the prompt_toolkit no-tty error and print a one-line hint to use `--classic`).

- [ ] **Step 1: Write the failing test (append to tests/test_cli.py)**

```python
def test_main_defaults_to_classic(monkeypatch):
    import pentai.cli as cli
    calls = {}
    monkeypatch.setattr(cli, "main_classic", lambda argv=None: calls.setdefault("classic", argv) or 0)
    monkeypatch.setattr(cli, "main_tui", lambda argv: calls.setdefault("tui", argv) or 0)
    cli.main([])
    assert "classic" in calls and "tui" not in calls

def test_main_tui_flag_dispatches_to_tui(monkeypatch):
    import pentai.cli as cli
    calls = {}
    monkeypatch.setattr(cli, "main_classic", lambda argv=None: calls.setdefault("classic", argv) or 0)
    monkeypatch.setattr(cli, "main_tui", lambda argv: calls.setdefault("tui", argv) or 0)
    cli.main(["--tui"])
    assert "tui" in calls and "classic" not in calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: FAIL (no main_tui / main dispatch).

- [ ] **Step 3: Implement** the rename + `main` dispatcher + `main_tui` per the behavior above. Keep `main_classic` byte-for-byte the current `main` body. Reuse existing imports and helpers; add `import threading`, and `from .ui.app import build_app, OutputBuffer`, `from .ui.runner import TurnController`, `from .ui.tui_core import render_to_ansi`.

- [ ] **Step 4: Verify - tests + import + smoke**

Run: `python3 -m pytest -q` (all pass, incl. the 2 new dispatch tests) and `python3 -c "import pentai.cli"`.
Smoke (both must exit cleanly, no traceback):
```bash
printf '/quit\n' | env HOME=$(mktemp -d) ANTHROPIC_API_KEY=sk-test python3 -m pentai --tui
printf '/quit\n' | env HOME=$(mktemp -d) ANTHROPIC_API_KEY=sk-test python3 -m pentai
```
The `--tui` run under a pipe is non-TTY: it is acceptable for it to either run the app and exit on `/quit`, OR print a clean one-line "no TTY, use --classic" message - but it MUST NOT dump a traceback. The default run must still be the classic REPL. Paste both outputs. If the `--tui` non-TTY path dumps a traceback, wrap `app.run()` to catch it and print the hint.

- [ ] **Step 5: Commit**

```bash
git add pentai/cli.py tests/test_cli.py
git commit -m "feat: full-screen TUI wired behind --tui (background turns, queue, confirm); classic stays default"
```

Note for the controller: real agent-turn / confirm / queue behavior over a live provider cannot be validated headlessly - after this task the human runs `pentai --tui` to validate the interactive feel before the default is flipped.

---

### Task 4: Wire the app into the CLI with a --classic fallback

**Files:**
- Modify: `pentai/cli.py`
- Modify: `pentai/__main__.py` (if needed)
- Test: `tests/test_cli.py`

**Outline:**
- Keep the current `main()` loop as `main_classic()`. Add `main(argv)` that parses `--classic` (-> `main_classic`) else launches the full-screen app, reusing onboarding/config/scope/modes/toolcheck/build_agent exactly as today.
- The console-script entry stays `pentai.cli:main`.
- Smoke: `printf '/quit\n' | pentai` starts the app and exits cleanly (prompt_toolkit degrades under non-TTY - guard so it does not crash); `pentai --classic` still runs the old loop. Paste both.

---

## Self-Review
- Codex-style bordered input + scrollable output + queued messages + ESC-stop: Tasks 2 + 3.
- rich content preserved via ANSI capture: Task 1 + 2.
- Resize artifacts eliminated (full-screen owns the screen): inherent to Task 2's Application.
- Classic REPL preserved under --classic; existing tests untouched: Task 4.
- Pure pieces unit-tested (Task 1, queue/stop logic in 3); interactive app verified by construction + smoke.
- NOTE: Tasks 2-4 outlines will be finalized with concrete prompt_toolkit 3.0.52 code as each task is dispatched (the controller iterates the app against smoke runs); Task 1 is fully specified now.
