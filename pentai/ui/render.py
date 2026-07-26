_TAGS = {"AI": "[AI]", "EXEC": "[EXEC]", "VULN": "[!] VULN", "INFO": "[INFO]"}

def format_tag(kind: str, text: str) -> str:
    tag = _TAGS.get(kind, _TAGS["INFO"])
    return f"{tag} {text}"

def status_bar(provider: str, model: str, scope_count: int, cmds: int, mode: str = "ask") -> str:
    return f"-[ {provider}:{model} ]-[ scope:{scope_count} ]-[ mode:{mode.upper()} ]-[ cmds:{cmds} ]-"
