---
title: "Narrow broad exception handlers — plans completion I/O and core migration"
component: python-quality
work_type: refactor
status: PENDING
priority: Medium
created: 2026-03-21
depends_on: []
sources:
  - .cortex/reviews/code-review-report-2026-03-21T11-18.md
---

## Goal

Reduce **`except Exception`** (and silent failure risk) on **plans completion I/O** and **core migration** paths by catching **specific exceptions**, preserving structured logging, and re-raising or mapping to typed errors where appropriate.

## Context

- Code review flagged: `src/cortex/tools/plans/completion_io.py` (multiple handlers), `src/cortex/core/migration.py` (migration and rollback paths).
- Project rules favor narrow catches so `ValidationError` / programming errors are not swallowed.

## Implementation steps

1. **Audit call sites** — For each `except Exception` in scope, list possible failures: `OSError`, `json.JSONDecodeError`, `UnicodeDecodeError`, `pydantic.ValidationError`, `KeyError`, etc.
2. **completion_io.py** — Replace broad catches with specific tuples per operation; ensure user-facing tool responses remain stable (same JSON shape).
3. **migration.py** — Classify rollback errors vs primary errors; log `rollback_error` with context; avoid nested bare `except Exception` masking the original failure.
4. **Tests** — Add tests that simulate `JSONDecodeError`, permission errors, and invalid payloads; assert correct error classification and no silent success.
5. **Logging** — Verify no sensitive paths or payloads in log messages; use `exc_info=True` where stack traces help operators.

## Verification checklist (per step)

| Step | What to search for | Scope | Re-read |
|------|---------------------|--------|---------|
| 1 | `except Exception` | two modules | grep after change |
| 4 | `pytest` | `tests/tools/`, `tests/` migration | coverage on branches |

## Dependencies

- None.

## Success criteria

- No remaining bare `except Exception` in the edited functions unless explicitly justified with comment + test (e.g. top-level telemetry guard).
- Tests cover at least one failure path per public handler touched.

## Testing strategy (95%+ coverage target for new code)

- Aim for **≥95%** on new/changed branches in `completion_io.py` and migration helpers; use `tmp_path` and monkeypatch for I/O faults.
