from pathlib import Path
from pentai.tools.findings import record_finding, RECORD_FINDING_TOOL
from pentai.findings import load_findings

def test_record_finding_persists_and_confirms(tmp_path: Path):
    msg = record_finding({"title": "SQLi", "severity": "high", "target": "10.0.0.5"},
                         session_dir=tmp_path)
    assert "F-001" in msg and "HIGH" in msg
    saved = load_findings(tmp_path)
    assert len(saved) == 1 and saved[0].title == "SQLi" and saved[0].severity == "high"

def test_record_finding_requires_title(tmp_path: Path):
    msg = record_finding({"severity": "high"}, session_dir=tmp_path)
    assert "title" in msg.lower()
    assert load_findings(tmp_path) == []

def test_record_finding_warns_on_unrecognized_severity(tmp_path: Path):
    msg = record_finding({"title": "RCE", "severity": "urgent"}, session_dir=tmp_path)
    assert "not recognized" in msg.lower()
    assert "critical/high/medium/low/info" in msg
    # still persisted (defaulted to info) - the finding isn't lost
    assert load_findings(tmp_path)[0].severity == "info"

def test_record_finding_synonym_severity_is_silent(tmp_path: Path):
    msg = record_finding({"title": "XSS", "severity": "moderate"}, session_dir=tmp_path)
    assert "not recognized" not in msg.lower()
    assert load_findings(tmp_path)[0].severity == "medium"   # moderate -> medium

def test_tool_schema_lists_severities_and_requires_title():
    props = RECORD_FINDING_TOOL.parameters["properties"]
    assert "critical" in props["severity"]["enum"]
    assert RECORD_FINDING_TOOL.parameters["required"] == ["title", "severity"]
