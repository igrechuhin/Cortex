# Fix getting-started.md Removed Tool References and Stale Quick Start

**Status**: COMPLETE
**Priority**: CRITICAL
**Created**: 2026-02-28
**Type**: Fix
**Effort**: Medium (30 min)

## Goal

Update `docs/getting-started.md` Quick Start section to reference current tool names and the `.cortex/` storage layout, replacing references to tools that were consolidated or removed.

## Context

The Quick Start section in `docs/getting-started.md` references several tools that no longer exist after Phase 50 tool consolidation:

| Getting-started Reference | Current Equivalent |
|--------------------------|-------------------|
| `initialize_memory_bank` (line 134) | `initialize` prompt or `manage_file` |
| `validate_memory_bank` (line 194) | `validate(check_type=...)` |
| `get_quality_score` (line 304) | `validate(check_type="quality")` |
| `setup_project_structure` (line 306) | `get_structure_info()` / initialize prompt |

The Quick Start also describes creating `.memory-bank/` directory (legacy) instead of `.cortex/memory-bank/` (current), and references `.memory-bank-index` instead of `.cortex/index.json`.

## Approach

Rewrite the Quick Start section (lines 130-312) to use current tools, paths, and workflows matching README.md's Getting Started section.

## Implementation Steps

1. **Audit current tool names**: Verify the exact current equivalents by checking `src/cortex/tools/__init__.py` and tool dispatchers
2. **Rewrite section "1. Initialize a Memory Bank"** (lines 132-147):
   - Replace `initialize_memory_bank` with the `initialize` prompt workflow
   - Update directory listing from `.memory-bank/` to `.cortex/memory-bank/`
   - Remove `.memory-bank-index` reference
3. **Rewrite section "2. Set Up Project Structure"** (lines 148-166):
   - Update directory listing to `.cortex/` layout (`.cortex/memory-bank/`, `.cortex/plans/`, `.cortex/config/`)
   - Replace `.memory-bank/knowledge/` with `.cortex/memory-bank/`
4. **Rewrite section "3. Write Your First Memory Bank File"** (lines 168-188):
   - Keep content but ensure it references `.cortex/memory-bank/projectBrief.md`
5. **Rewrite section "4. Validate Your Memory Bank"** (lines 190-206):
   - Replace `validate_memory_bank` with `validate(check_type="schema")` or equivalent
6. **Keep section "5. Load Context"** (lines 207-224) as-is (already uses current `load_context` tool)
7. **Update "Common Workflows" section** (lines 226-296):
   - Line 229: `.memory-bank/knowledge/` → `.cortex/memory-bank/`
   - Line 233: `validate_memory_bank` → `validate`
   - Line 234: `get_quality_score` → `validate(check_type="quality")`
8. **Update "Next Steps" section** (line 300):
   - Replace "100+ MCP tools" with correct count (~71)
9. **Update "Tips" section** (lines 306-311):
   - Line 306: `setup_project_structure` → `initialize` prompt
   - Line 308: `validate_memory_bank` → `validate`
   - Line 309: `get_quality_score` → `validate(check_type="quality")`
10. **Cross-check with README.md** Getting Started section to ensure consistency

## Dependencies

None (can be done independently, but pairs well with `plan-docs-fix-legacy-paths.md`).

## Success Criteria

- No references to `initialize_memory_bank`, `validate_memory_bank`, `get_quality_score`, or `setup_project_structure` in getting-started.md
- All tool names match tools registered in `src/cortex/tools/__init__.py`
- All paths use `.cortex/` layout
- Quick Start is consistent with README.md Getting Started

## Testing Strategy

- **Coverage Target**: N/A (docs-only change)
- **Verification**: `grep -n "initialize_memory_bank\|validate_memory_bank\|get_quality_score\|setup_project_structure" docs/getting-started.md` returns empty
- **Regression**: No code changes

## Risks & Mitigation

- **Risk**: New tool names may have different parameter signatures → **Mitigation**: Check actual tool definitions in source

## Timeline

Single session (30 min).
