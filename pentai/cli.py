import sys
from pathlib import Path
from typing import Callable
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markup import escape
from rich.markdown import Markdown
from .config import Config, load_config, load_config_file, default_config
from .onboarding import needs_onboarding, run_wizard, save_config, merge_provider, read_config_file
from .scope import Scope
from .providers.factory import build_provider
from .agent import Agent, ToolSpec, ToolInvocation
from .providers.base import TextDelta
from .tools.shell import run_command, RUN_COMMAND_TOOL
from .tools.notes import save_note, SAVE_NOTE_TOOL
from .tools.playbooks import load_playbook, LOAD_PLAYBOOK_TOOL
from .commands import parse_slash, handle_slash
from .permissions import MODES, next_mode
from .ui.theme import get_palette
from .ui.banner import render_banner, boot_lines
from .ui.render import status_bar, markdown_theme

_SKILLS_DIR = Path(__file__).parent / "skills"
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text()

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
    console.print(render_banner(palette, simple=not fx), style=palette["primary"])

    scope = Scope(cfg.scope)
    session_dir = Path.home() / ".pentai" / "session"
    cmds = 0

    def confirm(prompt: str) -> bool:
        return console.input(
            f"[{palette['accent']}]{escape(prompt)} [y/N] [/]"
        ).strip().lower() == "y"

    mode_ref = {"mode": "ask"}

    kb = KeyBindings()

    @kb.add("s-tab")
    def _(event):
        mode_ref["mode"] = next_mode(mode_ref["mode"])
        event.app.invalidate()

    def bottom_toolbar():
        return (f" mode: {mode_ref['mode'].upper()}  (shift+tab to cycle)"
                f"   scope: {len(scope.entries)}   cmds: {cmds}")

    agent = build_agent(cfg, scope, confirm, session_dir, lambda: mode_ref["mode"])
    session: PromptSession = PromptSession(key_bindings=kb, bottom_toolbar=bottom_toolbar)
    while True:
        console.print(status_bar(cfg.active, cfg.providers[cfg.active].model,
                                 len(scope.entries), cmds, mode_ref["mode"]),
                      style=palette["dim"])
        try:
            line = session.prompt("root@pentai:~# ")
        except (EOFError, KeyboardInterrupt):
            break
        slash = parse_slash(line)
        if slash is not None:
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
                scope = Scope(cfg.scope)
                agent = build_agent(cfg, scope, confirm, session_dir, lambda: mode_ref["mode"])
                console.print("[ OK ] saved ~/.pentai/config.yaml", style=palette["accent"])
                continue
            if slash[0] == "mode":
                mode_ref["mode"] = apply_mode_command(mode_ref["mode"], slash[1])
                console.print(f"[ mode: {mode_ref['mode'].upper()} ]", style=palette["accent"])
                continue
            console.print(result, style=palette["accent"])
            continue
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
    console.print("bye", style=palette["dim"])
    return 0
