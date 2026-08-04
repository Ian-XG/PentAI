import os
import shutil
import socket
import sys
import threading
import time
from io import StringIO
from pathlib import Path
import httpx
from typing import Callable
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markup import escape
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text
from .config import Config, load_config, load_config_file, default_config
from .onboarding import (needs_onboarding, run_wizard, save_config, merge_provider,
                         read_config_file, set_active_model, PROVIDER_CHOICES,
                         ProviderChoice, prompt_provider_details)
from .scope import Scope
from .providers.factory import build_provider
from .providers.openai_compat import list_models
from .agent import Agent, ToolSpec, ToolInvocation
from .providers.base import TextDelta, Notice, Message
from .sessions import (Session, new_session, latest_session, load_session,
                       list_sessions)
from .tools.shell import run_command, RUN_COMMAND_TOOL
from .tools.notes import save_note, SAVE_NOTE_TOOL
from .tools.findings import record_finding, RECORD_FINDING_TOOL
from .tools.playbooks import load_playbook, LOAD_PLAYBOOK_TOOL, list_playbooks
from .findings import load_findings, render_report, summarize_findings
from .commands import parse_slash, handle_slash
from .permissions import MODES, next_mode
from .toolcheck import check_tools
from .ui.theme import get_palette
from .ui.animations import run_once, glitch_frames
from .ui.banner import boot_lines, SIGIL
from .ui.startup import render_startup, render_toolcheck
from .ui.settings import render_provider_menu
from .ui.select import select
from .ui.render import markdown_theme
from .ui.mdtable import md
from .ui.toolfmt import format_command_output, looks_like_tool_schema_dump
from .ui.app import build_app, OutputBuffer
from .ui.runner import TurnController

_SKILLS_DIR = Path(__file__).parent / "skills"
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text()

AGENT_TOOL_NAMES = ["run_command", "save_note", "record_finding", "load_playbook"]

def _play_sigil_glitch(console, palette) -> None:
    try:
        with Live(console=console, refresh_per_second=20, transient=True) as live:
            for frame in glitch_frames(SIGIL, frames=6):
                live.update(Text(frame, style=palette["accent"]))
                time.sleep(0.05)
    except Exception:
        pass  # cosmetic only - never let a boot animation crash the app

def stream_turn(events, render_text, render_tool, render_error, render_notice=None) -> None:
    """Consume agent events, buffering text and flushing it as one block before
    each tool invocation, at the end, AND on error (so partial output is never lost)."""
    buf: list[str] = []
    def flush():
        if buf:
            render_text("".join(buf))
            buf.clear()
    try:
        for ev in events:
            if isinstance(ev, TextDelta):
                buf.append(ev.text)
            elif isinstance(ev, Notice):
                flush()
                if render_notice:
                    render_notice(ev.text)
            elif isinstance(ev, ToolInvocation):
                flush()
                render_tool(ev)
    except Exception as e:
        flush()
        render_error(e)
    else:
        flush()

def friendly_error(e: Exception) -> str:
    conn_types = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, socket.gaierror)
    msg = str(e)
    if isinstance(e, conn_types) or "nodename nor servname" in msg or "Name or service not known" in msg or "Temporary failure in name resolution" in msg:
        return ("cannot reach the AI provider (network / DNS). Check your internet connection, "
                "the provider base_url, and your API key with /setup.")
    if "401" in msg or "403" in msg or "unauthorized" in msg.lower() or "invalid api key" in msg.lower():
        return "the AI provider rejected the request (auth). Check your API key with /setup."
    return f"error: {msg}"

def session_context(scope_entries: list[str], mode: str, cwd: str,
                    tools: list[str] | None = None,
                    findings_summary: str = "") -> str:
    scope = ", ".join(scope_entries) if scope_entries else "(none set)"
    lines = [f"--- session context ---",
             f"authorized scope: {scope}",
             f"permission mode: {mode}",
             f"working directory: {cwd}"]
    if tools:
        lines.append(f"installed tools: {', '.join(tools)}")
    if findings_summary:
        lines.append("findings so far (do not re-report; build on these):\n"
                     + findings_summary)
    return "\n".join(lines)

