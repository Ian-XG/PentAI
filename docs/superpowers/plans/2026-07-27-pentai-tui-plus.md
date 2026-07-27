# PentAI TUI Plus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Round out the TUI: a Shannon-style tool-availability check at startup (and tell the agent which tools are actually installed), more slash commands (/clear, /notes, /report, /tools, /playbooks), and a responsive startup screen that adapts to narrow terminals.

**Architecture:** A new `pentai/toolcheck.py` detects installed pentest tools via `shutil.which`. `cli.py` renders the availability line at boot and feeds the installed list into the per-turn agent context. `commands.py` gains sentinels for the new slash commands, handled in `cli.py`. `ui/startup.py`'s `render_startup` stacks vertically when the console is narrow.

**Tech Stack:** Python 3.11+, rich, existing modules, pytest.

## Global Constraints
- Python 3.11+ (`X | Y` unions allowed).
- Injected dependencies for testability: `check_tools(..., which=...)` takes an injectable `which`; no test may run a real subprocess, hit the network, or prompt.
- Plain hyphens and straight quotes only; no em dashes or smart quotes. (The check mark glyphs in the availability display are the one intentional non-ASCII, like the sigil art.)

---

### Task 1: Tool-availability check (Shannon-style) + feed installed tools to the agent

**Files:**
- Create: `pentai/toolcheck.py`
- Modify: `pentai/ui/startup.py` (add `render_toolcheck`)
- Modify: `pentai/cli.py` (render at boot; add installed tools to `session_context`)
- Test: `tests/test_toolcheck.py`, `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `COMMON_TOOLS: list[str]` - a curated pentest toolset to probe.
  - `check_tools(names: list[str] | None = None, which: Callable[[str], str | None] | None = None) -> list[tuple[str, bool]]` - returns `(name, available)` for each name (defaults to COMMON_TOOLS), using `which` (defaults to `shutil.which`).
  - `render_toolcheck(console, palette, results: list[tuple[str, bool]]) -> None` (in ui/startup.py) - prints a compact wrapped line: available tools in the accent style with a check, missing in the dim style with a cross.
  - `session_context(scope_entries, mode, cwd, tools: list[str] | None = None) -> str` gains an optional installed-tools line (appended only when `tools` is given).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_toolcheck.py
from pentai.toolcheck import COMMON_TOOLS, check_tools

def test_common_tools_includes_nmap():
    assert "nmap" in COMMON_TOOLS

def test_check_tools_uses_injected_which():
    present = {"nmap", "curl"}
    which = lambda name: "/usr/bin/" + name if name in present else None
    results = check_tools(["nmap", "sqlmap", "curl"], which=which)
    assert results == [("nmap", True), ("sqlmap", False), ("curl", True)]

def test_check_tools_defaults_to_common_tools():
    results = check_tools(which=lambda n: None)
    assert [n for n, _ in results] == COMMON_TOOLS
    assert all(avail is False for _, avail in results)
```

Append to `tests/test_cli.py`:
```python
def test_session_context_includes_installed_tools():
    from pentai.cli import session_context
    ctx = session_context(["10.0.0.0/24"], "ask", "/home/x", tools=["nmap", "curl"])
    assert "nmap, curl" in ctx
    assert "10.0.0.0/24" in ctx and "ask" in ctx

def test_session_context_without_tools_omits_line():
    from pentai.cli import session_context
    ctx = session_context([], "ask", "/home/x")
    assert "installed tools" not in ctx.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_toolcheck.py tests/test_cli.py -v`
Expected: FAIL (no toolcheck module; session_context has no tools param).

- [ ] **Step 3: Implement**

```python
# pentai/toolcheck.py
import shutil
from typing import Callable

COMMON_TOOLS: list[str] = [
    "nmap", "masscan", "rustscan", "gobuster", "ffuf", "dirsearch", "nikto",
    "sqlmap", "hydra", "whatweb", "wpscan", "dig", "whois", "curl", "nc",
    "subfinder", "john", "hashcat", "netcat", "enum4linux",
]

def check_tools(names: list[str] | None = None,
                which: Callable[[str], str | None] | None = None) -> list[tuple[str, bool]]:
    names = COMMON_TOOLS if names is None else names
    which = shutil.which if which is None else which
    return [(name, which(name) is not None) for name in names]
```

