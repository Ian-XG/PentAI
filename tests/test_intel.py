from pentai.assets import Host, Service
from pentai.intel import service_intel, intel_leads, ServiceIntel

def test_service_intel_http_has_next_steps():
    intel = service_intel("http", "nginx", "1.18.0")
    assert intel.next_steps                      # non-empty
    assert any("dir" in s.lower() or "gobuster" in s.lower() for s in intel.next_steps)
    assert intel.vulns == []                     # nginx 1.18 not in the famous list

def test_service_intel_matches_vsftpd_backdoor():
    intel = service_intel("ftp", "vsftpd", "2.3.4")
    assert any("CVE-2011-2523" in v for v in intel.vulns)
    assert any("anon" in s.lower() for s in intel.next_steps)   # still gets ftp hints

def test_service_intel_version_specific_no_false_positive():
    # a non-vulnerable vsftpd version must NOT flag the backdoor
    intel = service_intel("ftp", "vsftpd", "3.0.3")
    assert intel.vulns == []

def test_service_intel_version_extension_no_false_positive():
    # a startswith() check would wrongly match these - "2.3.40" and "3.0.200"
    # are different, newer version numbers, not the vulnerable 2.3.4/3.0.20
    # with a suffix. This is the case the previous test's "3.0.3" didn't
    # actually exercise (it's not even a prefix match).
    assert service_intel("ftp", "vsftpd", "2.3.40").vulns == []
    assert service_intel("netbios-ssn", "Samba smbd", "3.0.200").vulns == []

def test_service_intel_version_suffix_still_matches():
    # a real build/variant suffix ("p1", "-Debian") of a vulnerable version
    # must still be flagged - only a continuing DIGIT means "different version".
    assert any("CVE-2011-2523" in v for v in service_intel("ftp", "vsftpd", "2.3.4p1").vulns)
    assert any("CVE-2007-2447" in v
              for v in service_intel("netbios-ssn", "Samba smbd", "3.0.20-Debian").vulns)

def test_service_intel_samba_usermap():
    intel = service_intel("netbios-ssn", "Samba smbd", "3.0.20")
    assert any("CVE-2007-2447" in v for v in intel.vulns)

def test_service_intel_apache_path_traversal():
    assert any("CVE-2021-41773" in v for v in service_intel("http", "Apache httpd", "2.4.49").vulns)
    assert any("CVE-2021-42013" in v for v in service_intel("http", "Apache httpd", "2.4.50").vulns)

def test_service_intel_unknown_service_is_empty_but_safe():
    intel = service_intel("weirdproto", "", "")
    assert isinstance(intel, ServiceIntel)
    assert intel.next_steps == [] and intel.vulns == []

def test_service_intel_matches_by_port_when_name_missing():
    # nmap sometimes leaves SERVICE blank; fall back to well-known port
    intel = service_intel("", "", "", port=445)
    assert intel.next_steps                       # smb hints from port 445

def test_intel_leads_lists_open_services_with_leads():
    hosts = [Host(address="10.0.0.5", services=[
        Service(port=21, name="ftp", product="vsftpd", version="2.3.4"),
        Service(port=80, name="http", product="nginx", version="1.18.0"),
        Service(port=3306, name="mysql", state="closed"),   # closed -> skipped
    ])]
    out = intel_leads(hosts)
    assert "10.0.0.5:21" in out and "ftp" in out
    assert "CVE-2011-2523" in out                 # known vuln surfaced
    assert "10.0.0.5:80" in out
    assert "3306" not in out                      # closed service excluded

def test_intel_leads_empty():
    assert intel_leads([]) == ""
    assert intel_leads([Host(address="10.0.0.5", services=[])]) == ""
