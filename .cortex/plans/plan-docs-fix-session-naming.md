# Fix Session Function Naming Inconsistency in AGENTS.md

**Status**: PENDING
**Priority**: MEDIUM
**Created**: 2026-02-28
**Type**: Fix
**Effort**: Small (10 min)

## Goal

Resolve the inconsistent session function naming in `AGENTS.md` where both `session(operation="start")` and `session_start()` are used interchangeably.

## Context

`AGENTS.md` uses two different names for the session start function:

- Line 53: `session(operation="start")` — dispatcher syntax
- Line 90: `session_start()` — legacy direct function name
- Line 110: `session_start()` — legacy direct function name

Both exist in source code (`session_dispatcher.py` has `session()` dispatcher; `session_start_tools.py` has the legacy entry point). The dispatcher syntax `session(operation="start")` is the canonical form. `CLAUDE.md` consistently uses the dispatcher syntax. `README.md` uses `session_start()`.

## Approach

Standardize on one name across all files. The dispatcher `session(operation="start")` is the canonical tool; `session_start()` is the user-facing shorthand shown in README. Pick one per context.

## Implementation Steps

1. **Decide canonical names**:
   - For **agent instructions** (CLAUDE.md, AGENTS.md): use `session(operation="start")` (MCP dispatcher syntax)
   - For **user-facing docs** (README.md): keep `session_start()` (simpler)
2. **Update AGENTS.md**:
   - Line 90: `session_start()` → `session(operation="start")` (or note both work)
   - Line 110: `session_start()` → `session(operation="start")`
3. **Verify CLAUDE.md** is already consistent (it is)
4. **Verify README.md** — keep `session_start()` for user simplicity, but add note that it's equivalent to `session(operation="start")`

## Dependencies

None.

## Success Criteria

- AGENTS.md uses consistent session naming throughout
- CLAUDE.md and AGENTS.md are aligned
- README.md is clear for end users

## Testing Strategy

- **Coverage Target**: N/A (docs-only change)
- **Verification**: Manual review of all session references
- **Regression**: No code changes

## Risks & Mitigation

None.

## Timeline

Single session (10 min).
