import sys
from pathlib import Path
from typing import Callable
from prompt_toolkit import PromptSession
from rich.console import Console
from rich.markup import escape
from .config import Config, load_config, load_config_file, default_config
from .scope import Scope
from .providers.factory import build_provider
from .agent import Agent, ToolSpec, ToolInvocation
from .providers.base import TextDelta
from .tools.shell import run_command, RUN_COMMAND_TOOL
from .tools.notes import save_note, SAVE_NOTE_TOOL
from .tools.playbooks import load_playbook, LOAD_PLAYBOOK_TOOL
from .commands import parse_slash, handle_slash
from .ui.theme import get_palette
from .ui.banner import render_banner, boot_lines
from .ui.render import status_bar

_SKILLS_DIR = Path(__file__).parent / "skills"
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text()

def build_agent(cfg: Config, scope: Scope, confirm: Callable[[str], bool],
                session_dir: Path) -> Agent:
    provider = build_provider(cfg)
    tools = {
        "run_command": ToolSpec(
            RUN_COMMAND_TOOL,
            lambda args: run_command(args.get("command", ""), scope=scope, confirm=confirm)),
        "save_note": ToolSpec(
            SAVE_NOTE_TOOL,
            lambda args: save_note(args.get("text", ""), session_dir=session_dir)),
        "load_playbook": ToolSpec(
            LOAD_PLAYBOOK_TOOL,
            lambda args: load_playbook(args.get("name", ""), skills_dir=_SKILLS_DIR)),
    }
    return Agent(provider, _SYSTEM_PROMPT, tools)

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    fx = "--no-fx" not in argv
    console = Console()
    try:
        cfg = load_config_file()
    except Exception:
        cfg = default_config()
    palette = get_palette(cfg.palette)
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

    agent = build_agent(cfg, scope, confirm, session_dir)
    session: PromptSession = PromptSession()
    while True:
        console.print(status_bar(cfg.active, cfg.providers[cfg.active].model,
                                 len(scope.entries), cmds), style=palette["dim"])
        try:
            line = session.prompt("root@pentai:~# ")
        except (EOFError, KeyboardInterrupt):
            break
        slash = parse_slash(line)
        if slash is not None:
            result = handle_slash(*slash, scope=scope)
            if result == "__quit__":
                break
            console.print(result, style=palette["accent"])
            continue
        try:
            for ev in agent.send(line):
                if isinstance(ev, TextDelta):
                    console.print(ev.text, style=palette["primary"], end="")
                elif isinstance(ev, ToolInvocation):
                    cmds += 1
                    console.print(f"\n[EXEC] {ev.arguments}\n{ev.result}",
                                  style=palette["accent"], markup=False)
            console.print()
        except Exception as e:
            console.print(f"\n[!] error: {e}", style=palette["alert"])
    console.print("bye", style=palette["dim"])
    return 0
