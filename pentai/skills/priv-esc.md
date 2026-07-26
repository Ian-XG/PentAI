# Privilege Escalation Playbook

After a foothold on an authorized host:

- Enumerate: `id`, `sudo -l`, `uname -a`, running services.
- Automated checks: `linpeas.sh` (Linux), `winPEAS` (Windows).
- SUID binaries: `find / -perm -4000 -type f 2>/dev/null`.
- Cron jobs and writable paths, kernel exploits matched to `uname -a`.

Teach: explain the difference between horizontal and vertical escalation and why
enumeration beats guessing.
