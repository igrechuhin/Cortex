# Phase 80: Add Synapse Submodule Presence Guard

**Status**: PENDING
**Priority**: High
**Complexity**: Low
**Category**: Fix / Infrastructure

## Goal

Prevent cryptic CI/local failures when `.cortex/synapse` submodule is not initialized. Add fast-fail guards with actionable error messages.

## Context

- The quality workflow invokes scripts under `.cortex/synapse/scripts/python/...`.
- If submodule is not initialized (shallow clone, skipped `--recurse-submodules`), checks fail with non-obvious errors.
- Project review (2026-03-05) classified this as **High severity**.
- Chat sessions showed agents repeatedly encountering missing tool descriptor paths.

## Approach

1. Add a guard function that checks `.cortex/synapse` is populated.
2. Wire the guard into CI workflow as an early step.
3. Add fallback native commands for critical checks when Synapse is unavailable.
4. Document the submodule requirement prominently in README quickstart.

## Implementation Steps

### Step 1: Create guard script

- Create `scripts/check_synapse.sh` (or add to bootstrap) that verifies `.cortex/synapse/scripts` directory is non-empty.
- Print clear remediation message: `git submodule update --init --recursive`.
- Exit with code 1 on failure.

### Step 2: Wire into CI

- Add guard as first step in `.github/workflows/quality.yml` (before any Synapse script invocation).

### Step 3: Wire into local tooling

- Add guard to `Makefile` check/test targets.
- Add guard to pre-commit checks if applicable.

### Step 4: Add fallback commands

- For critical checks (format, lint), provide native `ruff`/`black` fallback when Synapse scripts are unavailable.
- Log warning that Synapse is preferred.

### Step 5: Update README

- Add submodule requirement to quickstart section (not just deep docs).

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `submodule` | README.md | At least one mention in quickstart |
| `check_synapse` or submodule guard | CI workflow | Present as early step |

## Dependencies

- None.

## Success Criteria

- CI fails fast with a clear message when Synapse submodule is missing.
- Local `make check` fails fast with actionable message.
- README quickstart mentions submodule initialization.

## Testing Strategy

- **Coverage Target**: N/A (infrastructure/scripts)
- **Manual verification**: Clone without `--recurse-submodules`, run `make check`, verify clear error.

## Risks & Mitigation

- **Risk**: Fallback commands diverge from Synapse scripts. **Mitigation**: Only provide fallbacks for formatting/linting; full pipeline still requires Synapse.

## Timeline

- Estimated: 1–2 hours.
