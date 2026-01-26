# Phase 53 Blocker: Investigate `fix_quality_issues` failing with "'CheckResult' object is not subscriptable"

**Date:** 2026-01-24  
**Status:** 🟢 COMPLETE  
**Priority:** ASAP (blocks mandatory agent workflow)

---

## Problem

Calling the MCP tool `fix_quality_issues()` fails at runtime with:

- `"'CheckResult' object is not subscriptable"`

Repro (local, via Python):

- `./.venv/bin/python -c "import asyncio; from cortex.tools.pre_commit_tools import fix_quality_issues; print(asyncio.run(fix_quality_issues(project_root='...')))"`  

Observed output is a structured JSON error with `error_message` set to the exception string.

---

## Why this matters

Repo agent rules require automatically invoking `fix_quality_issues()`:

- after code changes
- when IDE errors are detected
- before starting new work

So this failure is a **workflow blocker** and must be tracked + fixed.

---

## Hypothesis (most likely)

`fix_quality_issues()` expects JSON-decoded dicts for nested check results, but the underlying `execute_pre_commit_checks()` may be returning nested `CheckResult` objects (or a structure containing them) at some boundary, leading to dict-style access on a `CheckResult` instance.

---

## Investigation steps

1. Add a minimal failing reproduction in a unit test (or extend existing tests in `tests/unit/test_pre_commit_tools.py`) to capture this exact exception path without mocks.
2. Inspect `execute_pre_commit_checks()` response construction:
   - confirm what `adapter.fix_errors()`, `adapter.format_code()`, `adapter.type_check()` return (Pydantic model vs plain dataclass vs dict)
   - confirm `PreCommitResult.model_dump()` produces JSON-serializable primitives for nested results
3. Identify the exact subscripting site:
   - likely in `_extract_fix_statistics()` / `_extract_check_results()` or in JSON serialization of the results
4. Fix by ensuring `execute_pre_commit_checks()` serializes nested results to JSON-safe dicts before returning:
   - e.g. normalize `CheckResult` / `TestResult` / `QualityCheckResult` to `dict[str, JsonValue]` using `model_dump()` when they are Pydantic models
5. Validate:
   - `fix_quality_issues()` returns `status="success"` (or a meaningful `"error"` with actionable message)
   - the existing mocked tests still pass
   - add a new test covering the real (non-mocked) shape if feasible

---

## Exit criteria

- `fix_quality_issues()` runs successfully in a local `.venv` environment for this repo.
- Unit tests cover the regression.
- No type ignores / suppressions added.

---

## Resolution (2026-01-25)

- Local `.venv` invocation of `fix_quality_issues()` no longer reproduces the `"'CheckResult' object is not subscriptable"` failure.
- Keep/extend regression coverage in `tests/unit/test_pre_commit_tools.py` to prevent reintroduction.
