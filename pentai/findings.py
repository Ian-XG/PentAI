"""Structured findings: the agent's actual deliverable. Notes are freeform;
findings are typed (title, severity, target, evidence, remediation) so PentAI can
count them, sort them, feed them back into its own context, and render a
professional engagement report. Stored per-session in findings.json, written
0600 - findings carry credentials and evidence and never leave the machine."""
import json
import os
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path

# worst-first: index doubles as the sort/severity rank
SEVERITIES = ["critical", "high", "medium", "low", "info"]

_SYNONYMS = {
    "crit": "critical",
    "hi": "high",
    "med": "medium", "moderate": "medium", "medium-high": "medium",
    "lo": "low",
    "informational": "info", "information": "info", "none": "info",
}

@dataclass
class Finding:
    title: str
    severity: str = ""
    target: str = ""
    description: str = ""
    evidence: str = ""
    remediation: str = ""
    id: str = ""
    created_at: str = ""

def normalize_severity(sev) -> str:
    if not sev:
        return "info"
    s = str(sev).strip().lower()
    if s in SEVERITIES:
        return s
    return _SYNONYMS.get(s, "info")

def is_known_severity(sev) -> bool:
    """True if `sev` maps to a real severity level (directly or via a synonym).
    Lets callers tell an intended 'info' from an unrecognized value that
    normalize_severity would silently bucket into 'info'."""
    if not sev:
        return False
    s = str(sev).strip().lower()
    return s in SEVERITIES or s in _SYNONYMS

def severity_rank(sev: str) -> int:
    s = normalize_severity(sev)
    return SEVERITIES.index(s)

def _findings_path(session_dir: Path) -> Path:
    return session_dir / "findings.json"

def _now() -> str:
    import time
    return time.strftime("%Y%m%d_%H%M%S")

_FINDING_FIELDS = {f.name for f in fields(Finding)}

def _finding_from_dict(d: dict) -> Finding | None:
    """Build a Finding from a stored dict, tolerating extra keys (a newer or
    hand-edited schema) and missing optional ones. Returns None if there isn't
    even a title to salvage. load_findings runs every turn, so a single stale
    record must never crash the whole session."""
    if not isinstance(d, dict) or not d.get("title"):
        return None
    known = {k: v for k, v in d.items() if k in _FINDING_FIELDS}
    f = Finding(**known)
    f.severity = normalize_severity(f.severity)
    return f

def load_findings(session_dir: Path) -> list[Finding]:
    try:
        data = json.loads(_findings_path(session_dir).read_text())
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out = [_finding_from_dict(d) for d in data]
    return [f for f in out if f is not None]

def _save_findings(session_dir: Path, findings: list[Finding]) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(session_dir, 0o700)
    except OSError:
        pass
    path = _findings_path(session_dir)
    payload = json.dumps([asdict(f) for f in findings], indent=1)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(payload)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)

def add_finding(session_dir: Path, *, title: str, severity: str, target: str = "",
                description: str = "", evidence: str = "", remediation: str = "",
                now=_now) -> Finding:
    existing = load_findings(session_dir)
    f = Finding(title=title.strip(), severity=normalize_severity(severity),
                target=target, description=description, evidence=evidence,
                remediation=remediation, id=f"F-{len(existing) + 1:03d}",
                created_at=now())
    existing.append(f)
    _save_findings(session_dir, existing)
    return f

def summarize_findings(findings: list[Finding]) -> str:
    """One compact line per finding, worst-first - fed back into the agent's
    context so it knows what it has already found and builds on it."""
    if not findings:
        return ""
    ordered = sorted(findings, key=lambda f: severity_rank(f.severity))
    lines = [f"{f.id} [{f.severity.upper()}] {f.title}"
             + (f" ({f.target})" if f.target else "") for f in ordered]
    return "\n".join(lines)

def render_report(findings: list[Finding], *, notes: str = "",
                  scope: list[str] | None = None, date: str = "",
                  title: str = "PentAI Engagement Report") -> str:
    out: list[str] = [f"# {title}", ""]
    if scope:
        out.append(f"**Scope:** {', '.join(scope)}")
    if date:
        out.append(f"**Date:** {date}")
    out.append("")
    if not findings:
        out.append("_No findings recorded. The agent records them with `record_finding`._")
        if notes.strip():
            out += ["", "## Notes", "", notes.rstrip()]
        return "\n".join(out)

    ordered = sorted(findings, key=lambda f: severity_rank(f.severity))
    out += ["## Summary", "", "| Severity | Count |", "| --- | --- |"]
    for sev in SEVERITIES:
        n = sum(1 for f in ordered if f.severity == sev)
        if n:
            out.append(f"| {sev} | {n} |")
    out.append(f"| **total** | **{len(ordered)}** |")
    out += ["", "## Findings", ""]
    for f in ordered:
        out.append(f"### [{f.severity.upper()}] {f.title}  ({f.id})")
        if f.target:
            out.append(f"**Target:** {f.target}")
        if f.description:
            out += ["", f.description.rstrip()]
        if f.evidence:
            out += ["", "**Evidence:**", "", "```", f.evidence.rstrip(), "```"]
        if f.remediation:
            out += ["", f"**Remediation:** {f.remediation.rstrip()}"]
        out.append("")
    if notes.strip():
        out += ["## Notes", "", notes.rstrip()]
    return "\n".join(out)
