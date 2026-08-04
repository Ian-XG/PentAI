from pathlib import Path
from pentai.tools.assets import record_service_tool, RECORD_SERVICE_TOOL, ingest_nmap
from pentai.assets import load_assets

_NMAP = ("Nmap scan report for web01 (10.0.0.5)\n"
         "PORT    STATE SERVICE VERSION\n"
         "22/tcp  open  ssh     OpenSSH 8.2p1\n"
         "80/tcp  open  http    nginx 1.18.0\n"
         "443/tcp closed https\n")

def test_ingest_nmap_records_open_services_only(tmp_path: Path):
    n = ingest_nmap(tmp_path, _NMAP)
    assert n == 2                                  # closed port skipped
    h = load_assets(tmp_path)[0]
    assert h.address == "10.0.0.5" and h.hostname == "web01"
    ports = sorted(s.port for s in h.services)
    assert ports == [22, 80]
    ssh = next(s for s in h.services if s.port == 22)
    assert ssh.product == "OpenSSH" and ssh.version == "8.2p1"

def test_ingest_nmap_is_idempotent_and_enriches(tmp_path: Path):
    ingest_nmap(tmp_path, "Nmap scan report for 10.0.0.5\nPORT   STATE SERVICE\n22/tcp open ssh\n")
    ingest_nmap(tmp_path, _NMAP)                    # richer re-scan
    hosts = load_assets(tmp_path)
    assert len(hosts) == 1                          # same host, not duplicated
    ssh = next(s for s in hosts[0].services if s.port == 22)
    assert ssh.product == "OpenSSH"                 # enriched on rescan

def test_ingest_nmap_no_scan_output_records_nothing(tmp_path: Path):
    assert ingest_nmap(tmp_path, "ls: command output, not a scan") == 0
    assert load_assets(tmp_path) == []

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