In `pentai/ui/startup.py`, add:
```python
def render_toolcheck(console, palette, results) -> None:
    accent = palette["accent"]
    dim = palette["dim"]
    parts = []
    for name, available in results:
        mark = "✓" if available else "✗"
        style = accent if available else dim
        parts.append(f"[{style}]{mark} {name}[/]")
    console.print("tools  " + "  ".join(parts), style=dim)
```

In `pentai/cli.py`:
- import: `from .toolcheck import check_tools` and `from .ui.startup import render_startup, render_toolcheck`.
- extend `session_context` to accept `tools`:
```python
def session_context(scope_entries: list[str], mode: str, cwd: str,
                    tools: list[str] | None = None) -> str:
    scope = ", ".join(scope_entries) if scope_entries else "(empty - tell the user to run /scope add <target>)"
    lines = [f"--- session context ---",
             f"authorized scope: {scope}",
             f"permission mode: {mode}",
             f"working directory: {cwd}"]
    if tools:
        lines.append(f"installed tools: {', '.join(tools)}")
    return "\n".join(lines)
```
- in `main()`, after the `render_startup(...)` call, compute and render tool availability, and remember the installed list:
```python
    _tool_results = check_tools()
    render_toolcheck(console, palette, _tool_results)
    installed_tools = [name for name, ok in _tool_results if ok]
```
- update BOTH `context_provider` lambdas (initial build and /setup rebuild) to pass the installed tools:
```python
    context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd(), installed_tools)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_toolcheck.py tests/test_cli.py -v` then full `python3 -m pytest -q`.
Expected: PASS. Also `python3 -c "import pentai.cli"`.

- [ ] **Step 5: Commit**

```bash
git add pentai/toolcheck.py pentai/ui/startup.py pentai/cli.py tests/test_toolcheck.py tests/test_cli.py
git commit -m "feat: startup tool-availability check and feed installed tools to the agent"
```

---

### Task 2: More slash commands (/clear, /notes, /report, /tools, /playbooks)

**Files:**
- Modify: `pentai/commands.py`
- Modify: `pentai/cli.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Produces: `handle_slash` returns sentinels `__clear__`, `__notes__`, `__report__`, `__tools__`, `__playbooks__` for the new commands; `_HELP` lists them. `cli.py` acts on each sentinel (clear screen; show notes; render report from notes; list tools + availability; list playbooks or show one named in args).

- [ ] **Step 1: Write the failing test (append to tests/test_commands.py)**

```python
def test_new_command_sentinels():
    from pentai.scope import Scope
    from pentai.commands import handle_slash
    s = Scope([])
    assert handle_slash("clear", [], scope=s) == "__clear__"
    assert handle_slash("notes", [], scope=s) == "__notes__"
    assert handle_slash("report", [], scope=s) == "__report__"
    assert handle_slash("tools", [], scope=s) == "__tools__"
    assert handle_slash("playbooks", [], scope=s) == "__playbooks__"

def test_help_lists_new_commands():
    from pentai.scope import Scope
    from pentai.commands import handle_slash
    h = handle_slash("help", [], scope=Scope([]))
    for c in ("/clear", "/notes", "/report", "/tools", "/playbooks"):
        assert c in h
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `pentai/commands.py`, update `_HELP` and add the sentinels (place the new branches before the `help` branch):
```python
_HELP = ("commands: /scope add <target>, /scope list, /setup, /mode [ask|auto|bypass], "
         "/clear, /notes, /report, /tools, /playbooks [name], /help, /quit")
```
```python
    if command in ("clear", "notes", "report", "tools", "playbooks"):
        return "__" + command + "__"
```

