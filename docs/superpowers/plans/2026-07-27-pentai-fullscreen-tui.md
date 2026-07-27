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

### Task 3: Agent worker + queued messages + confirm + ESC-stop

**Files:**
- Create: `pentai/ui/runner.py`
- Modify: `pentai/ui/app.py`
- Test: `tests/test_runner.py`

**Outline:**
- A `TurnRunner` that, given an `Agent` and render callbacks, runs `agent.send(text)` in a background executor, marshals each rendered event back to the UI thread (via the app's event loop `call_soon_threadsafe` / `run_in_terminal`), and supports a cooperative stop flag checked between events. While a turn runs, submitted input is `TurnQueue.enqueue`d; on completion the next queued message is dispatched.
- Confirm (ASK mode): the worker's `confirm(prompt)` posts a request to the UI (a yes/no line in the input/status) and blocks on a threading.Event until the user answers; AUTO/BYPASS never prompt.
- Unit-test the parts that can be isolated: the queue-drain logic (enqueue during "busy", drain on "idle"), and the stop flag halting iteration of a scripted event generator. The threading/prompt_toolkit marshaling is verified by smoke.

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
