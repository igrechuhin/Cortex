---
title: "Add URL scheme validation to preflight registry probe"
component: cli
work_type: security
status: PENDING
priority: Low
created: 2026-03-22
depends_on: []
covers:
  - REV-2026-03-22-3
---

## Plan: Add URL scheme Validation to Preflight Registry Probe

### Goal

Prevent `UV_INDEX_URL` from being set to a non-HTTP(S) URL (e.g., `file://`, `ftp://`,
`ldap://`) that would be passed directly to `urlopen`, which could allow unintended
local file reads or non-HTTP protocol probes in restricted or adversarial environments.

### Context

**REV-2026-03-22-3 — Missing URL scheme guard (reports T18-17 and T18-27):**

`src/cortex/cli/preflight.py:20–25`, function `resolve_registry_url`:

```python
def resolve_registry_url() -> str:
    """Return ``UV_INDEX_URL`` if set and non-empty after strip, else PyPI default."""
    raw = os.environ.get(UV_INDEX_ENV, "").strip()
    if raw:
        return raw
    return DEFAULT_REGISTRY_URL
```

The returned value is passed to `_probe_with_method` → `Request(url, ...)` → `urlopen`.
Python's `urlopen` supports `file://`, `ftp://`, and other schemes. If `UV_INDEX_URL`
is set to `file:///etc/passwd` (e.g., by a CI environment variable injection or a
misconfigured `.env` file), the probe silently reads a local file.

The fix is a single scheme-prefix guard in `resolve_registry_url`: if the env-var value
does not start with `https://` or `http://`, fall back to the default PyPI URL (or raise
a `ValueError` — falling back is less disruptive for CI pipelines; raising is more
explicit for security auditing; choose the approach that fits project conventions).

The recommended approach is **raise `ValueError`** with a clear message so the operator
knows the configuration is rejected, rather than silently ignoring a potentially
intentional override.

### Implementation Steps

#### Step 1 — Add scheme guard in `resolve_registry_url`

**File:** `src/cortex/cli/preflight.py`
**Location:** lines 20–25

Replace the body of `resolve_registry_url` so that a non-HTTP(S) URL value is rejected:

```python
ALLOWED_SCHEMES = ("https://", "http://")

def resolve_registry_url() -> str:
    """Return ``UV_INDEX_URL`` if set and non-empty after strip, else PyPI default.

    Raises:
        ValueError: If ``UV_INDEX_URL`` is set but does not start with ``https://``
            or ``http://``.
    """
    raw = os.environ.get(UV_INDEX_ENV, "").strip()
    if not raw:
        return DEFAULT_REGISTRY_URL
    if not raw.startswith(ALLOWED_SCHEMES):
        raise ValueError(
            f"UV_INDEX_URL must start with 'https://' or 'http://'; got: {raw!r}"
        )
    return raw
```

Alternatively, if silent fallback is preferred over raising:

```python
    if not raw.startswith(ALLOWED_SCHEMES):
        import warnings
        warnings.warn(
            f"UV_INDEX_URL has unsupported scheme; falling back to default. Got: {raw!r}",
            stacklevel=2,
        )
        return DEFAULT_REGISTRY_URL
    return raw
```

**Decision gate for implementer:** Confirm project convention with the security
best-practices doc at `docs/security/best-practices.md` before choosing raise vs.
fallback. The `raise ValueError` approach is more auditable.

Also update `main()` to catch `ValueError` from `resolve_registry_url` and print a
diagnostic message with exit code `2`:

```python
def main() -> int:
    try:
        url = resolve_registry_url()
    except ValueError as exc:
        print(f"[FAIL] Invalid registry URL: {exc}")
        return 2
    ...
```

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `ALLOWED_SCHEMES` constant defined | `preflight.py:14–20` | same |
| `startswith(ALLOWED_SCHEMES)` guard in `resolve_registry_url` | `preflight.py:20–40` | same |
| `main()` catches `ValueError` | `preflight.py:73–86` | same |
| No new imports needed (all stdlib) | `preflight.py:1–15` | same |

---

#### Step 2 — Add / update unit tests for scheme validation

**File:** `tests/test_preflight.py`

The file already contains `test_resolve_registry_url_default`,
`test_resolve_registry_url_from_env`, and `test_resolve_registry_url_empty_env_uses_default`.
Add:

1. `test_resolve_registry_url_rejects_file_scheme` — set `UV_INDEX_URL=file:///etc/passwd`;
   assert `ValueError` is raised with a message mentioning the bad scheme.
2. `test_resolve_registry_url_rejects_ftp_scheme` — set `UV_INDEX_URL=ftp://internal/`;
   assert `ValueError` is raised.
3. `test_resolve_registry_url_accepts_https` — set `UV_INDEX_URL=https://my.registry/simple/`;
   assert the value is returned unchanged.
4. `test_resolve_registry_url_accepts_http` — set `UV_INDEX_URL=http://internal.registry/`;
   assert the value is returned unchanged.
5. `test_main_invalid_url_scheme` — set `UV_INDEX_URL=file:///tmp/`;
   call `main()`; assert return value is `2` and stdout contains `"[FAIL]"`.

If the silent-fallback approach is chosen instead of raising, adjust tests accordingly
(assert return value is `DEFAULT_REGISTRY_URL` and a warning is emitted).

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `test_resolve_registry_url_rejects_file_scheme` present | `tests/test_preflight.py` | full file |
| `test_main_invalid_url_scheme` present | same | same |
| All 5 new tests pass | `run_quality_gate()` | N/A |

---

#### Step 3 — Run quality gate

After changes and tests, run `run_quality_gate()`. Confirm:

- Zero ruff/pyright/black violations.
- All existing preflight tests still pass.
- `resolve_registry_url` coverage reaches 95%+.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `run_quality_gate()` passes | MCP output | N/A |
| Security score maintained at 8/10 | review notes | N/A |

---

### Dependencies

- No upstream dependency.
- Independent of Plan A, Plan B, Plan D.
- Review `docs/security/best-practices.md` before choosing raise vs. fallback approach.

### Success Criteria

1. `resolve_registry_url` rejects any `UV_INDEX_URL` value that does not start with
   `https://` or `http://`.
2. The rejection is visible to the operator (either `ValueError` or a warning + fallback
   logged to stdout/stderr).
3. `main()` handles the rejection gracefully with exit code `2`.
4. Five new tests added and passing.
5. `run_quality_gate()` passes with zero new violations.
6. Security score: maintained at 8/10 (no regression).

### Testing Strategy

- **Coverage target:** 95% on `resolve_registry_url` and `main`.
- **Pattern:** AAA; each test is independent.
- **Mocking:** `monkeypatch.setenv` for `UV_INDEX_URL`; `capsys` for stdout capture
  in `test_main_invalid_url_scheme`.
- **No subprocess or network calls needed** — all scheme validation is pure logic.
- **Regression guard:** Existing `test_registry_reachable_*` tests must still pass
  unchanged after this modification.
