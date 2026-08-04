from pathlib import Path
from pentai.assets import (Host, Service, record_service, set_host, load_assets,
                           summarize_assets, render_assets)

def test_record_service_creates_host_and_service(tmp_path: Path):
    h = record_service(tmp_path, address="10.0.0.5", port=80, service="http",
                       product="nginx", version="1.18")
    assert h.address == "10.0.0.5"
    assert len(h.services) == 1
    s = h.services[0]
    assert s.port == 80 and s.proto == "tcp" and s.name == "http" and s.product == "nginx"
    assert load_assets(tmp_path) == [h]

def test_record_service_upserts_same_port(tmp_path: Path):
    record_service(tmp_path, address="10.0.0.5", port=22, service="ssh")
    record_service(tmp_path, address="10.0.0.5", port=22, service="ssh",
                   product="OpenSSH", version="8.2")   # enrich same service
    hosts = load_assets(tmp_path)
    assert len(hosts) == 1 and len(hosts[0].services) == 1
    assert hosts[0].services[0].product == "OpenSSH" and hosts[0].services[0].version == "8.2"

def test_record_service_distinguishes_proto(tmp_path: Path):
    record_service(tmp_path, address="10.0.0.5", port=53, proto="tcp", service="dns")
    record_service(tmp_path, address="10.0.0.5", port=53, proto="udp", service="dns")
    assert len(load_assets(tmp_path)[0].services) == 2

def test_record_service_second_host(tmp_path: Path):
    record_service(tmp_path, address="10.0.0.5", port=80)
    record_service(tmp_path, address="10.0.0.6", port=443)
    hosts = load_assets(tmp_path)
    assert {h.address for h in hosts} == {"10.0.0.5", "10.0.0.6"}

def test_record_service_merges_only_nonempty(tmp_path: Path):
    record_service(tmp_path, address="10.0.0.5", port=80, product="nginx", version="1.18")
    record_service(tmp_path, address="10.0.0.5", port=80, service="http")  # no product/version
    s = load_assets(tmp_path)[0].services[0]
    assert s.product == "nginx" and s.version == "1.18"   # not wiped by later empty record
    assert s.name == "http"                               # new info added

def test_record_service_sets_host_fields_when_given(tmp_path: Path):
    record_service(tmp_path, address="10.0.0.5", port=22, hostname="web01", os="Linux")
    h = load_assets(tmp_path)[0]
    assert h.hostname == "web01" and h.os == "Linux"

def test_set_host_updates_metadata(tmp_path: Path):
    record_service(tmp_path, address="10.0.0.5", port=22)
    set_host(tmp_path, address="10.0.0.5", os="Ubuntu 20.04")
    assert load_assets(tmp_path)[0].os == "Ubuntu 20.04"

def test_set_host_creates_when_absent(tmp_path: Path):
    set_host(tmp_path, address="10.0.0.9", hostname="dc01")
    hosts = load_assets(tmp_path)
    assert len(hosts) == 1 and hosts[0].hostname == "dc01" and hosts[0].services == []

def test_load_assets_missing_and_corrupt(tmp_path: Path):
    assert load_assets(tmp_path) == []
    (tmp_path / "assets.json").write_text("{bad")
    assert load_assets(tmp_path) == []

def test_summarize_assets_compact_lines():
    hosts = [Host(address="10.0.0.5", hostname="web01", os="Linux",
                  services=[Service(port=22, name="ssh", product="OpenSSH", version="8.2"),
                            Service(port=80, name="http", product="nginx")])]
    out = summarize_assets(hosts)
    assert "10.0.0.5" in out and "web01" in out
    assert "22/tcp ssh" in out and "OpenSSH 8.2" in out
    assert "80/tcp http" in out

def test_summarize_assets_empty():
    assert summarize_assets([]) == ""

def test_render_assets_markdown_table():
    hosts = [Host(address="10.0.0.5", services=[Service(port=80, name="http", product="nginx", version="1.18")])]
    out = render_assets(hosts)
    assert "10.0.0.5" in out
    assert "80" in out and "http" in out and "nginx" in out
    assert "|" in out            # rendered as a table

def test_ports_sorted_in_summary_and_render():
    record = [Service(port=443, name="https"), Service(port=22, name="ssh"), Service(port=80, name="http")]
    hosts = [Host(address="10.0.0.5", services=record)]
    out = summarize_assets(hosts)
    assert out.index("22/tcp") < out.index("80/tcp") < out.index("443/tcp")
