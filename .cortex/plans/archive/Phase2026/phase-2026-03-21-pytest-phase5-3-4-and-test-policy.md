---
title: "Convert tests/test_phase5_3_4.py to pytest and guard against script-only test files"
component: testing
work_type: remediation
status: PENDING
priority: P1
created: 2026-03-21
depends_on: []
sources:
  - "Comprehensive Project Review — 2026-03-21 (audit)"
  - tests/test_phase5_3_4.py
---

## Goal

Ensure **Phase 5.3–5.4** execution/learning paths are covered by **collected pytest tests**, and prevent new **`tests/test_*.py`** files from being **script-only** (`if __name__ == "__main__"`) without an explicit, reviewed exception.

## Context

- `tests/test_phase5_3_4.py` documents that it is script-style and wraps logic under `__main__`, so **pytest never runs** those checks.
- File name and location imply CI coverage; refactors can ship without regression signal.

## Implementation steps

1. **Extract behaviors** — List discrete behaviors under `__main__`: imports, `AdaptationConfig`, `ApprovalManager`, `LearningEngine`, and any integration-style checks. Map each to a pytest function or class.
2. **Convert to pytest** — Use fixtures (`tmp_path` if needed), `pytest.mark.asyncio` where async, and **AAA** structure. Remove `print`/`sys.exit` from test paths; use assertions and `pytest.raises` where appropriate.
3. **Module-level side effects** — If “import smoke” is required, use a minimal `def test_phase5_3_4_imports()` that imports the public modules (or use lazy imports only inside tests to avoid collection cost if needed).
4. **Relocation alternative** — If conversion is staged: interim move to a non-collected path (e.g. under `docs/` manual scripts is wrong; prefer `tests/manual/` only if repo policy allows — **default: stay in `tests/` and convert**).
5. **Policy guard** — Add a lightweight test or pre-commit/ruff-adjacent check that flags new `tests/test_*.py` files where **no test functions are collected** (only `__main__` body). Document allowed exceptions in the check’s docstring.
6. **Interim skip (only if conversion split)** — If keeping file temporarily: module-level `pytest.skip("Tracked in phase-2026-03-21-pytest-phase5-3-4-and-test-policy.md", allow_module_level=True)` with link — **prefer full conversion over permanent skip.**

## Verification checklist (per step)

| Step | What to search for | Scope | Re-read |
|------|---------------------|--------|---------|
| 2 | `def test_`, `pytest.mark` | `tests/test_phase5_3_4.py` | pytest collection list |
| 5 | `__main__`, `collect` | `tests/`, new guard test | `pytest --collect-only` |
| 6 | `pytest.skip` | same file | Should be absent in final state |

## Dependencies

- Understanding of `cortex.refactoring.*` APIs and any env requirements for learning features.

## Success criteria

- `pytest tests/test_phase5_3_4.py` runs **non-empty** collected tests; all pass in CI.
- No `tests/test_*.py` relies solely on `__main__` for its assertions (except documented exclusions in the guard).
- Guard fails CI if a new script-style test file is added.

## Testing strategy (95%+ coverage target for new code)

- Target **≥95% line coverage** on newly exercised `cortex.refactoring` branches touched by converted tests.
- Add parametrized tests for config edge cases (threshold bounds, learning rate enums) where logic exists.
