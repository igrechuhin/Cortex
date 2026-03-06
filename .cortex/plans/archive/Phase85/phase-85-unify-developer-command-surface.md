# Phase 85: Unify Developer Command Surface

**Status**: PENDING
**Priority**: Medium
**Complexity**: Medium
**Category**: Fix / Documentation

## Goal

Consolidate the fragmented developer command surface so that README, Makefile, CI, and AGENTS.md all reference the same canonical commands. Eliminate "works in CI but not locally" behavior.

## Context

- README/manual setup, Make targets, and CI commands use overlapping but not fully unified command surfaces.
- Different `uv sync` variants and different quality entry points across docs.
- CI calls Synapse scripts directly; developers use Make targets or raw pytest; AGENTS.md references Cortex MCP tools.
- Project review (2026-03-05): "command drift increases support overhead."

## Approach

1. Define one canonical developer command set.
2. Make CI call the same canonical wrappers.
3. Add a docs consistency check.

## Implementation Steps

### Step 1: Audit current command surfaces

- Catalog all commands in README.md, Makefile, CI workflow YAML, and AGENTS.md.
- Identify overlaps, divergences, and gaps.
- Note which commands are canonical vs shortcuts.

### Step 2: Define canonical commands

- `make bootstrap` — Install Python, sync dependencies.
- `make check` — Run all quality checks (format, lint, types, quality).
- `make test` — Run tests with coverage.
- `make commit-check` — Full pre-commit validation (Phase A + B).
- Document each command's exact behavior.

### Step 3: Update Makefile

- Ensure each canonical command delegates to the correct underlying tool.
- Remove or alias any deprecated targets.

### Step 4: Update CI

- Replace raw script invocations with `make check`, `make test`, etc.
- Ensure CI and local produce identical results.

### Step 5: Update documentation

- Unify README, CONTRIBUTING, and AGENTS.md to reference canonical commands.
- Remove or mark deprecated command references.

### Step 6: Add consistency check

- Create a script or test that validates README/CI/Makefile command references are consistent.
- Add to CI as a lint check.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `uv sync` variants | README + CI + Makefile | Only canonical form |
| `make check` | CI workflow | Present |

## Dependencies

- Phase 79 (bootstrap script) should land first.
- Phase 80 (Synapse guard) should land first.

## Success Criteria

- One canonical command set used across README, Makefile, CI, and AGENTS.md.
- CI passes using the same Make targets developers use locally.
- No diverging `uv sync` variants across documentation.

## Testing Strategy

- **Coverage Target**: N/A (documentation/infrastructure).
- **Manual verification**: Follow README setup instructions on a clean machine.
- **CI verification**: CI uses same Make targets as documented.

## Risks & Mitigation

- **Risk**: CI-specific environment needs differ from local. **Mitigation**: Use environment variables in Make targets for CI overrides.

## Timeline

- Estimated: 3–4 hours.
