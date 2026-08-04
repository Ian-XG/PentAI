"""Parse nmap output into structured hosts/services so PentAI can auto-populate
its asset map from a scan - no model round-trip, no missed ports. Parses nmap's
default (normal) text output, which is what run_command captures."""
import re
from dataclasses import dataclass, field

@dataclass
class ParsedService:
    port: int
    proto: str = "tcp"
    state: str = "open"
    name: str = ""
    product: str = ""
    version: str = ""

@dataclass
class ParsedHost:
    address: str
    hostname: str = ""
    os: str = ""
    services: list[ParsedService] = field(default_factory=list)

# "Nmap scan report for web01 (10.0.0.5)"  or  "Nmap scan report for 10.0.0.5"
_REPORT = re.compile(r"^Nmap scan report for (?:(\S+) \(([^)]+)\)|(\S+))\s*$")
# "22/tcp  open  ssh     OpenSSH 8.2p1 ..."
_PORT = re.compile(r"^(\d+)/(tcp|udp)\s+(open\|filtered|open|filtered|closed)\s+(\S+)(?:\s+(.*))?$")
_OS_INFO = re.compile(r"Service Info:.*?OS:\s*([^;]+)")

def is_nmap_command(command: str) -> bool:
    tokens = re.split(r"[\s|;&]+", command.strip())
    return any(t == "nmap" or t.endswith("/nmap") for t in tokens)

def _split_version(rest: str) -> tuple[str, str]:
    """Split nmap's VERSION column into (product, version). nmap renders it as
    'Product Name Version extra...', e.g. 'OpenSSH 8.2p1 Ubuntu ...' or
    'Apache Tomcat 9.0.65'. Everything up to the first version-looking token is
    the product; that token is the version."""
    rest = rest.strip()
    if not rest:
        return "", ""
    parts = rest.split()
    for i, tok in enumerate(parts):
        if i > 0 and re.match(r"^\d", tok):        # first numeric-leading token after product
            return " ".join(parts[:i]), tok
    return parts[0], ""

def parse_nmap(text: str) -> list[ParsedHost]:
    hosts: list[ParsedHost] = []
    current: ParsedHost | None = None
    for line in text.splitlines():
        m = _REPORT.match(line.strip())
        if m:
            if m.group(3):                       # "for <addr>" (no hostname)
                current = ParsedHost(address=m.group(3))
            else:                                # "for <name> (<addr>)"
                current = ParsedHost(address=m.group(2), hostname=m.group(1))
            hosts.append(current)
            continue
        if current is None:
            continue
        pm = _PORT.match(line.strip())
        if pm:
            product, version = _split_version(pm.group(5) or "")
            current.services.append(ParsedService(
                port=int(pm.group(1)), proto=pm.group(2), state=pm.group(3),
                name=pm.group(4), product=product, version=version))
            continue
        om = _OS_INFO.search(line)
        if om:
            current.os = om.group(1).strip()
    return hosts
