from pathlib import Path
from ..providers.base import Tool
from ..assets import record_service
from ..recon_parse import parse_nmap

def ingest_nmap(session_dir: Path, output: str) -> int:
    """Parse nmap output and fold every open service into the asset map. Returns
    the number of services recorded. This is the automatic recon loop: the agent
    runs a scan, PentAI captures the surface without the model having to."""
    count = 0
    for h in parse_nmap(output):
        for s in h.services:
            if "open" not in s.state:
                continue
            record_service(session_dir, address=h.address, port=s.port, proto=s.proto,
                           state=s.state, service=s.name, product=s.product,
                           version=s.version, hostname=h.hostname, os=h.os)
            count += 1
    return count

def record_service_tool(args: dict, *, session_dir: Path) -> str:
    address = (args.get("address") or "").strip()
    port = args.get("port")
    if not address or port is None:
        return "[record_service needs an address and a port]"
    try:
        port = int(port)
    except (TypeError, ValueError):
        return f"[record_service: invalid port {port!r}]"
    proto = args.get("proto", "tcp")
    h = record_service(session_dir, address=address, port=port,
                       proto=proto, state=args.get("state", "open"),
                       service=args.get("service", ""), product=args.get("product", ""),
                       version=args.get("version", ""), hostname=args.get("hostname", ""),
                       os=args.get("os", ""))
    # match on (port, proto), not port alone - a host can have distinct tcp
    # and udp services on the same port (record_service itself already keys
    # on both), and matching port-only here could report the wrong service's
    # name back to the agent.
    svc = next((s for s in h.services if s.port == port and s.proto == proto), None)
    detail = f"{port}/{proto}"
    if svc and svc.name:
        detail += f" {svc.name}"
    return f"[mapped {address} {detail}]"

RECORD_SERVICE_TOOL = Tool(
    name="record_service",
    description=("Add a discovered host/port/service to the engagement's live asset "
                 "map. Call this for every open port or service you find during recon "
                 "(nmap, gobuster, banner grabs) so the attack surface is tracked and "
                 "shows up in the report. Safe to call repeatedly to enrich a service."),
    parameters={
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "Host IP or address"},
            "port": {"type": "integer", "description": "Port number"},
            "proto": {"type": "string", "description": "tcp or udp (default tcp)"},
            "state": {"type": "string", "description": "open | filtered | closed (default open)"},
            "service": {"type": "string", "description": "Service name, e.g. http, ssh"},
            "product": {"type": "string", "description": "Product/banner, e.g. nginx, OpenSSH"},
            "version": {"type": "string", "description": "Version string if known"},
            "hostname": {"type": "string", "description": "Resolved hostname, if any"},
            "os": {"type": "string", "description": "OS guess for the host, if any"},
        },
        "required": ["address", "port"],
    },
)
