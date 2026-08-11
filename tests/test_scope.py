from pentai.scope import extract_targets, Scope

def test_extract_ip_and_host():
    t = extract_targets("nmap -sV 10.0.0.5 http://juice.local/rest")
    assert "10.0.0.5" in t
    assert "juice.local" in t

def test_extract_ignores_local_filenames():
    # dotted filenames are not targets - they must not trip the OOS warning
    for cmd in ["cat report.txt", "bash linpeas.sh", "python exploit.py",
                "gobuster -o out.json", "ls -la scan.xml", "sqlmap -r req.log"]:
        assert extract_targets(cmd) == [], cmd

def test_extract_keeps_real_hosts_alongside_files():
    t = extract_targets("nmap -oN scan.txt juice.local example.com")
    assert "juice.local" in t and "example.com" in t
    assert "scan.txt" not in t

def test_out_of_scope_ignores_output_filename():
    s = Scope(["10.0.0.0/24"])
    # writing an output file next to an in-scope scan must not warn
    assert s.out_of_scope("nmap 10.0.0.5 -oN results.txt") == []

def test_cidr_membership():
    s = Scope(["10.0.0.0/24"])
    assert s.contains("10.0.0.5")
    assert not s.contains("10.0.1.5")

def test_domain_glob():
    s = Scope(["*.juice.local"])
    assert s.contains("api.juice.local")
    assert not s.contains("evil.com")

def test_out_of_scope_lists_uncovered():
    s = Scope(["10.0.0.0/24"])
    assert s.out_of_scope("nmap 10.0.0.5 1.2.3.4") == ["1.2.3.4"]

def test_scope_add_normalizes_url_to_host():
    s = Scope([])
    s.add("https://workforce-os.app/foo")
    assert s.entries == ["workforce-os.app"]
    assert s.contains("workforce-os.app")
    assert s.out_of_scope("dig +short workforce-os.app") == []

def test_scope_add_preserves_cidr():
    s = Scope([])
    s.add("10.0.0.0/24")
    assert s.entries == ["10.0.0.0/24"]
    assert s.contains("10.0.0.5")
