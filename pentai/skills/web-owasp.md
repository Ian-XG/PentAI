# Web / OWASP Playbook

Focus areas (OWASP Top 10) for authorized web targets like Juice Shop:

- Injection (SQLi): test inputs with `'`, observe errors; `sqlmap -u <url> --batch`.
- XSS: reflect `<script>alert(1)</script>` in parameters; check output encoding.
- Broken access control / IDOR: change object ids, replay another user's request.
- Auth: weak passwords, JWT `alg:none`, session fixation.
- Directory and content discovery: `gobuster dir -u <url> -w <wordlist>`.

Teach: describe the vulnerability class, the impact, and the remediation for each.
