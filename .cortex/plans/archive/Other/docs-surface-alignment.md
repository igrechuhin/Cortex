---
title: "Align docs/index.md with canonical 10-tool inventory"
component: documentation
work_type: fix
status: PENDING
priority: High
created: 2026-03-21
depends_on: []
---

## Goal

Remove stale "70+ MCP tools" claim in `docs/index.md` and align all top-level documentation pages with the canonical published surface (10 tools, 6 resources, up to 4 prompts).

## Context

- `docs/index.md:95` states "MCP Tools Reference - 70+ MCP tools" — this is the legacy surface before Phase 5.3-5.4 consolidation.
- Canonical inventory: `README.md:158` (`<!-- cortex-published-inventory: tools=10 resources=6 prompts-max=4 -->`), `docs/api/tools.md:7` ("10 tools and 6 static resources").
- New contributors may target removed/legacy entrypoints.
- `docs/index.md` also references a phase-based taxonomy (Phase 1-8) that no longer reflects the current architecture.

## Implementation Steps

### Step 1: Update docs/index.md tool reference

- **File**: `docs/index.md:95`
- **Before**: `[MCP Tools Reference](./api/tools.md) - 70+ MCP tools`
- **After**: `[MCP Tools Reference](./api/tools.md) - 10 MCP tools, 6 static resources`
- Add HTML comment marker for automated drift detection: `<!-- cortex-published-inventory: tools=10 resources=6 -->`

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `70+` or `70` in markdown files | `docs/*.md`, `docs/**/*.md` | `docs/index.md` |
| `cortex-published-inventory` comment | `docs/index.md` | `docs/index.md`, `README.md` |

### Step 2: Review and update phase-based descriptions

- **File**: `docs/index.md:25-85` (Key Features section)
- Audit each Phase 1-8 description against current codebase reality
- Replace removed/legacy feature descriptions with current capabilities
- Keep section structure but update content to match current architecture

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Phase references in docs | `docs/index.md` | `docs/index.md`, `docs/api/tools.md` |
| Tool names mentioned in descriptions | `docs/index.md` | `src/cortex/tools/structure/categories.py` |

### Step 3: Cross-check other docs pages for stale tool counts

- Grep all `docs/**/*.md` for numeric tool counts (`\d+ tools`, `\d+ MCP`)
- Fix any that don't match canonical 10/6/4 numbers
- Exclude `docs/` archive paths

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `\d+ tools` or `\d+ MCP` patterns | `docs/**/*.md` | Any files with stale counts |

## Dependencies

None.

## Success Criteria

- Zero occurrences of "70+ tools" in non-archive docs
- `docs/index.md` tool reference matches `README.md` and `docs/api/tools.md` canonical counts
- All top-level docs pages reference consistent tool/resource numbers

## Testing Strategy

- `uv run rumdl check docs/index.md` passes (no markdown lint issues introduced)
- Grep for stale counts returns zero matches in non-archive docs
- Existing `test_tool_categories_governance.py` continues to pass (tool inventory parity)
- Target: 95%+ coverage maintained (no new source code, so coverage unchanged)
