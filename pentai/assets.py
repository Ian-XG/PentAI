"""Engagement asset store: a live, structured map of the target - hosts and the
services on them. Real recon output (nmap, gobuster, etc.) is captured here as
first-class objects the agent can query and reason over, instead of text that
scrolls away. Fed back into the agent's context every turn as the current attack
surface, and rendered into the report. Stored per-session in assets.json, 0600
- host/service inventory is engagement data and stays on the machine."""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

@dataclass
class Service:
    port: int
    proto: str = "tcp"
    state: str = "open"
    name: str = ""       # service, e.g. http
    product: str = ""    # e.g. nginx
    version: str = ""

@dataclass
class Host:
    address: str
    hostname: str = ""
    os: str = ""
    services: list[Service] = field(default_factory=list)

def _assets_path(session_dir: Path) -> Path:
    return session_dir / "assets.json"

def load_assets(session_dir: Path) -> list[Host]:
    try:
        data = json.loads(_assets_path(session_dir).read_text())
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    hosts = []
    for h in data:
        services = [Service(**s) for s in h.get("services", [])]
        hosts.append(Host(address=h["address"], hostname=h.get("hostname", ""),
                          os=h.get("os", ""), services=services))
    return hosts

def _save_assets(session_dir: Path, hosts: list[Host]) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(session_dir, 0o700)
    except OSError:
        pass
    path = _assets_path(session_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps([asdict(h) for h in hosts], indent=1))
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)

def _find_host(hosts: list[Host], address: str) -> Host | None:
    return next((h for h in hosts if h.address == address), None)

def set_host(session_dir: Path, *, address: str, hostname: str = "", os: str = "") -> Host:
    hosts = load_assets(session_dir)
    h = _find_host(hosts, address)
    if h is None:
        h = Host(address=address)
        hosts.append(h)
    if hostname:
        h.hostname = hostname
    if os:
        h.os = os
    _save_assets(session_dir, hosts)
    return h

def record_service(session_dir: Path, *, address: str, port: int, proto: str = "tcp",
                   state: str = "open", service: str = "", product: str = "",
                   version: str = "", hostname: str = "", os: str = "") -> Host:
    hosts = load_assets(session_dir)
    h = _find_host(hosts, address)
    if h is None:
        h = Host(address=address)
        hosts.append(h)
    if hostname:
        h.hostname = hostname
    if os:
        h.os = os
    svc = next((s for s in h.services if s.port == port and s.proto == proto), None)
    if svc is None:
        svc = Service(port=port, proto=proto)
        h.services.append(svc)
    # merge: only overwrite with non-empty new info, never wipe what we knew
    if state:
        svc.state = state
    if service:
        svc.name = service
    if product:
        svc.product = product
    if version:
        svc.version = version
    _save_assets(session_dir, hosts)
    return h

def _svc_label(s: Service) -> str:
    parts = [f"{s.port}/{s.proto}"]
    if s.name:
        parts.append(s.name)
    banner = " ".join(x for x in (s.product, s.version) if x)
    if banner:
        parts.append(banner)
    return " ".join(parts)

def summarize_assets(hosts: list[Host]) -> str:
    """Compact attack-surface summary - one line per host, ports sorted - injected
    into the agent's context so it always knows the target's exposed surface."""
    if not hosts:
        return ""
    lines = []
    for h in hosts:
        label = h.address + (f" ({h.hostname})" if h.hostname else "")
        if h.os:
            label += f" [{h.os}]"
        svcs = ", ".join(_svc_label(s) for s in sorted(h.services, key=lambda s: (s.port, s.proto)))
        lines.append(f"{label}: {svcs}" if svcs else label)
    return "\n".join(lines)

def render_assets(hosts: list[Host]) -> str:
    if not hosts:
        return ""
    out: list[str] = []
    for h in hosts:
        title = h.address
        if h.hostname:
            title += f" ({h.hostname})"
        if h.os:
            title += f" - {h.os}"
        out.append(f"### {title}")
        if h.services:
            out += ["", "| Port | Proto | State | Service | Product | Version |",
                    "| --- | --- | --- | --- | --- | --- |"]
            for s in sorted(h.services, key=lambda s: (s.port, s.proto)):
                out.append(f"| {s.port} | {s.proto} | {s.state} | {s.name} | {s.product} | {s.version} |")
        out.append("")
    return "\n".join(out).rstrip()
