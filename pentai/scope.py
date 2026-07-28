import ipaddress
import re
from fnmatch import fnmatch

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HOST_RE = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")

def _normalize_entry(entry: str) -> str:
    entry = entry.strip()
    for pre in ("http://", "https://"):
        if entry.startswith(pre):
            entry = entry[len(pre):]
            break
    if "/" in entry:
        host, _, rest = entry.partition("/")
        if not rest.isdigit():  # a URL path, not a CIDR mask - drop it
            entry = host
    return entry

def extract_targets(command: str) -> list[str]:
    found: list[str] = []
    for m in _IP_RE.findall(command):
        if m not in found:
            found.append(m)
    for m in _HOST_RE.findall(command):
        if m not in found:
            found.append(m)
    return found

class Scope:
    def __init__(self, entries: list[str]):
        self.entries = list(entries)

    def add(self, entry: str) -> None:
        entry = _normalize_entry(entry)
        if entry and entry not in self.entries:
            self.entries.append(entry)

    def contains(self, target: str) -> bool:
        for entry in self.entries:
            if self._match(entry, target):
                return True
        return False

    def out_of_scope(self, command: str) -> list[str]:
        return [t for t in extract_targets(command) if not self.contains(t)]

    @staticmethod
    def _match(entry: str, target: str) -> bool:
        try:
            net = ipaddress.ip_network(entry, strict=False)
            addr = ipaddress.ip_address(target)
            return addr in net
        except ValueError:
            pass
        return fnmatch(target, entry) or entry == target