_PENTAI_HOME = Path.home() / ".pentai"

def build_agent(cfg: Config, scope: Scope, confirm: Callable[[str], bool],
                session_dir: Path, mode_getter: Callable[[], str] = lambda: "ask",
                context_provider: Callable[[], str] | None = None,
                history: list[Message] | None = None) -> Agent:
    provider = build_provider(cfg)
    tools = {
        "run_command": ToolSpec(
            RUN_COMMAND_TOOL,
            lambda args: run_command(args.get("command", ""), scope=scope,
                                     confirm=confirm, mode=mode_getter())),
        "save_note": ToolSpec(
            SAVE_NOTE_TOOL,
            lambda args: save_note(args.get("text", ""), session_dir=session_dir)),
        "record_finding": ToolSpec(
            RECORD_FINDING_TOOL,
            lambda args: record_finding(args, session_dir=session_dir)),
        "load_playbook": ToolSpec(
            LOAD_PLAYBOOK_TOOL,
            lambda args: load_playbook(args.get("name", ""), skills_dir=_SKILLS_DIR)),
    }
    return Agent(provider, _SYSTEM_PROMPT, tools, history=history,
                 context_provider=context_provider)

def parse_session_arg(argv: list[str]) -> tuple[str, str | None]:
    """Decide which session to open from the command line. Returns a (kind, id)
    pair: ("new", None) fresh (default), ("latest", None) resume most recent
    (-c/--continue/--resume), or ("id", <id>) resume a specific engagement
    (--resume <id> / --resume=<id>)."""
    for i, a in enumerate(argv):
        if a in ("-c", "--continue"):
            return ("latest", None)
        if a == "--resume":
            nxt = argv[i + 1] if i + 1 < len(argv) else None
            if nxt and not nxt.startswith("-"):
                return ("id", nxt)
            return ("latest", None)
        if a.startswith("--resume="):
            return ("id", a.split("=", 1)[1])
    return ("new", None)

def resolve_session(base: Path, argv: list[str], *, provider: str, model: str,
                    scope: list[str], now=None) -> Session:
    """Open the session the command line asked for, creating a fresh one when
    there is nothing to resume (empty store, or an unknown id)."""
    kind, sid = parse_session_arg(argv)
    kw = {} if now is None else {"now": now}
    if kind == "latest":
        s = latest_session(base)
        if s is not None:
            return s
    elif kind == "id":
        s = load_session(base, sid)
        if s is not None:
            return s
    return new_session(base, provider=provider, model=model, scope=scope, **kw)

def build_and_save_report(session: Session, scope_entries: list[str]) -> tuple[str, Path]:
    """Render the engagement report from structured findings + freeform notes and
    write it to report.md in the session dir (0600). Returns (markdown, path)."""
    findings = load_findings(session.dir)
    notes_path = session.notes_path
    notes = notes_path.read_text() if notes_path.exists() else ""
    md_text = render_report(findings, notes=notes, scope=scope_entries,
                            date=session.meta.created_at,
                            title=f"PentAI Engagement Report - {session.id}")
    out = session.dir / "report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md_text)
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass
    return md_text, out

def format_sessions(base: Path) -> str:
    metas = list_sessions(base)
    if not metas:
        return "no saved sessions yet - each run starts one; resume with 'pentai --resume'."
    lines = ["saved sessions (resume with /resume <id>):"]
    for m in metas:
        title = m.title or "(untitled)"
        prov = f"{m.provider}:{m.model}".strip(":") or "?"
        lines.append(f"  {m.id}  {m.turns:>3} turns  {prov:<24} {title}")
    return "\n".join(lines)

def model_command(provider, args: list[str], *, list_models_fn=list_models,
                  persist=set_active_model) -> str:
    """Switch the active provider's model in place (/model <name>), or list what's
    available (/model). The switch is live for this session and persisted to config."""
    if args:
        name = args[0]
        if hasattr(provider, "set_model"):
            provider.set_model(name)
        else:
            provider.model = name
        persist(name)
        return f"[ model: {name} ]"
    base = getattr(provider, "base_url", None)
    if not base:
        return f"current model: {provider.model}\nswitch with /model <name>"
    try:
        models = list_models_fn(base, getattr(provider, "api_key", None))
    except Exception as e:
        return f"current model: {provider.model}\n(couldn't list models: {e})"
    listing = ", ".join(models) if models else "(none found)"
    return f"current model: {provider.model}\navailable: {listing}\nswitch with /model <name>"

