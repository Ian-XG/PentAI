from pentai.recon_parse import parse_nmap, is_nmap_command, ParsedHost, ParsedService

NMAP_BASIC = """\
Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for 10.0.0.5
Host is up (0.0010s latency).
Not shown: 997 closed tcp ports (reset)
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.5 (Ubuntu Linux; protocol 2.0)
80/tcp  open  http    nginx 1.18.0 (Ubuntu)
443/tcp closed https
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 12.34 seconds
"""

NMAP_HOSTNAME_MULTIHOST = """\
Nmap scan report for web01 (10.0.0.5)
Host is up.
PORT   STATE SERVICE
22/tcp open  ssh

Nmap scan report for 10.0.0.6
Host is up.
PORT   STATE SERVICE
21/tcp open  ftp
"""

def test_is_nmap_command():
    assert is_nmap_command("nmap -sV 10.0.0.5")
    assert is_nmap_command("sudo nmap -A target")
    assert not is_nmap_command("ls -la")
    assert not is_nmap_command("echo nmapster")   # must be the nmap binary, not a substring

def test_parse_basic_host_and_ports():
    hosts = parse_nmap(NMAP_BASIC)
    assert len(hosts) == 1
    h = hosts[0]
    assert h.address == "10.0.0.5"
    assert h.os == "Linux"
    ports = {s.port: s for s in h.services}
    assert set(ports) == {22, 80, 443}
    assert ports[22].state == "open" and ports[22].name == "ssh"
    assert ports[22].product == "OpenSSH" and ports[22].version == "8.2p1"
    assert ports[80].name == "http" and ports[80].product == "nginx" and ports[80].version == "1.18.0"
    assert ports[443].state == "closed"

def test_parse_hostname_and_multiple_hosts():
    hosts = parse_nmap(NMAP_HOSTNAME_MULTIHOST)
    assert len(hosts) == 2
    a, b = hosts
    assert a.address == "10.0.0.5" and a.hostname == "web01"
    assert a.services[0].port == 22 and a.services[0].name == "ssh"
    assert b.address == "10.0.0.6" and b.hostname == ""
    assert b.services[0].port == 21

def test_parse_ignores_noise_and_no_report():
    assert parse_nmap("just some text\nno scan here") == []
    assert parse_nmap("") == []

def test_parse_udp_and_open_filtered():
    text = ("Nmap scan report for 10.0.0.7\n"
            "PORT    STATE         SERVICE\n"
            "53/udp  open|filtered domain\n")
    h = parse_nmap(text)[0]
    assert h.services[0].proto == "udp"
    assert h.services[0].state == "open|filtered"
    assert h.services[0].port == 53

def test_parse_combined_and_unfiltered_states_not_dropped():
    # closed|filtered and unfiltered are real nmap states; earlier the regex
    # only knew open|filtered and silently dropped these port lines.
    text = ("Nmap scan report for 10.0.0.9\n"
            "PORT     STATE           SERVICE\n"
            "137/udp  closed|filtered netbios-ns\n"
            "445/tcp  unfiltered      microsoft-ds\n")
    states = {s.port: s.state for s in parse_nmap(text)[0].services}
    assert states == {137: "closed|filtered", 445: "unfiltered"}

def test_parse_multiword_product_keeps_version():
    text = ("Nmap scan report for 10.0.0.5\n"
            "PORT     STATE SERVICE VERSION\n"
            "8080/tcp open  http    Apache Tomcat 9.0.65\n")
    s = parse_nmap(text)[0].services[0]
    assert s.product == "Apache Tomcat" and s.version == "9.0.65"

def test_parse_service_without_version_leaves_product_empty():
    text = ("Nmap scan report for 10.0.0.8\n"
            "PORT   STATE SERVICE\n"
            "22/tcp open  ssh\n")
    s = parse_nmap(text)[0].services[0]
    assert s.name == "ssh" and s.product == "" and s.version == ""
