import shutil
from typing import Callable

COMMON_TOOLS: list[str] = [
    "nmap", "masscan", "rustscan", "gobuster", "ffuf", "dirsearch", "nikto",
    "sqlmap", "hydra", "whatweb", "wpscan", "dig", "whois", "curl", "nc",
    "subfinder", "john", "hashcat", "netcat", "enum4linux",
]

def check_tools(names: list[str] | None = None,
                which: Callable[[str], str | None] | None = None) -> list[tuple[str, bool]]:
    names = COMMON_TOOLS if names is None else names
    which = shutil.which if which is None else which
    return [(name, which(name) is not None) for name in names]
