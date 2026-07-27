import os
import socket
import sys
import time
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
from .onboarding import needs_onboarding, run_wizard, save_config, merge_provider, read_config_file
from .scope import Scope
from .providers.factory import build_provider
from .agent import Agent, ToolSpec, ToolInvocation
from .providers.base import TextDelta
from .tools.shell import run_command, RUN_COMMAND_TOOL
from .tools.notes import save_note, SAVE_NOTE_TOOL
from .tools.playbooks import load_playbook, LOAD_PLAYBOOK_TOOL, list_playbooks
from .commands import parse_slash, handle_slash
from .permissions import MODES, next_mode
from .toolcheck import check_tools
from .ui.theme import get_palette
from .ui.animations import run_once, glitch_frames
from .ui.banner import boot_lines, SIGIL
from .ui.startup import render_startup, render_toolcheck
from .ui.render import markdown_theme

_SKILLS_DIR = Path(__file__).parent / "skills"
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text()

AGENT_TOOL_NAMES = ["run_command", "save_note", "load_playbook"]

def _play_sigil_glitch(console, palette) -> None:
    try:
        with Live(console=console, refresh_per_second=20, transient=True) as live:
            for frame in glitch_frames(SIGIL, frames=6):
                live.update(Text(frame, style=palette["accent"]))
                time.sleep(0.05)
    except Exception:
        pass  # cosmetic only - never let a boot animation crash the app

def stream_turn(events, render_text, render_tool, render_error) -> None:
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
                    tools: list[str] | None = None) -> str:
    scope = ", ".join(scope_entries) if scope_entries else "(empty - tell the user to run /scope add <target>)"
    lines = [f"--- session context ---",
             f"authorized scope: {scope}",
             f"permission mode: {mode}",
             f"working directory: {cwd}"]
    if tools:
        lines.append(f"installed tools: {', '.join(tools)}")
    return "\n".join(lines)

def build_agent(cfg: Config, scope: Scope, confirm: Callable[[str], bool],
                session_dir: Path, mode_getter: Callable[[], str] = lambda: "ask",
                context_provider: Callable[[], str] | None = None) -> Agent:
    provider = build_provider(cfg)
    tools = {
        "run_command": ToolSpec(
            RUN_COMMAND_TOOL,
            lambda args: run_command(args.get("command", ""), scope=scope,
                                     confirm=confirm, mode=mode_getter())),
        "save_note": ToolSpec(
            SAVE_NOTE_TOOL,
            lambda args: save_note(args.get("text", ""), session_dir=session_dir)),
        "load_playbook": ToolSpec(
            LOAD_PLAYBOOK_TOOL,
            lambda args: load_playbook(args.get("name", ""), skills_dir=_SKILLS_DIR)),
    }
    return Agent(provider, _SYSTEM_PROMPT, tools, context_provider=context_provider)

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

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    fx = "--no-fx" not in argv
    console = Console()
    session_id = time.strftime("%Y%m%d_%H%M%S")
    if needs_onboarding():
        cfg_dict = run_wizard(lambda p: console.input(p, markup=False),
                              lambda m: console.print(m),
                              secret_fn=lambda p: console.input(p, markup=False, password=True))
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
    if fx:
        for line in boot_lines():
            console.print(line, style=palette["dim"])
        _play_sigil_glitch(console, palette)
    render_startup(console, palette=palette, provider=cfg.active,
                   model=cfg.providers[cfg.active].model,
                   playbooks=list_playbooks(_SKILLS_DIR),
                   tools=AGENT_TOOL_NAMES,
                   modes=MODES, scope_count=len(cfg.scope), session_id=session_id)
    _tool_results = check_tools()
    render_toolcheck(console, palette, _tool_results)
    installed_tools = [name for name, ok in _tool_results if ok]

    scope = Scope(cfg.scope)
    session_dir = Path.home() / ".pentai" / "session"
    cmds = 0

    spinner_stop: dict = {"fn": lambda: None}

    def confirm(prompt: str) -> bool:
        spinner_stop["fn"]()
        return console.input(
            f"[{palette['accent']}]{escape(prompt)} [y/N] [/]"
        ).strip().lower() in ("y", "yes")

    mode_ref = {"mode": "ask"}
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
                        context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd(), installed_tools))
    session: PromptSession = PromptSession(key_bindings=kb, bottom_toolbar=bottom_toolbar)
    while True:
        try:
            line = session.prompt("root@pentai:~# ")
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
                wiz = run_wizard(lambda p: console.input(p, markup=False),
                                 lambda m: console.print(m, style=palette["accent"]),
                                 secret_fn=lambda p: console.input(p, markup=False, password=True))
                merged = merge_provider(read_config_file(), wiz)
                save_config(merged)
                cfg = load_config_file()
                palette = get_palette(cfg.palette)
                console.push_theme(markdown_theme(palette))
                scope = Scope(cfg.scope)
                agent = build_agent(cfg, scope, confirm, session_dir, mode_getter,
                                    context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd(), installed_tools))
                console.print("[ OK ] saved ~/.pentai/config.yaml", style=palette["accent"])
                continue
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
            console.print(result, style=palette["accent"])
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
            cmds += 1
            cmd = ev.arguments.get("command", ev.arguments)
            console.print(f"[EXEC] {cmd}", style=palette["accent"], markup=False)
            console.print(ev.result, style=palette["dim"], markup=False)

        def render_error(e):
            stop()
            console.print(f"\n[!] {friendly_error(e)}", style=palette["alert"])

        try:
            stream_turn(agent.send(line), render_text, render_tool, render_error)
        except KeyboardInterrupt:
            stop()
            console.print("\n[!] interrupted", style=palette["alert"])
        finally:
            stop()
            spinner_stop["fn"] = lambda: None
    console.print("bye", style=palette["dim"])
    return 0