def apply_mode_command(current: str, args: list[str]) -> str:
    if not args:
        return next_mode(current)
    if args[0] in MODES:
        return args[0]
    return current

def provider_ready(cfg: Config) -> bool:
    pc = cfg.providers[cfg.active]
    if pc.api_key:
        return True
    if pc.kind == "anthropic":
        return False
    if pc.api_key_env is None:
        return True
    return False

def main_classic(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    fx = "--no-fx" not in argv
    console = Console()
    if needs_onboarding():
        onboard_palette = get_palette("green")
        try:
            cfg_dict = run_wizard(lambda p: console.input(p, markup=False),
                                  lambda m: console.print(m),
                                  secret_fn=lambda p: console.input(p, markup=False, password=True),
                                  render_menu=lambda: render_provider_menu(console, onboard_palette, None))
        except (KeyboardInterrupt, EOFError):
            console.print("\ncancelled, no changes saved", style=onboard_palette["dim"])
            return 0
        save_config(cfg_dict)
    cfg_error: Exception | None = None
    try:
        cfg = load_config_file()
    except Exception as e:
        cfg_error = e
        cfg = default_config()
    palette = get_palette(cfg.palette)
    console.push_theme(markdown_theme(palette))
    if cfg_error is not None:
        console.print(f"[!] could not load config, using defaults: {cfg_error}",
                      style=palette["alert"], markup=False)
    if not provider_ready(cfg):
        pc = cfg.providers[cfg.active]
        env_hint = pc.api_key_env or "the provider's API key env var"
        console.print(f"[!] no API key for '{cfg.active}'. Run /setup, or set {env_hint}.",
                      style=palette["alert"])
    session = resolve_session(_PENTAI_HOME, argv, provider=cfg.active,
                              model=cfg.providers[cfg.active].model, scope=cfg.scope)
    history = session.load_history()
    session_id = session.id
    if fx:
        for line in boot_lines():
            console.print(line, style=palette["dim"])
        _play_sigil_glitch(console, palette)
    render_startup(console, palette=palette, provider=cfg.active,
                   model=cfg.providers[cfg.active].model,
                   playbooks=list_playbooks(_SKILLS_DIR),
                   tools=AGENT_TOOL_NAMES,
                   modes=MODES, scope_count=len(cfg.scope), session_id=session_id)
    if history:
        console.print(f"[ resumed session {session_id} - {len(history)} messages restored ]",
                      style=palette["accent"], markup=False)
    _tool_results = check_tools()
    render_toolcheck(console, palette, _tool_results)
    installed_tools = [name for name, ok in _tool_results if ok]

    scope = Scope(cfg.scope)
    session_dir = session.dir
    cmds = 0

    spinner_stop: dict = {"fn": lambda: None}

    def confirm(prompt: str) -> bool:
        spinner_stop["fn"]()
        return console.input(
            f"[{palette['accent']}]{escape(prompt)} [y/N] [/]"
        ).strip().lower() in ("y", "yes")

    mode_ref = {"mode": "bypass"}
    mode_getter = lambda: mode_ref["mode"]

    kb = KeyBindings()

    @kb.add("s-tab")
    def _(event):
        mode_ref["mode"] = next_mode(mode_ref["mode"])
        event.app.invalidate()

    def bottom_toolbar():
        m = mode_ref["mode"].upper()
        base = f" mode: {m}  (shift+tab to cycle)   scope: {len(scope.entries)}   cmds: {cmds} "
        if mode_ref["mode"] == "bypass":
            return HTML(f'<style bg="ansired" fg="ansiwhite">{base} - NO CONFIRMATIONS </style>')
        return base

    agent = build_agent(cfg, scope, confirm, session_dir, mode_getter,
                        context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd(), installed_tools, summarize_findings(load_findings(session_dir))),
                        history=history)
    prompt_session: PromptSession = PromptSession(key_bindings=kb, bottom_toolbar=bottom_toolbar)
    while True:
        try:
            line = prompt_session.prompt("root@pentai:~# ")
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            continue
        slash = parse_slash(line)
        if slash is not None:
            if slash[0] == "mode":
                mode_ref["mode"] = apply_mode_command(mode_ref["mode"], slash[1])
                console.print(f"[ mode: {mode_ref['mode'].upper()} ]", style=palette["accent"])
                continue
            result = handle_slash(*slash, scope=scope)
            if result == "__quit__":
                break
            if result == "__setup__":
                try:
                    wiz = run_wizard(lambda p: console.input(p, markup=False),
                                     lambda m: console.print(m, style=palette["accent"]),
                                     secret_fn=lambda p: console.input(p, markup=False, password=True),
                                     render_menu=lambda: render_provider_menu(console, palette, cfg.active))
                except (KeyboardInterrupt, EOFError):
                    console.print("\ncancelled, no changes saved", style=palette["dim"])
                    continue
                merged = merge_provider(read_config_file(), wiz)
                save_config(merged)
                cfg = load_config_file()
                palette = get_palette(cfg.palette)
                console.push_theme(markdown_theme(palette))
                scope = Scope(cfg.scope)
                agent = build_agent(cfg, scope, confirm, session_dir, mode_getter,
                                    context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd(), installed_tools, summarize_findings(load_findings(session_dir))),
                                    history=agent.history)
                console.print("[ OK ] saved ~/.pentai/config.yaml", style=palette["accent"])
                continue
            if result == "__model__":
                console.print(model_command(agent.provider, slash[1]),
                              style=palette["accent"], markup=False)
                continue
            if result == "__sessions__":
                console.print(format_sessions(_PENTAI_HOME), style=palette["dim"], markup=False)
                continue
            if result == "__resume__":
                target = load_session(_PENTAI_HOME, slash[1][0]) if slash[1] else latest_session(_PENTAI_HOME)
                if target is None:
                    console.print("[no such session - try /sessions]", style=palette["alert"], markup=False)
                    continue
                session.save_history(agent.history)   # checkpoint the one we're leaving
                session = target
                session_dir = session.dir
                agent = build_agent(cfg, scope, confirm, session_dir, mode_getter,
                                    context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd(), installed_tools, summarize_findings(load_findings(session_dir))),
                                    history=session.load_history())
                console.print(f"[ resumed {session.id} - {len(agent.history)} messages ]",
                              style=palette["accent"], markup=False)
                continue
            if result == "__clear__":
                console.clear()
                continue
            if result == "__notes__":
                notes = session_dir / "notes.md"
                if notes.exists():
                    console.print(Markdown(notes.read_text()))
                else:
                    console.print("[no notes yet]", style=palette["dim"], markup=False)
                continue
            if result == "__findings__":
                summary = summarize_findings(load_findings(session_dir))
                console.print(summary or "[no findings yet - the agent records them with record_finding]",
                              style=palette["dim"] if not summary else palette["accent"], markup=False)
                continue
            if result == "__report__":
                md_text, out = build_and_save_report(session, scope.entries)
                console.print(Markdown(md_text))
                console.print(f"[ saved report to {out} ]", style=palette["accent"], markup=False)
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
            console.print(result, style=palette["accent"], markup=False)
            continue
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
            if ev.name == "run_command":
                cmds += 1
                cmd = ev.arguments.get("command", ev.arguments)
                console.print(f"[EXEC] {cmd}", style=palette["accent"], markup=False)
                console.print(ev.result, style=palette["dim"], markup=False)
            else:
                console.print(ev.result, style=palette["dim"], markup=False)

        def render_error(e):
            stop()
            console.print(f"\n[!] {friendly_error(e)}", style=palette["alert"])

        def render_notice(text):
            stop()
            console.print(f"[!] {text}", style=palette["alert"])

        try:
            stream_turn(agent.send(line), render_text, render_tool, render_error, render_notice)
        except KeyboardInterrupt:
            stop()
            console.print("\n[!] interrupted", style=palette["alert"])
        finally:
            stop()
            spinner_stop["fn"] = lambda: None
            session.save_history(agent.history)   # persist after every turn
    console.print("bye", style=palette["dim"])
    return 0

