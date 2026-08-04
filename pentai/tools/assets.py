from pathlib import Path
from ..providers.base import Tool
from ..assets import record_service

def record_service_tool(args: dict, *, session_dir: Path) -> str:
    address = (args.get("address") or "").strip()
    port = args.get("port")
    if not address or port is None:
        return "[record_service needs an address and a port]"
    try:
        port = int(port)
    except (TypeError, ValueError):
        return f"[record_service: invalid port {port!r}]"
    h = record_service(session_dir, address=address, port=port,
                       proto=args.get("proto", "tcp"), state=args.get("state", "open"),
                       service=args.get("service", ""), product=args.get("product", ""),
                       version=args.get("version", ""), hostname=args.get("hostname", ""),
                       os=args.get("os", ""))
    svc = next((s for s in h.services if s.port == port), None)
    detail = f"{port}/{args.get('proto', 'tcp')}"
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
