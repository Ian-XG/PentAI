from .scope import Scope

_HELP = ("commands: /scope add <target>, /scope list, /settings, /setup, /model [name], "
         "/mode [ask|auto|bypass], /sessions, /resume [id], /clear, /notes, /findings, "
         "/report, /tools, /playbooks [name], /help, /quit")

SLASH_COMMANDS = [
    ("/scope", "add or list authorized targets"),
    ("/mode", "switch permission mode (ask / auto / bypass)"),
    ("/model", "switch model for the active provider, or /model to list"),
    ("/settings", "change AI provider, key, and settings"),
    ("/sessions", "list past engagements you can resume"),
    ("/resume", "resume a past engagement: /resume <id> (or /resume for the latest)"),
    ("/clear", "clear the screen"),
    ("/notes", "show session notes"),
    ("/findings", "list structured findings recorded this engagement"),
    ("/report", "render the engagement report and save it to the session"),
    ("/tools", "list agent tools and installed CLI tools"),
    ("/playbooks", "list playbooks, or /playbooks <name> to show one"),
    ("/help", "show available commands"),
    ("/quit", "exit PentAI"),
]

def parse_slash(line: str) -> tuple[str, list[str]] | None:
    line = line.strip()
    if not line.startswith("/"):
        return None
    parts = line[1:].split()
    if not parts:
        return None
    return parts[0], parts[1:]

def handle_slash(command: str, args: list[str], *, scope: Scope) -> str:
    if command == "scope":
        if args and args[0] == "add" and len(args) > 1:
            scope.add(args[1])
            return f"[scope +] {args[1]}"
        if args and args[0] == "list":
            return "scope: " + (", ".join(scope.entries) or "(empty)")
        return "usage: /scope add <target> | /scope list"
    if command in ("setup", "settings"):
        return "__setup__"
    if command in ("clear", "notes", "report", "tools", "playbooks", "model",
                   "sessions", "resume", "findings"):
        return "__" + command + "__"
    if command == "help":
        return _HELP
    if command == "quit":
        return "__quit__"
    return "[unknown command] " + command
