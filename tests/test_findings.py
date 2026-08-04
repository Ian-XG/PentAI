from pathlib import Path
from pentai.findings import (Finding, SEVERITIES, normalize_severity, severity_rank,
                            add_finding, load_findings, render_report)

def test_normalize_severity_maps_synonyms_and_case():
    assert normalize_severity("Critical") == "critical"
    assert normalize_severity("HIGH") == "high"
    assert normalize_severity("med") == "medium"
    assert normalize_severity("informational") == "info"
    assert normalize_severity("moderate") == "medium"

def test_normalize_severity_unknown_defaults_info():
    assert normalize_severity("banana") == "info"
    assert normalize_severity("") == "info"
    assert normalize_severity(None) == "info"

def test_severity_rank_orders_critical_first():
    ranks = [severity_rank(s) for s in SEVERITIES]
    assert ranks == sorted(ranks)                 # SEVERITIES already worst-first
    assert severity_rank("critical") < severity_rank("info")

def test_add_and_load_finding_roundtrip(tmp_path: Path):
    f = add_finding(tmp_path, title="SQLi in login", severity="Critical",
                    target="10.0.0.5", description="union-based",
                    evidence="' OR 1=1--", remediation="parameterize",
                    now=lambda: "20260804_120000")
    assert f.id == "F-001"
    assert f.severity == "critical"               # normalized
    loaded = load_findings(tmp_path)
    assert loaded == [f]

def test_finding_ids_increment(tmp_path: Path):
    a = add_finding(tmp_path, title="a", severity="low")
    b = add_finding(tmp_path, title="b", severity="high")
    assert a.id == "F-001" and b.id == "F-002"

def test_load_findings_missing_returns_empty(tmp_path: Path):
    assert load_findings(tmp_path) == []

def test_load_findings_corrupt_returns_empty(tmp_path: Path):
    (tmp_path / "findings.json").write_text("{bad")
    assert load_findings(tmp_path) == []

def test_render_report_has_summary_table_and_sorted_findings():
    findings = [
        Finding(title="Info leak", severity="info", id="F-002"),
        Finding(title="RCE", severity="critical", target="10.0.0.9",
                description="deserialization", evidence="payload", remediation="patch", id="F-001"),
        Finding(title="Weak TLS", severity="medium", id="F-003"),
    ]
    out = render_report(findings, scope=["10.0.0.0/24"], date="2026-08-04")
    # summary table counts by severity
    assert "| critical | 1 |" in out.lower()
    assert "| info | 1 |" in out.lower()
    # critical finding rendered before info (sorted by severity)
    assert out.index("RCE") < out.index("Info leak")
    # finding detail present
    assert "10.0.0.9" in out and "deserialization" in out and "patch" in out
    assert "F-001" in out
    assert "10.0.0.0/24" in out and "2026-08-04" in out

def test_render_report_empty_is_graceful():
    out = render_report([])
    assert "no findings" in out.lower()

def test_render_report_includes_notes_section():
    out = render_report([Finding(title="x", severity="low", id="F-001")],
                        notes="misc recon output")
    assert "misc recon output" in out
    assert "notes" in out.lower()

def test_render_report_omits_empty_optional_fields():
    out = render_report([Finding(title="Open port", severity="low", id="F-001",
                                 target="", description="just noting", evidence="", remediation="")])
    assert "Evidence" not in out          # empty evidence not shown
    assert "just noting" in out
