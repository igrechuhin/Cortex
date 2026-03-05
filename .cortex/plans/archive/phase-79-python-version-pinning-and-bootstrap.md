# Phase 79: Fix Python Version Pinning and Bootstrap Script

**Status**: PENDING
**Priority**: High
**Complexity**: Low
**Category**: Fix / Infrastructure

## Goal

Eliminate environment bootstrap friction caused by exact patch-level Python pin (`3.13.6`) conflicting with the broader `>=3.13` project requirement. Provide a single-command bootstrap path.

## Context

- `.python-version` pins `3.13.6`, but `pyproject.toml` requires `>=3.13`.
- Fresh machines or CI runners that only have `3.13.7` or `3.13.8` fail to bootstrap.
- The project review (2026-03-05) classified this as **High severity**.
- Multiple chat sessions showed test execution blocked by interpreter/version setup.

## Approach

1. Relax `.python-version` from `3.13.6` to `3.13` (minor pin).
2. Create a `scripts/bootstrap.sh` that runs `uv python install 3.13 && uv sync --group dev --extra dev`.
3. Add a preflight check in `Makefile` (or existing scripts) that detects interpreter mismatch and prints remediation.
4. Update README quickstart and contributing docs to reference the bootstrap script.
5. Ensure CI workflow uses the same bootstrap path.

## Implementation Steps

### Step 1: Relax Python version pin

- Change `.python-version` from `3.13.6` to `3.13`.
- Verify `pyproject.toml` requires-python is still compatible.

### Step 2: Create bootstrap script

- Create `scripts/bootstrap.sh` with `uv python install 3.13 && uv sync --group dev --extra dev`.
- Make it executable.

### Step 3: Add Makefile preflight

- Add `make bootstrap` target that calls the script.
- Add interpreter version check to `make check` / `make test` that prints a clear error message on mismatch.

### Step 4: Update documentation

- Update README quickstart section.
- Update CONTRIBUTING or developer setup docs.

### Step 5: Align CI

- Ensure CI workflow references the same bootstrap command.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `3.13.6` | Full repo | Zero matches (except git history) |
| `bootstrap` | README.md | At least one reference |

## Dependencies

- None.

## Success Criteria

- `.python-version` contains `3.13` (minor only).
- `scripts/bootstrap.sh` exists and works on a clean machine.
- README references the bootstrap command.
- CI uses the same bootstrap path.

## Testing Strategy

- **Coverage Target**: N/A (infrastructure only)
- **Manual verification**: Run bootstrap on a clean venv and confirm `uv run pytest` works.

## Risks & Mitigation

- **Risk**: Some tool hardcodes `3.13.6`. **Mitigation**: Grep for `3.13.6` across full repo.

## Timeline

- Estimated: 1 hour.
