# Recon Playbook

Goal: map the attack surface before touching anything loud.

1. Host discovery: `nmap -sn <cidr>` to find live hosts.
2. Port and service scan: `nmap -sV -sC <target>` for versions and default scripts.
3. Full TCP sweep when time allows: `nmap -p- <target>`.
4. Web fingerprint: `whatweb <url>`, `curl -sI <url>`.
5. DNS and subdomains (authorized scope only): `dig`, `subfinder -d <domain>`.

Teach: explain why service versions matter (they map to known CVEs) and why you
start quiet before going loud.
