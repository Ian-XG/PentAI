"""Offline service intelligence. For a discovered service, PentAI suggests the
highest-signal next recon/exploitation step and flags a small, curated set of
famous version-specific vulnerabilities. Injected into the agent's context as
"recon leads" so it always knows the next move.

Deliberately OFFLINE and local: no CVE-API lookups that would leak the target's
software stack to a third party. The known-vuln set is small, famous, and stable
- correctness over coverage. The agent still verifies before reporting."""
from dataclasses import dataclass, field

# next-step hints keyed by nmap service name (lowercased)
_SERVICE_HINTS: dict[str, list[str]] = {
    "ssh": ["grab the banner for the exact version", "check for weak/default creds",
            "OpenSSH < 7.7 allows username enumeration (CVE-2018-15473)"],
    "ftp": ["try anonymous login (anonymous:anonymous)", "check write access for a webshell drop"],
    "http": ["gobuster/feroxbuster dir enum", "nikto scan", "check /robots.txt and default creds"],
    "https": ["gobuster dir enum over TLS", "inspect the cert for hostnames/subdomains", "nikto -ssl"],
    "http-proxy": ["test for open proxy / SSRF", "check Tomcat /manager with default creds"],
    "smb": ["enum4linux-ng", "smbclient -L //target/ -N (null session)", "check for EternalBlue (MS17-010)"],
    "microsoft-ds": ["enum4linux-ng", "smbclient -L //target/ -N", "check MS17-010 (EternalBlue)"],
    "netbios-ssn": ["enum4linux-ng", "smbclient -L //target/ -N (null session)"],
    "telnet": ["grab banner", "try default/weak creds - traffic is cleartext"],
    "mysql": ["try root with empty/weak password", "check for anonymous access"],
    "ms-sql-s": ["try sa with weak password", "xp_cmdshell if you get in"],
    "postgresql": ["try postgres with weak/default creds"],
    "ms-wbt-server": ["check NLA; try cred spray carefully", "screenshot the login (rdesktop/xfreerdp)"],
    "rdp": ["check NLA; BlueKeep (CVE-2019-0708) on old Windows"],
    "vnc": ["check for no-auth / weak password", "vncviewer to peek"],
    "redis": ["unauthenticated access? try redis-cli, then webshell/SSH key write"],
    "mongodb": ["check for unauthenticated access"],
    "smtp": ["VRFY/EXPN user enumeration", "check for open relay"],
    "snmp": ["snmpwalk with 'public' community string"],
    "ldap": ["anonymous bind + ldapsearch to dump the directory"],
    "rpcbind": ["rpcinfo -p; check for NFS exports (showmount -e)"],
    "nfs": ["showmount -e; mount exports and look for keys/creds"],
    "domain": ["try a zone transfer (dig axfr)", "enumerate subdomains"],
    "dns": ["try a zone transfer (dig axfr @target domain)"],
}

# nmap SERVICE is sometimes blank; fall back to the well-known port
_PORT_TO_SERVICE: dict[int, str] = {
    22: "ssh", 21: "ftp", 23: "telnet", 25: "smtp", 53: "domain", 80: "http",
    110: "pop3", 139: "netbios-ssn", 143: "imap", 443: "https", 445: "microsoft-ds",
    1433: "ms-sql-s", 3306: "mysql", 3389: "ms-wbt-server", 5432: "postgresql",
    5900: "vnc", 6379: "redis", 27017: "mongodb", 161: "snmp", 389: "ldap",
    111: "rpcbind", 2049: "nfs", 8080: "http-proxy",
}

