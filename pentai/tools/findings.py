from pathlib import Path
from ..providers.base import Tool
from ..findings import add_finding, is_known_severity, SEVERITIES

def record_finding(args: dict, *, session_dir: Path) -> str:
    title = (args.get("title") or "").strip()
    if not title:
        return "[record_finding needs a title]"
    given_sev = args.get("severity", "info")
    f = add_finding(session_dir, title=title,
                    severity=given_sev,
                    target=args.get("target", ""),
                    description=args.get("description", ""),
                    evidence=args.get("evidence", ""),
                    remediation=args.get("remediation", ""))
    msg = f"[recorded {f.id} [{f.severity.upper()}] {f.title}]"
    if not is_known_severity(given_sev):
        # Don't let a mistyped severity silently bury a serious finding at info -
        # tell the model so it can re-record with a valid level.
        msg += (f" [note: severity {given_sev!r} not recognized, defaulted to "
                f"{f.severity}; use one of {'/'.join(SEVERITIES)}]")
    return msg

RECORD_FINDING_TOOL = Tool(
    name="record_finding",
    description=("Record a structured security finding (vulnerability, weakness, or "
                 "exposure) for the engagement report. Use this - not save_note - "
                 "for anything that belongs in the final report."),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short finding title, e.g. 'SQL injection in /login'"},
            "severity": {"type": "string", "enum": SEVERITIES,
                         "description": "critical | high | medium | low | info"},
            "target": {"type": "string", "description": "Affected host, URL, or endpoint"},
            "description": {"type": "string", "description": "What the issue is and its impact"},
            "evidence": {"type": "string", "description": "Proof: request/response, payload, command output"},
            "remediation": {"type": "string", "description": "How to fix it"},
        },
        "required": ["title", "severity"],
    },
)
