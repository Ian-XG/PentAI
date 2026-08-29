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

def test_ingest_nmap_maps_ping_sweep_hosts_with_no_services(tmp_path: Path):
    # `nmap -sn <cidr>` (host discovery, recon playbook's own step 1) finds
    # live hosts but no ports at all - these must still land in the asset
    # map, not be silently dropped because record_service is per-port.
    sweep = ("Nmap scan report for 10.0.0.1\nHost is up (0.0012s latency).\n"
            "Nmap scan report for web01 (10.0.0.5)\nHost is up (0.045s latency).\n")
    n = ingest_nmap(tmp_path, sweep)
    assert n == 2
    hosts = {h.address: h for h in load_assets(tmp_path)}
    assert set(hosts) == {"10.0.0.1", "10.0.0.5"}
    assert hosts["10.0.0.5"].hostname == "web01"
    assert hosts["10.0.0.1"].services == []

def test_ingest_nmap_does_not_record_ambiguous_open_filtered_as_open(tmp_path: Path):
    # "open|filtered" is nmap's own AMBIGUOUS, unconfirmed state - a substring
    # check on "open" wrongly matches it, silently recording an unconfirmed
    # port as if nmap had confirmed it open. Same bug class already fixed in
    # intel.py's intel_leads(); this is the sibling in the asset-ingest path.
    # The host itself still gets mapped (nmap did find it live) - it's the
    # unconfirmed port specifically that must not show up as a service.
    scan = "Nmap scan report for 10.0.0.9\n53/udp open|filtered domain\n"
    n = ingest_nmap(tmp_path, scan)
    assert n == 1                          # the host, not the ambiguous port
    hosts = load_assets(tmp_path)
    assert hosts[0].address == "10.0.0.9"
    assert hosts[0].services == []         # ambiguous port not recorded as a service

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

def test_record_service_tool_confirms_correct_service_on_proto_clash(tmp_path: Path):
    # a host can have distinct tcp and udp services on the same port -
    # the confirmation message must name the one that was just recorded,
    # not whichever one happens to match on port alone.
    msg_tcp = record_service_tool({"address": "10.0.0.5", "port": 53, "proto": "tcp",
                                   "service": "dns-tcp"}, session_dir=tmp_path)
    msg_udp = record_service_tool({"address": "10.0.0.5", "port": 53, "proto": "udp",
                                   "service": "dns-udp"}, session_dir=tmp_path)
    assert "dns-tcp" in msg_tcp
    assert "dns-udp" in msg_udp

def test_tool_schema_requires_address_and_port():
    assert RECORD_SERVICE_TOOL.parameters["required"] == ["address", "port"]
