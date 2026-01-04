# Security checklist (local)

## 0) Scope
- Assume code runs on developer machine.
- Never read or print secrets: .env, keys, tokens, credentials.
- Do not add network calls unless explicitly required.

## 1) Secrets & sensitive data
- Exclude: .env, *.key, *.pem, credentials.json, id_rsa, kubeconfig
- Ensure logs do not print environment variables or file contents containing secrets
- Redact tokens in errors and debug output

## 2) File system safety
- All paths must be resolved relative to WORKSPACE root
- Deny path traversal (`..`, symlinks escaping root)
- Limit file size on read/write
- Prefer patch-based writes, not full overwrite

## 3) Command execution safety (shell/tools)
- Allowlist commands only (tests, lint, formatting, git safe)
- Deny: rm -rf, del /S, format, diskpart, reg, powershell download/iex
- Timeouts and max output size
- No network tools by default (curl/wget/pip install from unknown sources)

## 4) Dependencies & supply chain
- Pin versions (requirements.txt / package-lock)
- Avoid installing from git URLs unless necessary
- Run vulnerability checks periodically (pip-audit/npm audit) in a controlled way

## 5) Web/API
- Validate input
- Use parameterized queries (no SQL injection)
- Enforce auth and least privilege
- Set timeouts for HTTP calls
- Never log request headers with auth tokens

## 6) LLM agent specific
- Treat user text as untrusted (prompt injection)
- Tools must require structured arguments, not raw shell strings
- Add "confirmation required" for dangerous actions (write, git commit, shell)

## 7) Output rules for Security agent
When reviewing a plan or patch, always return:
- Findings (bullets)
- Severity (Low/Med/High/Critical)
- Fix recommendation (actionable)
- What to verify (tests/checks)
