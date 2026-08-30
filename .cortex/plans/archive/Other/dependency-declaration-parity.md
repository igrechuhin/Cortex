---
title: "Automate dependency parity between pyproject.toml and requirements.txt"
component: build
work_type: fix
status: PENDING
priority: Medium
created: 2026-03-21
depends_on: []
---

## Goal

Replace the manual "keep in sync" process for `pyproject.toml` and `requirements.txt` with an automated generation or CI validation step to prevent dependency drift.

## Context

- **Codex review finding #7**: Runtime dependencies are declared in both `pyproject.toml` and `requirements.txt` with a manual sync note. Manual synchronization eventually drifts.
- This is a common source of "works locally, fails in CI" issues.

## Implementation Steps

### Step 1: Evaluate generation vs validation approach

**Option A (generation)**: Script that exports `pyproject.toml` deps to `requirements.txt` (e.g., `uv pip compile pyproject.toml -o requirements.txt`).
**Option B (validation)**: CI step that compares the two and fails on drift.

Choose Option B (validation) as it preserves the current workflow and adds a safety net.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Current requirements.txt content | Root | `requirements.txt` |
| pyproject.toml dependencies | Root | `pyproject.toml` |
| CI workflow steps | `.github/workflows/` | `quality.yml` |

### Step 2: Create parity check script

Add `scripts/check_dep_parity.py` (or shell script) that parses both files and reports mismatches. Normalize package names (PEP 503) before comparison.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| PEP 503 normalization | Script | New script |

### Step 3: Add CI integration

Add a step in `quality.yml` that runs the parity check. Also add a `make check-dep-parity` target.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| New CI step | `.github/workflows/quality.yml` | Workflow file |
| New make target | `Makefile` | Makefile |

### Step 4: Document the workflow

Update `CONTRIBUTING.md` or equivalent to note that `requirements.txt` must stay in sync and CI will catch drift.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Dependency sync docs | `docs/` or `CONTRIBUTING.md` | Relevant doc |

## Dependencies

- None.

## Success Criteria

- CI fails if `requirements.txt` and `pyproject.toml` dependencies diverge.
- `make check-dep-parity` available for local use.
- Documentation updated.
- Quality gate passes.

## Testing Strategy

- Test script with intentionally mismatched deps to verify detection.
- Test with matching deps to verify clean pass.
- Target: 95% coverage maintained.