def _capture_console(render_fn: Callable[[Console], None], width: int | None = None) -> str:
    """Like render_to_ansi, but for helpers (render_startup/render_toolcheck) that
    print onto a Console they're handed rather than returning a renderable."""
    import shutil
    w = shutil.get_terminal_size((100, 24)).columns if width is None else width
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor",
                      width=w, soft_wrap=False)
    render_fn(console)
    return buf.getvalue()

def _restore_terminal() -> None:
    """Belt-and-suspenders on TUI exit: disable every mouse-tracking mode and
    show the cursor, so an abnormal exit (crash, SIGTERM, lost tty) can never
    leave the shell echoing raw mouse escape codes like ^[[<35;13;20M. Harmless
    to run after prompt_toolkit has already restored on a clean exit."""
    try:
        sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1015l\x1b[?25h")
        sys.stdout.flush()
    except Exception:
        pass  # never let cleanup raise on the way out

def run_settings(prompt_fn: Callable[[str], str], print_fn: Callable[[str], None],
                 secret_fn: Callable[[str], str] | None = None,
                 *, current: dict | None = None,
                 render_menu: Callable[[], None] | None = None) -> dict:
    """Show the current provider, run the provider wizard, and merge the result
    into the existing config (preserving scope and other providers). Pure w.r.t.
    disk: callers pass `current` and persist the returned dict themselves.
    `render_menu`, if given, draws the polished panel/table (which already shows
    the current provider), so the plain "current provider: ..." line is skipped."""
    if render_menu is None:
        if current and current.get("active"):
            active = current["active"]
            pc = current.get("providers", {}).get(active, {})
            print_fn(f"current provider: {active}:{pc.get('model', '?')}")
        else:
            print_fn("no provider configured yet - let's set one up")
    wiz = run_wizard(prompt_fn, print_fn, secret_fn, render_menu=render_menu)
    return merge_provider(current, wiz)

def _provider_row(c: ProviderChoice, current_active: str | None) -> str:
    tag = "  ● current" if c.name == current_active else ""
    return f"{c.icon}  {c.name:<14}{c.label}{tag}"

def _provider_start_index(active: str | None) -> int:
    return next((i for i, c in enumerate(PROVIDER_CHOICES) if c.name == active), 0)

def main_settings(argv: list[str] | None = None) -> int:
    console = Console()
    current = read_config_file()
    palette = get_palette((current or {}).get("palette", "green"))
    console.push_theme(markdown_theme(palette))
    active = current.get("active") if current else None
    try:
        if sys.stdout.isatty():
            # arrow-key picker (like Claude Code / OpenClaw / Hermes Agent) - only
            # makes sense with a real interactive terminal attached.
            idx = select(PROVIDER_CHOICES,
                        title="PentAI · Settings — choose your AI provider",
                        render_row=lambda c, is_sel: _provider_row(c, active),
                        active_index=_provider_start_index(active),
                        palette=palette)
            if idx is None:
                console.print("cancelled, no changes saved", style=palette["dim"])
                return 0
            wiz = prompt_provider_details(
                PROVIDER_CHOICES[idx],
                lambda p: console.input(p, markup=False),
                secret_fn=lambda p: console.input(p, markup=False, password=True))
            merged = merge_provider(current, wiz)
        else:
            # non-tty (tests, pipes, non-interactive shells): fall back to the
            # plain/rich text menu - never try to run the interactive app.
            merged = run_settings(
                lambda p: console.input(p, markup=False),
                lambda m: console.print(m),
                secret_fn=lambda p: console.input(p, markup=False, password=True),
                current=current,
                render_menu=lambda: render_provider_menu(console, palette, active))
    except (KeyboardInterrupt, EOFError):
        console.print("\ncancelled, no changes saved", style=palette["dim"])
        return 0
    path = save_config(merged)
    console.print(f"[ OK ] saved {path}", style=palette["accent"])
    return 0

def main_tui(argv: list[str]) -> int:
    console = Console()
    if needs_onboarding():
        onboard_palette = get_palette("green")
        try:
            cfg_dict = run_wizard(lambda p: console.input(p, markup=False),
                                  lambda m: console.print(m),
                                  secret_fn=lambda p: console.input(p, markup=False, password=True),
                                  render_menu=lambda: render_provider_menu(console, onboard_palette, None))
        except (KeyboardInterrupt, EOFError):
            console.print("\ncancelled, no changes saved", style=onboard_palette["dim"])
            return 0
        save_config(cfg_dict)
    cfg_error: Exception | None = None
    try:
        cfg = load_config_file()
    except Exception as e:
        cfg_error = e
        cfg = default_config()
    palette = get_palette(cfg.palette)

    _tool_results = check_tools()
    installed_tools = [name for name, ok in _tool_results if ok]
    scope = Scope(cfg.scope)
    session = resolve_session(_PENTAI_HOME, argv, provider=cfg.active,
                              model=cfg.providers[cfg.active].model, scope=cfg.scope)
    session_dir = session.dir
    session_id = session.id
    restored = session.load_history()

    output = OutputBuffer()
    if cfg_error is not None:
        output.append(Text(
            f"[!] could not load config, using defaults: {cfg_error}", style=palette["alert"]),
            theme=markdown_theme(palette))
    if not provider_ready(cfg):
        pc = cfg.providers[cfg.active]
        env_hint = pc.api_key_env or "the provider's API key env var"
        output.append(Text(
            f"[!] no API key for '{cfg.active}'. Run /setup, or set {env_hint}.", style=palette["alert"]),
            theme=markdown_theme(palette))
    output.append_renderer(lambda w: _capture_console(lambda c: render_startup(
        c, palette=palette, provider=cfg.active, model=cfg.providers[cfg.active].model,
        playbooks=list_playbooks(_SKILLS_DIR), tools=AGENT_TOOL_NAMES, modes=MODES,
        scope_count=len(cfg.scope), session_id=session_id), width=w))
    output.append_renderer(lambda w: _capture_console(lambda c: render_toolcheck(c, palette, _tool_results), width=w))
    if restored:
        output.append(Text(
            f"[ resumed session {session_id} - {len(restored)} messages restored ]",
            style=palette["accent"]), theme=markdown_theme(palette))

    mode_ref = {"mode": "bypass"}
    cmds_ref = {"n": 0}
    thinking = {"start": None, "chars": 0}

    def get_thinking():
        if thinking["start"] is None:
            return None
        from .ui.tui_core import format_thinking
        import time as _t
        return format_thinking(thinking["chars"], _t.time() - thinking["start"])

    def _run_on_loop(fn: Callable[[], None]) -> None:
        app.loop.call_soon_threadsafe(fn)

    def _post(renderable, theme=None) -> None:
        def _append() -> None:
            output.append(renderable, theme=theme)
            app.invalidate()
        _run_on_loop(_append)

    def _confirm(prompt: str) -> bool:
        # Blocks the WORKER thread (this runs inside run_command, called from
        # _start_turn's background thread) until the user answers in the input
        # box. The answer is routed back by _on_submit -> controller.submit,
        # which detects controller.awaiting_confirm and calls this callback.
        event = threading.Event()
        answer = {"v": False}
        def on_answer(yes: bool) -> None:
            answer["v"] = yes
            event.set()
        def _ask() -> None:
            output.append(Text(f"[confirm] {prompt} [y/N]", style=palette["accent"]),
                theme=markdown_theme(palette))
            controller.request_confirm(on_answer)
            app.invalidate()
        _run_on_loop(_ask)
        event.wait()
        return answer["v"]

    agent = build_agent(cfg, scope, _confirm, session_dir, lambda: mode_ref["mode"],
                        context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd(), installed_tools, summarize_findings(load_findings(session_dir))),
                        history=restored)

    def _start_turn(text: str) -> None:
        thinking["start"] = time.time()
        thinking["chars"] = 0
        def render_tool(ev: ToolInvocation) -> None:
            if ev.name == "run_command":
                cmd = ev.arguments.get("command", "")
                cmd_text = Text(f"$ {cmd}", style=palette["accent"])
                result_text = Text(format_command_output(ev.result), style=palette["dim"])
                def _append_exec(cmd_text: Text = cmd_text, result_text: Text = result_text) -> None:
                    cmds_ref["n"] += 1
                    output.append(cmd_text, theme=markdown_theme(palette))
                    output.append(result_text, theme=markdown_theme(palette))
                    app.invalidate()
                _run_on_loop(_append_exec)
            elif ev.name == "save_note":
                def _append_note() -> None:
                    output.append(Text("[note saved]", style=palette["dim"]), theme=markdown_theme(palette))
                    app.invalidate()
                _run_on_loop(_append_note)
            elif ev.name == "record_finding":
                def _append_finding(result: str = ev.result) -> None:
                    output.append(Text(result, style=palette["accent"]), theme=markdown_theme(palette))
                    app.invalidate()
                _run_on_loop(_append_finding)
            elif ev.name == "load_playbook":
                def _append_playbook(result: str = ev.result) -> None:
                    output.append(md(result), theme=markdown_theme(palette))
                    app.invalidate()
                _run_on_loop(_append_playbook)
            else:
                def _append_other(result: str = str(ev.result)) -> None:
                    output.append(Text(result, style=palette["dim"]), theme=markdown_theme(palette))
                    app.invalidate()
                _run_on_loop(_append_other)

        def worker() -> None:
            buf: list[str] = []
            def flush() -> None:
                if buf:
                    text_out = "".join(buf)
                    buf.clear()
                    if looks_like_tool_schema_dump(text_out):
                        _post(Text(
                            "[!] the model echoed the tool schema instead of answering - it is "
                            "probably too small for reliable tool-calling. Switch to a larger model "
                            "with /settings (e.g. gpt-oss:20b, or Claude / GPT-4o).",
                            style=palette["alert"]), theme=markdown_theme(palette))
                    else:
                        _post(md(text_out), theme=markdown_theme(palette))
            try:
                for ev in agent.send(text):
                    if controller.stopped:
                        break
                    if isinstance(ev, TextDelta):
                        buf.append(ev.text)
                        thinking["chars"] += len(ev.text)
                    elif isinstance(ev, Notice):
                        flush()
                        _post(Text(f"[!] {ev.text}", style=palette["alert"]),
                              theme=markdown_theme(palette))
                    elif isinstance(ev, ToolInvocation):
                        flush()
                        render_tool(ev)
            except Exception as e:
                flush()
                _post(Text(f"[!] {friendly_error(e)}", style=palette["alert"]),
                    theme=markdown_theme(palette))
            else:
                flush()
            finally:
                def _done() -> None:
                    thinking["start"] = None
                    session.save_history(agent.history)   # persist after every turn
                    controller.finish()
                    app.invalidate()
                _run_on_loop(_done)
        threading.Thread(target=worker, daemon=True).start()

    controller = TurnController(start_turn=_start_turn)

    def _on_submit(text: str) -> None:
        nonlocal session, session_dir, agent
        text = text.strip()
        if not text:
            return
        output.append_full_width(f" > {text}", f"bold black on {palette['accent']}")
        app.invalidate()
        if controller.awaiting_confirm:
            controller.submit(text)
            app.invalidate()
            return
        if text.startswith("/"):
            slash = parse_slash(text)
            if slash is None:
                return
            cmd, args = slash
            if cmd == "mode":
                mode_ref["mode"] = apply_mode_command(mode_ref["mode"], args)
                output.append(Text(f"[ mode: {mode_ref['mode'].upper()} ]", style=palette["accent"]),
                    theme=markdown_theme(palette))
                app.invalidate()
                return
            result = handle_slash(cmd, args, scope=scope)
            if result == "__quit__":
                app.exit()
                return
            if result == "__setup__":
                # The interactive wizard uses blocking console.input() calls that
                # would deadlock the full-screen event loop, so it's not run here.
                output.append(Text(
                    "to change your AI provider, quit (/quit) and run:  pentai --settings",
                    style=palette["accent"]), theme=markdown_theme(palette))
                app.invalidate()
                return
            if result == "__model__":
                output.append(Text(model_command(agent.provider, args), style=palette["accent"]),
                    theme=markdown_theme(palette))
                app.invalidate()
                return
            if result == "__sessions__":
                output.append(Text(format_sessions(_PENTAI_HOME), style=palette["dim"]),
                    theme=markdown_theme(palette))
                app.invalidate()
                return
            if result == "__resume__":
                target = load_session(_PENTAI_HOME, args[0]) if args else latest_session(_PENTAI_HOME)
                if target is None:
                    output.append(Text("[no such session - try /sessions]", style=palette["alert"]),
                        theme=markdown_theme(palette))
                    app.invalidate()
                    return
                session.save_history(agent.history)   # checkpoint the one we're leaving
                session = target
                session_dir = session.dir
                restored_now = session.load_history()
                agent = build_agent(cfg, scope, _confirm, session_dir, lambda: mode_ref["mode"],
                                    context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd(), installed_tools, summarize_findings(load_findings(session_dir))),
                                    history=restored_now)
                output.append(Text(f"[ resumed {session.id} - {len(restored_now)} messages ]",
                    style=palette["accent"]), theme=markdown_theme(palette))
                app.invalidate()
                return
            if result == "__clear__":
                output.clear()
                app.invalidate()
                return
            if result == "__notes__":
                notes = session_dir / "notes.md"
                if notes.exists():
                    output.append(md(notes.read_text()), theme=markdown_theme(palette))
                else:
                    output.append(Text("[no notes yet]", style=palette["dim"]),
                        theme=markdown_theme(palette))
                app.invalidate()
                return
            if result == "__findings__":
                summary = summarize_findings(load_findings(session_dir))
                output.append(Text(
                    summary or "[no findings yet - the agent records them with record_finding]",
                    style=palette["accent"] if summary else palette["dim"]),
                    theme=markdown_theme(palette))
                app.invalidate()
                return
            if result == "__report__":
                md_text, out = build_and_save_report(session, scope.entries)
                output.append(md(md_text), theme=markdown_theme(palette))
                output.append(Text(f"[ saved report to {out} ]", style=palette["accent"]),
                    theme=markdown_theme(palette))
                app.invalidate()
                return
            if result == "__tools__":
                output.append_renderer(lambda w: _capture_console(lambda c: render_toolcheck(c, palette, _tool_results), width=w))
                output.append(Text("agent tools: " + ", ".join(AGENT_TOOL_NAMES), style=palette["dim"]),
                    theme=markdown_theme(palette))
                app.invalidate()
                return
            if result == "__playbooks__":
                if args:
                    output.append(md(load_playbook(args[0], skills_dir=_SKILLS_DIR)),
                        theme=markdown_theme(palette))
                else:
                    names = list_playbooks(_SKILLS_DIR)
                    output.append(Text("playbooks: " + ", ".join(names), style=palette["accent"]),
                        theme=markdown_theme(palette))
                app.invalidate()
                return
            output.append(Text(result, style=palette["accent"]), theme=markdown_theme(palette))
            app.invalidate()
            return
        controller.submit(text)

    def _cycle_mode() -> None:
        mode_ref["mode"] = next_mode(mode_ref["mode"])

    def _status() -> str:
        return (f" mode:{mode_ref['mode'].upper()}  scope:{len(scope.entries)}  "
                f"cmds:{cmds_ref['n']}  queued:{len(controller.queue)}  (shift+tab mode, esc stop, /quit)")

    app = build_app(output=output, on_submit=_on_submit, on_stop=controller.stop,
                    on_cycle_mode=_cycle_mode, get_status=_status, get_thinking=get_thinking)

    if not sys.stdout.isatty():
        console.print("[!] --tui needs an interactive terminal; use classic mode (just run pentai).", markup=False)
        return 0
    console.clear()  # clean launch: no leftover shell prompt above the full-screen app
    try:
        app.run()
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        _restore_terminal()
    return 0

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--settings" in argv:
        return main_settings(argv)
    return main_classic(argv) if "--classic" in argv else main_tui(argv)
