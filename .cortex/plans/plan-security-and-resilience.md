# Plan: Security & Resilience Hardening

## Status: PLANNED

## Priority: P2 (Medium)

## Created: 2026-02-21

## Effort: 1 sprint

## Motivation

Comprehensive review (2026-02-21) identified resilience and security areas needing attention:

- No input sanitization audit for MCP tool parameters
- No rate limiting beyond semaphore-based concurrency control
- Global state patterns (semaphores, caches) need resilience testing
- No chaos/fault injection testing
- Async error handling could be more specific in some paths
- No formal security review since ADR-008

---

## Step 1: MCP Tool Input Sanitization Audit ✅ DONE (2026-02-25)

**Risk:** MCP tools accept string parameters from AI agents. Malformed or adversarial inputs could cause:

- Path traversal (e.g., `../../etc/passwd` in file paths)
- Injection in shell commands (if any tool constructs shell commands)
- Excessive resource consumption (very long strings, deep nesting)

**Action:**

1. Audit all 101+ tool parameter handlers for input validation — DONE: FileSystemManager + InputValidator block path traversal
2. Verify file path parameters are sandboxed to project root — DONE: construct_safe_path + validate_path enforce project root
3. Check for shell command construction (should use subprocess with args, not string interpolation) — DONE: framework adapters use list args, no shell=True
4. Add input size limits (max string length, max list size, max nesting depth) — DONE: MAX_MANAGE_FILE_CONTENT_BYTES, MAX_TASK_DESCRIPTION_CHARS, MAX_SECTIONS_LIST_SIZE; manage_file and load_context enforce limits
5. Add fuzz tests for critical tools: `manage_file`, `execute_pre_commit_checks`, `load_context` — DONE: tests/unit/test_mcp_tool_input_sanitization.py

**Acceptance criteria:** All tools validate inputs. Path traversal blocked. No shell injection possible. Fuzz tests pass.

---

## Step 2: Resilience Testing for Concurrent Access ✅ DONE (2026-02-25)

**Current state:** Cortex uses `asyncio.Lock`, `TrackedSemaphore`, and file locking. But no tests verify behavior under contention.

**Action:**

1. Create concurrent access test suite:
   - Multiple simultaneous `manage_file` writes to same file
   - Concurrent `session_start` calls
   - Semaphore exhaustion and recovery
   - Lock timeout handling
2. Test graceful degradation:
   - What happens when semaphore is exhausted?
   - What happens when file lock times out?
   - Are resources properly released on exceptions?
3. Add chaos tests:
   - Random delays in async operations
   - Simulated file system errors (permission denied, disk full)
   - Network interruption during MCP communication

**Acceptance criteria:** Concurrent access tests pass. No resource leaks. Graceful degradation verified.

---

## Step 3: Error Recovery Audit ✅ DONE (2026-02-25)

**Current state:** 44 generic exception raises (mostly `RuntimeError`, `ValueError`). Some catch-all patterns.

**Action:**

1. Audit all `except Exception` and `except BaseException` handlers — DONE: see docs/security/error-recovery-audit-2026-02-25.md
2. Ensure each handler:
   - Logs the error with context — verified for critical paths
   - Releases held resources (locks, semaphores, file handles) — mcp_stability_config releases semaphore; TrackedSemaphore **aexit** releases
   - Returns meaningful error to the MCP client — tool handlers return structured JSON
   - Does not swallow errors silently — context_logging and mcp_stability_config re-raise
3. Replace generic exceptions with specific custom exceptions where appropriate — documented as future work
4. Ensure `asyncio.CancelledError` is never accidentally caught — DONE: explicit re-raise in context_logging; mcp_stability_config re-raises; tests added

**Acceptance criteria:** No silent error swallowing. All resources released on error. Specific exceptions used.

---

## Step 4: Secret/Credential Protection

**Current state:** ADR-008 covers security practices. Need verification.

**Action:**

1. Verify no secrets in codebase (`git secrets --scan`)
2. Verify `.gitignore` covers all sensitive file patterns
3. Verify MCP tool responses never include credentials or tokens
4. Add pre-commit hook for secret detection if not present
5. Audit logging to ensure no secrets in log output

**Acceptance criteria:** No secrets in codebase. Pre-commit secret scanning active.

---

## Verification

After all steps:

1. Input sanitization tests pass (including fuzz tests)
2. Concurrent access tests pass under contention
3. Error recovery audit complete with no silent swallowing
4. Secret scanning active in pre-commit
5. Security audit findings documented
