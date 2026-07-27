import os
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
from .ui.app import build_app, OutputBuffer
from .ui.runner import TurnController
from .ui.tui_core import render_to_ansi

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
    scope = ", ".join(scope_entries) if scope_entries else "(none set)"
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

def main_classic(argv: list[str] | None = None) -> int:
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
                    console.print("[no notes yet]", style=palette["dim"], markup=False)
                continue
            if result == "__report__":
                notes = session_dir / "notes.md"
                if notes.exists():
                    console.print(Markdown("# PentAI Session Report\n\n" + notes.read_text()))
                else:
                    console.print("[no findings recorded yet - the agent saves them with save_note]",
                                  style=palette["dim"], markup=False)
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

def main_tui(argv: list[str]) -> int:
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

    _tool_results = check_tools()
    installed_tools = [name for name, ok in _tool_results if ok]
    scope = Scope(cfg.scope)
    session_dir = Path.home() / ".pentai" / "session"

    output = OutputBuffer()
    if cfg_error is not None:
        output.append(render_to_ansi(Text(
            f"[!] could not load config, using defaults: {cfg_error}", style=palette["alert"]),
            theme=markdown_theme(palette)))
    if not provider_ready(cfg):
        pc = cfg.providers[cfg.active]
        env_hint = pc.api_key_env or "the provider's API key env var"
        output.append(render_to_ansi(Text(
            f"[!] no API key for '{cfg.active}'. Run /setup, or set {env_hint}.", style=palette["alert"]),
            theme=markdown_theme(palette)))
    output.append(_capture_console(lambda c: render_startup(
        c, palette=palette, provider=cfg.active, model=cfg.providers[cfg.active].model,
        playbooks=list_playbooks(_SKILLS_DIR), tools=AGENT_TOOL_NAMES, modes=MODES,
        scope_count=len(cfg.scope), session_id=session_id)))
    output.append(_capture_console(lambda c: render_toolcheck(c, palette, _tool_results)))

    mode_ref = {"mode": "ask"}
    cmds_ref = {"n": 0}

    def _run_on_loop(fn: Callable[[], None]) -> None:
        app.loop.call_soon_threadsafe(fn)

    def _post(chunk: str) -> None:
        def _append() -> None:
            output.append(chunk)
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
            output.append(render_to_ansi(Text(f"[confirm] {prompt} [y/N]", style=palette["accent"]),
                theme=markdown_theme(palette)))
            controller.request_confirm(on_answer)
            app.invalidate()
        _run_on_loop(_ask)
        event.wait()
        return answer["v"]

    agent = build_agent(cfg, scope, _confirm, session_dir, lambda: mode_ref["mode"],
                        context_provider=lambda: session_context(scope.entries, mode_ref["mode"], os.getcwd(), installed_tools))

    def _start_turn(text: str) -> None:
        def worker() -> None:
            buf: list[str] = []
            def flush() -> None:
                if buf:
                    chunk = render_to_ansi(Markdown("".join(buf)), theme=markdown_theme(palette))
                    buf.clear()
                    _post(chunk)
            try:
                for ev in agent.send(text):
                    if controller.stopped:
                        break
                    if isinstance(ev, TextDelta):
                        buf.append(ev.text)
                    elif isinstance(ev, ToolInvocation):
                        flush()
                        cmd = ev.arguments.get("command", ev.arguments)
                        chunk = (render_to_ansi(Text(f"[EXEC] {cmd}", style=palette["accent"]),
                                    theme=markdown_theme(palette)) +
                                render_to_ansi(Text(str(ev.result), style=palette["dim"]),
                                    theme=markdown_theme(palette)))
                        def _append_exec(chunk: str = chunk) -> None:
                            cmds_ref["n"] += 1
                            output.append(chunk)
                            app.invalidate()
                        _run_on_loop(_append_exec)
            except Exception as e:
                flush()
                _post(render_to_ansi(Text(f"[!] {friendly_error(e)}", style=palette["alert"]),
                    theme=markdown_theme(palette)))
            else:
                flush()
            finally:
                def _done() -> None:
                    controller.finish()
                    app.invalidate()
                _run_on_loop(_done)
        threading.Thread(target=worker, daemon=True).start()

    controller = TurnController(start_turn=_start_turn)

    def _on_submit(text: str) -> None:
        text = text.strip()
        if not text:
            return
        output.append(render_to_ansi(
            Text(f" > {text} ", style=f"bold black on {palette['accent']}"),
            theme=markdown_theme(palette)))
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
                output.append(render_to_ansi(Text(f"[ mode: {mode_ref['mode'].upper()} ]", style=palette["accent"]),
                    theme=markdown_theme(palette)))
                app.invalidate()
                return
            result = handle_slash(cmd, args, scope=scope)
            if result == "__quit__":
                app.exit()
                return
            if result == "__setup__":
                # The interactive wizard uses blocking console.input() calls that
                # would deadlock the full-screen event loop, so it's not run here.
                output.append(render_to_ansi(Text(
                    "setup wizard is not available in --tui mode; run 'pentai --classic' then /setup",
                    style=palette["alert"]), theme=markdown_theme(palette)))
                app.invalidate()
                return
            if result == "__clear__":
                output.clear()
                app.invalidate()
                return
            if result == "__notes__":
                notes = session_dir / "notes.md"
                if notes.exists():
                    output.append(render_to_ansi(Markdown(notes.read_text()), theme=markdown_theme(palette)))
                else:
                    output.append(render_to_ansi(Text("[no notes yet]", style=palette["dim"]),
                        theme=markdown_theme(palette)))
                app.invalidate()
                return
            if result == "__report__":
                notes = session_dir / "notes.md"
                if notes.exists():
                    output.append(render_to_ansi(Markdown("# PentAI Session Report\n\n" + notes.read_text()),
                        theme=markdown_theme(palette)))
                else:
                    output.append(render_to_ansi(Text(
                        "[no findings recorded yet - the agent saves them with save_note]",
                        style=palette["dim"]), theme=markdown_theme(palette)))
                app.invalidate()
                return
            if result == "__tools__":
                output.append(_capture_console(lambda c: render_toolcheck(c, palette, _tool_results)))
                output.append(render_to_ansi(Text("agent tools: " + ", ".join(AGENT_TOOL_NAMES), style=palette["dim"]),
                    theme=markdown_theme(palette)))
                app.invalidate()
                return
            if result == "__playbooks__":
                if args:
                    output.append(render_to_ansi(Markdown(load_playbook(args[0], skills_dir=_SKILLS_DIR)),
                        theme=markdown_theme(palette)))
                else:
                    names = list_playbooks(_SKILLS_DIR)
                    output.append(render_to_ansi(Text("playbooks: " + ", ".join(names), style=palette["accent"]),
                        theme=markdown_theme(palette)))
                app.invalidate()
                return
            output.append(render_to_ansi(Text(result, style=palette["accent"]), theme=markdown_theme(palette)))
            app.invalidate()
            return
        controller.submit(text)

    def _cycle_mode() -> None:
        mode_ref["mode"] = next_mode(mode_ref["mode"])

    def _status() -> str:
        return (f" mode:{mode_ref['mode'].upper()}  scope:{len(scope.entries)}  "
                f"cmds:{cmds_ref['n']}  queued:{len(controller.queue)}  (shift+tab mode, esc stop, /quit)")

    app = build_app(output=output, on_submit=_on_submit, on_stop=controller.stop,
                    on_cycle_mode=_cycle_mode, get_status=_status)

    if not sys.stdout.isatty():
        console.print("[!] --tui needs an interactive terminal; use classic mode (just run pentai).", markup=False)
        return 0
    try:
        app.run()
    except (EOFError, KeyboardInterrupt):
        pass
    return 0

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    return main_classic(argv) if "--classic" in argv else main_tui(argv)
