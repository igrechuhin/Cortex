# Secret/Credential Protection Audit (2026-02-25)

Security & Resilience plan Step 4: Secret/Credential Protection.

## Scope

1. Verify no secrets in codebase
2. Verify `.gitignore` covers sensitive file patterns
3. Verify MCP tool responses never include credentials or tokens
4. Add pre-commit hook for secret detection
5. Audit logging to ensure no secrets in log output

## Findings

### 1. No secrets in codebase

- **Tool**: `detect-secrets` (v1.5.0) with baseline `.secrets.baseline`
- **Baseline**: Created via `detect-secrets scan . > .secrets.baseline`
- **Known findings** (false positives in baseline): Hex/Base64 strings in `docs/prompts/setup-synapse.md`, `tests/conftest.py`, `tests/unit/test_exceptions.py`, `tests/unit/test_version_manager.py` — example commit hashes and test fixtures, not real secrets
- **Pre-commit**: `detect-secrets` hook added; fails on new secrets not in baseline
- **Existing**: `detect-private-key` from pre-commit-hooks remains active

### 2. `.gitignore` sensitive patterns

- **Already covered**: `.env`, `.env.local`, `.env.development.local`, `.env.test.local`, `.env.production.local`
- **Added**: `*.pem`, `*.key`, `credentials.json`, `secrets.json`, `*credentials*.json`, `*secrets*.json`

### 3. MCP tool responses and credentials

- **Audit**: MCP tools return structured JSON from Pydantic `model_dump()`. No dedicated credential fields in tool responses.
- **Configuration**: `configure` and `get_config` return optimization/adaptation config. Cortex does not store API keys or passwords. User projects may have `.env` with secrets; Cortex does not read or expose those.
- **Recommendation**: Do not store secrets in Cortex config. Use environment variables for API keys; `.env` is gitignored.

### 4. Pre-commit secret detection

- **Hook**: `detect-secrets` from `https://github.com/Yelp/detect-secrets` (rev v1.5.0)
- **Args**: `["--baseline", ".secrets.baseline"]`
- **Behavior**: Compares scan to baseline; fails if new secrets detected

### 5. Logging audit

- **Format**: `[level] name  - message` (no config dumps)
- **Config load errors**: `logger.warning("Failed to load optimization config: {e}")` — exception message only, not full config
- **Pre-commit tools**: Log `health.model_dump()` for connection health (tools, semaphore) — no credential fields
- **Guidance**: Do not log full config, file content, or user input that may contain secrets. Exception messages are acceptable when they describe the error without exposing sensitive data.

## Acceptance criteria

- [x] No secrets in codebase (verify via detect-secrets; baseline captures known false positives)
- [x] Pre-commit secret scanning active (detect-secrets + detect-private-key)
- [x] `.gitignore` covers common sensitive patterns
- [x] MCP responses audited — no credential leakage
- [x] Logging audited — no secret dumps in logs