In `pentai/cli.py`, in the slash-command handling block (where `__setup__` is already handled), add handlers for the new sentinels (before the generic `console.print(result, ...)`), using state already in `main()` (`console`, `palette`, `session_dir`, `_SKILLS_DIR`, `AGENT_TOOL_NAMES`, `_tool_results` from Task 1, `list_playbooks`, `load_playbook`, `Markdown`):
```python
            if result == "__clear__":
                console.clear()
                continue
            if result == "__notes__":
                notes = session_dir / "notes.md"
                if notes.exists():
                    console.print(Markdown(notes.read_text()))
                else:
                    console.print("[no notes yet]", style=palette["dim"])
                continue
            if result == "__report__":
                notes = session_dir / "notes.md"
                if notes.exists():
                    console.print(Markdown("# PentAI Session Report\n\n" + notes.read_text()))
                else:
                    console.print("[no findings recorded yet - the agent saves them with save_note]",
                                  style=palette["dim"])
                continue
            if result == "__tools__":
                render_toolcheck(console, palette, _tool_results)
                console.print("agent tools: " + ", ".join(AGENT_TOOL_NAMES), style=palette["dim"])
                continue
            if result == "__playbooks__":
                names = list_playbooks(_SKILLS_DIR)
                if slash[1]:
                    name = slash[1][0]
                    console.print(Markdown(load_playbook(name, skills_dir=_SKILLS_DIR)))
                else:
                    console.print("playbooks: " + ", ".join(names), style=palette["accent"])
                continue
```
(`slash` is the `(command, args)` tuple from `parse_slash`; `slash[1]` is the args list. `list_playbooks` and `load_playbook` are already imported in cli.py.)

- [ ] **Step 4: Run tests + smoke**

Run: `python3 -m pytest tests/test_commands.py -q` then full `python3 -m pytest -q`. Also `python3 -c "import pentai.cli"`.
Smoke:
```bash
printf '/tools\n/playbooks\n/playbooks recon\n/help\n/quit\n' | env HOME=$(mktemp -d) ANTHROPIC_API_KEY=sk-test python3 -m pentai --no-fx
```
Expected: tool availability line, playbook list, the recon playbook rendered, help listing the new commands, clean exit. Paste output in the report.

- [ ] **Step 5: Commit**

```bash
git add pentai/commands.py pentai/cli.py tests/test_commands.py
git commit -m "feat: /clear, /notes, /report, /tools, /playbooks slash commands"
```

---

### Task 3: Responsive startup screen

**Files:**
- Modify: `pentai/ui/startup.py`
- Test: `tests/test_startup.py`

**Interfaces:**
- Produces: `render_startup` stacks the sigil above the capabilities panel when the console is narrow (width < 72), and keeps the side-by-side layout otherwise. Same fields either way.

- [ ] **Step 1: Write the failing test (append to tests/test_startup.py)**

```python
def test_render_startup_narrow_terminal_has_fields():
    from pentai.ui.startup import render_startup
    from pentai.ui.theme import get_palette
    from rich.console import Console
    con = Console(record=True, width=48)
    render_startup(con, palette=get_palette("green"), provider="ollama",
                   model="llama3.1", playbooks=["recon"], tools=["run_command"],
                   modes=["ask", "auto", "bypass"], scope_count=0, session_id="20260727_x")
    out = con.export_text()
    assert "PentAI" in out and "recon" in out and "20260727_x" in out
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `python3 -m pytest tests/test_startup.py -v`
(It may already pass if rich wraps gracefully; the point is to lock in that narrow width does not drop fields. If it passes as-is, still add the explicit stacking in Step 3 for a cleaner narrow layout.)

- [ ] **Step 3: Implement**

In `pentai/ui/startup.py`, change `render_startup` so that when `console.width < 72` it stacks the sigil above the body instead of a two-column grid:
```python
    if console.width < 72:
        layout = Table.grid()
        layout.add_column()
        layout.add_row(Text(SIGIL, style=accent))
        layout.add_row(body)
    else:
        layout = Table.grid(padding=(0, 3))
        layout.add_column()
        layout.add_column()
        layout.add_row(Text(SIGIL, style=accent), body)
```
(Replace the existing single two-column `layout` construction with this width-aware branch. The `Panel(layout, ...)` print stays the same.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_startup.py -q` then full `python3 -m pytest -q`.
Expected: PASS (narrow and normal both render all fields).

- [ ] **Step 5: Commit**

```bash
git add pentai/ui/startup.py tests/test_startup.py
git commit -m "feat: responsive startup screen (stack on narrow terminals)"
```

---

## Self-Review
- Shannon-style tool availability at boot + installed tools fed to the agent context: Task 1. Covered.
- /clear, /notes, /report, /tools, /playbooks: Task 2. Covered.
- Responsive startup for narrow terminals: Task 3. Covered.
- Testable via injected `which`, sentinels asserted, recorded-console width test; interactive handlers verified by smoke.
- Deferred to a dedicated next branch (bigger async rewrite): Codex-style bordered input box + queued messages; live thinking display + ESC-to-stop; sub-agent specialists.