# curated, famous, version-specific vulns. (product-substring, exact-version-prefix, note)
_KNOWN_VULNS: list[tuple[str, str, str]] = [
    ("vsftpd", "2.3.4", "vsftpd 2.3.4 has a backdoor root shell (CVE-2011-2523) - metasploit vsftpd_234_backdoor"),
    ("proftpd", "1.3.3c", "ProFTPD 1.3.3c shipped with a backdoor (OSVDB-69562)"),
    ("proftpd", "1.3.5", "ProFTPD 1.3.5 mod_copy RCE (CVE-2015-3306) - SITE CPFR/CPTO"),
    ("samba", "3.0.20", "Samba 3.0.20-3.0.25 usermap_script command injection (CVE-2007-2447)"),
    ("samba", "3.0.21", "Samba 3.0.20-3.0.25 usermap_script command injection (CVE-2007-2447)"),
    ("samba", "3.0.22", "Samba 3.0.20-3.0.25 usermap_script command injection (CVE-2007-2447)"),
    ("samba", "3.0.23", "Samba 3.0.20-3.0.25 usermap_script command injection (CVE-2007-2447)"),
    ("samba", "3.0.24", "Samba 3.0.20-3.0.25 usermap_script command injection (CVE-2007-2447)"),
    ("samba", "3.0.25", "Samba 3.0.20-3.0.25 usermap_script command injection (CVE-2007-2447)"),
    ("unrealircd", "3.2.8.1", "UnrealIRCd 3.2.8.1 backdoor (CVE-2010-2075)"),
    ("apache", "2.4.49", "Apache httpd 2.4.49 path traversal -> RCE (CVE-2021-41773)"),
    ("apache", "2.4.50", "Apache httpd 2.4.50 path traversal -> RCE (CVE-2021-42013)"),
    ("distcc", "", "distccd allows remote command execution (CVE-2004-2687)"),
]

@dataclass
class ServiceIntel:
    next_steps: list[str] = field(default_factory=list)
    vulns: list[str] = field(default_factory=list)

def _version_matches(v: str, ver_prefix: str) -> bool:
    """True if v IS ver_prefix, or a variant/build of it (a suffix like
    "p1"/"-ubuntu"/"a") - but not a different, longer version number that
    merely starts with the same digits. "2.3.4" and "2.3.4p1" both match
    prefix "2.3.4"; "2.3.40" does not (a plain startswith() would wrongly
    match it too - the char right after the prefix decides: a digit means
    it's a different version, anything else (or nothing) means a variant)."""
    if not v.startswith(ver_prefix):
        return False
    rest = v[len(ver_prefix):]
    return not rest or not rest[0].isdigit()

def _known_vulns(product: str, version: str) -> list[str]:
    p = (product or "").lower()
    v = (version or "").strip()
    out = []
    for prod_sub, ver_prefix, note in _KNOWN_VULNS:
        if prod_sub not in p:
            continue
        if ver_prefix and not _version_matches(v, ver_prefix):
            continue
        out.append(note)
    return out

def service_intel(service: str, product: str = "", version: str = "",
                  *, port: int | None = None) -> ServiceIntel:
    name = (service or "").lower()
    if name not in _SERVICE_HINTS and port is not None:
        name = _PORT_TO_SERVICE.get(port, name)
    return ServiceIntel(next_steps=list(_SERVICE_HINTS.get(name, [])),
                        vulns=_known_vulns(product, version))

def intel_leads(hosts) -> str:
    """One compact lead line per open service: the top next step, plus any known
    vuln flag. Fed into the agent's context so it always knows the next move."""
    lines: list[str] = []
    for h in hosts:
        for s in h.services:
            if "open" not in s.state:
                continue
            intel = service_intel(s.name, s.product, s.version, port=s.port)
            if not intel.next_steps and not intel.vulns:
                continue
            lead = f"{h.address}:{s.port} {s.name or _PORT_TO_SERVICE.get(s.port, '?')}"
            if intel.next_steps:
                lead += f" -> {intel.next_steps[0]}"
            if intel.vulns:
                lead += "  | KNOWN: " + "; ".join(intel.vulns)
            lines.append(lead)
    return "\n".join(lines)
