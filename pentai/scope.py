import ipaddress
import re
from fnmatch import fnmatch

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HOST_RE = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")

# Dotted tokens whose final label is one of these are local files, not hosts:
# `cat report.txt`, `bash linpeas.sh`, `gobuster -o out.json` must NOT trip the
# out-of-scope warning. Spurious warnings on everyday file arguments train the
# operator to click through them, which weakens the one prompt that matters.
# A handful of these are also real TLDs (.sh, .zip, .pub); in a pentest command
# line the file reading is overwhelmingly more likely, and IP targets - the
# common scan case - are matched separately and never affected.
_FILE_EXTS = frozenset("""
txt md rst log csv tsv json yaml yml xml html htm js mjs ts css scss
py pyc sh bash zsh rb pl php go rs c h cpp hpp java class jar
png jpg jpeg gif svg bmp ico webp pdf doc docx xls xlsx ppt pptx
zip tar gz tgz bz2 xz 7z rar db sqlite sqlite3 bak old tmp swp lock
conf cfg ini toml env pem key crt cert csr pub ovpn pcap cap
bin exe dll so o out dat dump nmap gnmap
""".split())

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

def _looks_like_file(host: str) -> bool:
    return host.rsplit(".", 1)[-1].lower() in _FILE_EXTS

def extract_targets(command: str) -> list[str]:
    found: list[str] = []
    for m in _IP_RE.findall(command):
        if m not in found:
            found.append(m)
    for m in _HOST_RE.findall(command):
        if m not in found and not _looks_like_file(m):
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
