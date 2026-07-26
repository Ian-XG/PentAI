from .scope import Scope

_HELP = ("commands: /scope add <target>, /scope list, /help, /quit")

def parse_slash(line: str) -> tuple[str, list[str]] | None:
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
    if command == "help":
        return _HELP
    if command == "quit":
        return "__quit__"
    return "[unknown command] " + command
