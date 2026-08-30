---
title: "README Tool Inventory Parity Fix"
component: documentation
work_type: fix
status: PENDING
priority: High
created: 2026-04-12
depends_on: []
---

## README Tool Inventory Parity Fix

## Goal

Align the `README.md` "Key Tools" section with the canonical 12-tool inventory in `docs/api/tools.md` and `src/cortex/tools/structure/categories.py`, then add a CI/doc test asserting parity with `docs/_generated/tool-inventory.json`.

## Context

### Finding (Review 2026-04-12, Issue #1 — High)

- `README.md` states Cortex exposes **12 MCP tools** but its "Key Tools" table omits `compress_memory_bank`.
- `docs/api/tools.md` (canonical section) lists all 12 including `compress_memory_bank`.
- `src/cortex/tools/structure/categories.py` sets `MAX_REGISTERED_TOOLS = 12` and includes `compress_memory_bank` in `TOOL_CATEGORIES`.
- New users and agents can operate with incomplete tool awareness, leading to manual workarounds instead of using the right tool.

**Note**: `AGENTS.md` also lists only 11 tools (omits `compress_memory_bank`). This plan should update `AGENTS.md` alongside `README.md`.

**Authoritative sources** (in priority order):

1. `src/cortex/tools/structure/categories.py` — `TOOL_CATEGORIES` dict (12 entries)
2. `docs/api/tools.md` — narrative canonical section
3. `docs/_generated/tool-inventory.json` — generated inventory (may need to be created/regenerated)

## Implementation Steps

### Step 1: Audit current README "Key Tools" table

1. Read `README.md` fully; locate "Key Tools" section and extract listed tool names.
2. Read `src/cortex/tools/structure/categories.py`; extract `TOOL_CATEGORIES` keys as the authoritative list.
3. Read `docs/api/tools.md`; extract listed tools from its canonical section.
4. Produce a diff: tools in categories but missing from README, and vice-versa.

**Verification checklist:**

- Search: `rg "compress_memory_bank|Key Tools|MCP tools" README.md`
- Search scope: `README.md`, `docs/api/tools.md`
- Re-read: `src/cortex/tools/structure/categories.py` for `TOOL_CATEGORIES` and `MAX_REGISTERED_TOOLS`

### Step 2: Update README "Key Tools" table

1. Replace/extend the "Key Tools" table in `README.md` so it lists all 12 tools exactly matching `TOOL_CATEGORIES` keys.
2. Include a one-line description for each tool consistent with `docs/api/tools.md`.
3. Preserve all other README content untouched.

**Verification checklist:**

- After edit: `rg -c "\\|" README.md` table rows should match tool count.
- Re-read changed section to confirm no truncation.

### Step 3: Update AGENTS.md tool table

1. Read `AGENTS.md` "Tools" table (currently lists 11 tools, missing `compress_memory_bank`).
2. Add `compress_memory_bank` with its one-line description from `TOOL_CATEGORIES`.
3. Update the heading count from "11" to "12".

**Verification checklist:**

- `rg "compress_memory_bank" AGENTS.md` — at least one match.
- Tool count in heading matches `TOOL_CATEGORIES` length (12).

### Step 4: Ensure `docs/_generated/tool-inventory.json` exists and is current

1. Check if `docs/_generated/tool-inventory.json` exists.
2. If absent: identify or create a script/fixture that serializes `TOOL_CATEGORIES` to that JSON file. Place generation logic in `scripts/generate_tool_inventory.py` (new file) or find existing generator.
3. If present: verify it matches current `TOOL_CATEGORIES`; update if stale.

**Verification checklist:**

- `Glob` on `docs/_generated/` for existing files.
- Re-read `tool-inventory.json` after generation to confirm all 12 tools present.

### Step 5: Add parity test

1. Create or locate a test file for documentation parity (e.g., `tests/docs/test_tool_inventory_parity.py`).
2. Write a test that:
   - Imports `TOOL_CATEGORIES` from `src/cortex/tools/structure/categories.py`.
   - Reads `docs/_generated/tool-inventory.json`.
   - Asserts all category keys are present in the JSON and counts match.
   - Reads `README.md` and asserts each tool name appears in the Key Tools section.
3. Test must pass with `run_quality_gate()`.

**Verification checklist:**

- Run `run_quality_gate()` — all tests green.
- Search: `rg "tool_inventory_parity" tests/` confirms test exists.

### Step 6: (Optional) Add CI enforcement

1. Evaluate whether a GitHub Actions step should run the parity test on every PR.
2. If yes: add a step in `.github/workflows/` that runs only the parity test fast.
3. Document in `docs/api/tools.md` that the parity test is the source of truth.

**Verification checklist:**

- Re-read relevant workflow file to confirm step is present.

## Dependencies

- `src/cortex/tools/structure/categories.py` — `TOOL_CATEGORIES` (read-only)
- `docs/api/tools.md` — canonical narrative (read-only reference)
- `README.md` — target of update
- `AGENTS.md` — target of update (tool table)
- `docs/_generated/` — may need directory creation

## Success Criteria

- `README.md` "Key Tools" section lists exactly 12 tools, matching `TOOL_CATEGORIES` names.
- `AGENTS.md` "Tools" table lists exactly 12 tools, matching `TOOL_CATEGORIES` names.
- `docs/_generated/tool-inventory.json` exists and contains all 12 tools.
- Parity test passes: `rg "\bcompress_memory_bank\b" README.md` returns at least one match.
- `run_quality_gate()` green.
- No `Any` type introduced in new test code.

## Testing Strategy

- **Unit test** (`tests/docs/test_tool_inventory_parity.py`): assert README lists all tools from `TOOL_CATEGORIES`; assert JSON inventory matches categories. Target 95%+ coverage on new code.
- **Integration**: parity test runs as part of existing test suite via `run_quality_gate()`.
- No mocks needed — this is a static content test.
