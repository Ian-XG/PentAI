from .scope import Scope

_HELP = ("commands: /scope add <target>, /scope list, /setup, /mode [ask|auto|bypass], "
         "/clear, /notes, /report, /tools, /playbooks [name], /help, /quit")

SLASH_COMMANDS = [
    ("/scope", "add or list authorized targets"),
    ("/mode", "switch permission mode (ask / auto / bypass)"),
    ("/setup", "configure AI provider and key"),
    ("/clear", "clear the screen"),
    ("/notes", "show session notes"),
    ("/report", "show the findings report"),
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
    if command == "setup":
        return "__setup__"
    if command in ("clear", "notes", "report", "tools", "playbooks"):
        return "__" + command + "__"
    if command == "help":
        return _HELP
    if command == "quit":
        return "__quit__"
    return "[unknown command] " + command
