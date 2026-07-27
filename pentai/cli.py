import sys
import time
from pathlib import Path
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
from .ui.theme import get_palette
from .ui.animations import run_once, glitch_frames
from .ui.banner import boot_lines, SIGIL
from .ui.startup import render_startup
from .ui.render import status_bar, markdown_theme

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

def build_agent(cfg: Config, scope: Scope, confirm: Callable[[str], bool],
                session_dir: Path, mode_getter: Callable[[], str] = lambda: "ask") -> Agent:
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
    return Agent(provider, _SYSTEM_PROMPT, tools)

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

    scope = Scope(cfg.scope)
    session_dir = Path.home() / ".pentai" / "session"
    cmds = 0

    spinner_stop: dict = {"fn": lambda: None}

    def confirm(prompt: str) -> bool:
        spinner_stop["fn"]()
        return console.input(
            f"[{palette['accent']}]{escape(prompt)} [y/N] [/]"
        ).strip().lower() == "y"

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

    agent = build_agent(cfg, scope, confirm, session_dir, mode_getter)
    session: PromptSession = PromptSession(key_bindings=kb, bottom_toolbar=bottom_toolbar)
    while True:
        bar_style = palette["alert"] if mode_ref["mode"] == "bypass" else palette["dim"]
        console.print(status_bar(cfg.active, cfg.providers[cfg.active].model,
                                 len(scope.entries), cmds, mode_ref["mode"]),
                      style=bar_style)
        try:
            line = session.prompt("root@pentai:~# ")
        except (EOFError, KeyboardInterrupt):
            break
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
                agent = build_agent(cfg, scope, confirm, session_dir, mode_getter)
                console.print("[ OK ] saved ~/.pentai/config.yaml", style=palette["accent"])
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
            console.print(f"\n[!] error: {e}", style=palette["alert"])

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
