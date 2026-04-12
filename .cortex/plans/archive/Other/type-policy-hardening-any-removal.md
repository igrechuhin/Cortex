---
title: "Type Policy Hardening: Remove Any from Production Code"
component: quality
work_type: refactor
status: PENDING
priority: high
created: 2026-04-12
depends_on: []
---

## Type Policy Hardening: Remove `Any` from Production Code

## Goal

Remove all `typing.Any` usage from `src/cortex/tools/execution/pre_commit_status.py` by replacing return types with Pydantic `BaseModel` or narrower unions. Then add a linting/typing guard to prevent `Any` from re-entering `src/` outside an explicit allowlist.

## Context

**Finding (Review 2026-04-12, Issue #3 — High)**

- AGENTS policy and `.cortex/synapse/` rules both forbid `typing.Any` and mandate `object`/Pydantic models.
- `src/cortex/tools/execution/pre_commit_status.py` imports `Any` and returns `dict[str, Any]` in multiple methods.
- This weakens type guarantees and sends mixed signals to contributors about whether the policy is truly enforced.

**Policy source of truth**: `cortex://rules` resource + `.cortex/synapse/` rules (read via MCP, not directly).

## Implementation Steps

### Step 1: Audit `pre_commit_status.py` for `Any` usage

1. Read `src/cortex/tools/execution/pre_commit_status.py` in full.
2. Identify every `Any` occurrence: method signatures, return types, intermediate variables.
3. For each occurrence, classify replacement strategy:
   - Structured result → new `BaseModel` subclass
   - Union of known types → `str | int | bool | None` or similar
   - Opaque external data → `object` with explicit cast at boundary
4. Document the classification in a short analysis comment before writing code.

**Verification checklist:**

- `rg "Any" src/cortex/tools/execution/pre_commit_status.py` — list all hits.
- Re-read file after listing to understand call sites.

### Step 2: Define typed models for structured results

1. Read `cortex://rules` resource to confirm Pydantic 2 conventions (field validators, `model_config`, etc.).
2. For each `dict[str, Any]` return that represents a structured result, create a `BaseModel` in the same file or in a sibling `_models.py` file (whichever keeps file ≤400 lines).
3. Use descriptive field names; add `model_config = ConfigDict(frozen=True)` where immutability is appropriate.
4. Keep each model ≤ one logical concept; no model files > 400 lines.

**Verification checklist:**

- After writing models: `rg "class.*BaseModel" src/cortex/tools/execution/` confirms new types.
- `rg "Any" src/cortex/tools/execution/pre_commit_status.py` returns zero results.

### Step 3: Refactor methods to use typed models

1. Update all method signatures in `pre_commit_status.py` to return typed models.
2. Replace `dict[str, Any]` constructions with `ModelClass(field=value, ...)` instantiation.
3. Update all call sites within `src/` that receive these return values to use the typed fields.
4. Ensure functions remain ≤30 lines; extract helpers if needed.

**Verification checklist:**

- Re-read all changed methods; confirm no `Any` remains.
- Search: `rg "Any" src/cortex/tools/execution/` for zero results.
- Search callers: `rg "pre_commit_status" src/` and verify each call site is updated.

### Step 4: Update and expand tests

1. Read existing tests for `pre_commit_status.py` (likely in `tests/unit/tools/execution/`).
2. Update test assertions to use typed model attributes instead of dict key access.
3. Add new tests covering the new model shapes, including invalid-input edge cases.
4. Verify coverage ≥95% for modified files.

**Verification checklist:**

- `run_quality_gate()` — all tests green, coverage target met.
- `rg "dict\[str, Any\]" tests/unit/tools/execution/test_pre_commit_status.py` — zero results.

### Step 5: Add lint/CI guard against `Any` re-entry

1. Check `pyproject.toml` / `ruff.toml` for existing `flake8-builtins`, `flake8-annotations`, or ruff rules.
2. Add a ruff rule or pyright config to flag `typing.Any` usage in `src/` — use `warn_return_any = true` and `disallow_any_generics = true` in pyright `strict` mode config, or add a ruff `ANN401` rule.
3. If an allowlist is needed (e.g., for third-party type stubs), document it with a `# noqa: ANN401  # allowlisted: <reason>` comment.
4. Confirm `run_quality_gate()` catches violations on a deliberate `Any` re-introduction (manual test in a scratch branch or via code comment).

**Verification checklist:**

- Re-read `pyproject.toml` after changes.
- `run_quality_gate()` — all green.
- `rg "\bAny\b" src/` filtered by `[^#]` context produces zero non-allowlisted hits.

## Dependencies

- `src/cortex/tools/execution/pre_commit_status.py` — primary target
- `cortex://rules` resource — Pydantic 2 conventions
- `pyproject.toml` / `ruff.toml` — lint config targets
- All call sites discovered in Step 1/3

## Success Criteria

- `rg "\bAny\b" src/cortex/tools/execution/pre_commit_status.py` returns zero results.
- `rg "\bfrom typing import.*Any\b" src/` returns zero non-allowlisted results.
- `run_quality_gate()` green.
- All new types are Pydantic `BaseModel` subclasses with 100% field type coverage.
- Existing tests pass; new tests cover typed model fields.

## Testing Strategy

- **Unit tests** (`tests/unit/tools/execution/test_pre_commit_status.py`): update to assert typed model attributes; add edge-case tests for malformed inputs. Target 95%+ coverage on changed files.
- **Static analysis**: `run_quality_gate()` includes pyright strict — validates no `Any` escapes.
- **Regression**: no changes to behavior, only types — existing integration tests must pass unchanged.
