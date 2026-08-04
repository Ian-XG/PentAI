from pathlib import Path
from pentai.tools.assets import record_service_tool, RECORD_SERVICE_TOOL
from pentai.assets import load_assets

def test_record_service_tool_persists(tmp_path: Path):
    msg = record_service_tool({"address": "10.0.0.5", "port": 80, "service": "http",
                               "product": "nginx"}, session_dir=tmp_path)
    assert "10.0.0.5" in msg and "80" in msg
    hosts = load_assets(tmp_path)
    assert hosts[0].services[0].name == "http" and hosts[0].services[0].product == "nginx"

def test_record_service_tool_coerces_string_port(tmp_path: Path):
    record_service_tool({"address": "10.0.0.5", "port": "443", "service": "https"},
                        session_dir=tmp_path)
    assert load_assets(tmp_path)[0].services[0].port == 443

def test_record_service_tool_requires_address_and_port(tmp_path: Path):
    assert "address" in record_service_tool({"port": 80}, session_dir=tmp_path).lower()
    assert "address" in record_service_tool({"address": "x"}, session_dir=tmp_path).lower()
    assert load_assets(tmp_path) == []

def test_record_service_tool_bad_port(tmp_path: Path):
    msg = record_service_tool({"address": "10.0.0.5", "port": "notaport"}, session_dir=tmp_path)
    assert "invalid port" in msg.lower()
    assert load_assets(tmp_path) == []

def test_tool_schema_requires_address_and_port():
    assert RECORD_SERVICE_TOOL.parameters["required"] == ["address", "port"]
