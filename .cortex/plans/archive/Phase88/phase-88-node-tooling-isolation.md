# Phase 88: Node Tooling Dependency Isolation

**Status**: COMPLETE
**Priority**: Medium
**Complexity**: Medium
**Category**: Fix / Infrastructure

## Goal

Move Node.js-based tooling (markdownlint, etc.) from global/external dependencies to pinned, project-local dev dependencies. Add offline-friendly bootstrap guidance.

## Context

- Project review (2026-03-05): "Lint/test bootstrap requires downloading dependencies and globally installing some Node tooling. In restricted or proxied environments this introduces frequent false negatives."
- `markdownlint` and potentially other Node tools are required for the quality pipeline but are not managed as project dependencies.
- Network failures during `npm install` cause quality gate false negatives that are hard to distinguish from actual lint failures.

## Implementation Steps

### Step 1: Inventory Node dependencies

- Identify all Node.js tools used in the quality pipeline.
- Check how they are currently installed (global, npx, local).

### Step 2: Add package.json with pinned versions

- Create `package.json` with exact pinned versions of required Node tools.
- Add `node_modules/` to `.gitignore` if not already present.
- Add `npm ci` to the bootstrap script.

### Step 3: Update tool invocations

- Change quality scripts to use `npx` with local `node_modules` rather than global commands.
- Ensure `Makefile` targets install Node deps if missing.

### Step 4: Separate environment failures from quality failures

- In quality gate scripts, detect and report "tool not installed" separately from "lint errors found."
- Add clear error messages: "markdownlint not found — run `make bootstrap` first."

### Step 5: Add offline guidance

- Document how to pre-cache Node dependencies for restricted environments.
- Add `npm cache` instructions to CONTRIBUTING or bootstrap docs.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `package.json` | Project root | Exists with pinned Node deps |
| Global npm install | CI workflow + scripts | Zero global installs |

## Dependencies

- Phase 79 (bootstrap script) — incorporate Node deps into bootstrap.

## Success Criteria

- All Node tools installed from project-local `package.json`.
- No global npm installs in CI or scripts.
- Quality gate clearly distinguishes "tool missing" from "lint failure."
- Bootstrap script installs both Python and Node dependencies.

## Testing Strategy

- **Coverage Target**: N/A (infrastructure).
- **Manual verification**: Run quality checks with and without Node tools installed.
- **CI verification**: CI installs from `package.json` not globally.

## Risks & Mitigation

- **Risk**: Node version compatibility. **Mitigation**: Pin Node version in `.node-version` or engines field.

## Timeline

- Estimated: 2–3 hours.
