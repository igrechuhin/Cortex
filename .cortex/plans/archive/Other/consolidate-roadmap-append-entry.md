# Plan: Consolidate roadmap + append_entry

**Status**: COMPLETE
**Priority**: P2 (medium)
**Estimated Effort**: 6–8 hours

## Goal

Reduce Cortex MCP tool count by merging `roadmap` and `append_entry` into a single `update_memory_bank` (or `mutate_memory_bank`) tool with operations for roadmap (add/remove/remove_section) and progress/activeContext append. Both are safe mutations of memory bank files.

## Context

- **roadmap**: add_entry, remove_entry, remove_section on roadmap.md.
- **append_entry**: append to progress.md or activeContext.md.
- Different targets but shared domain (memory bank mutations). Parameter sets partially overlap (entry_text, section, date_str).

**Reference**: [docs/guides/tool-description-altitude-rubric.md](../guides/tool-description-altitude-rubric.md) — target ≥ 4.

## Implementation Steps

**Implementation sequence**: Execute in order (Step 1 → 2 → … → 7).

### Step 1: Design consolidated tool API

- Tool name: `update_memory_bank` (or keep `roadmap` and extend with progress/active_context ops — evaluate naming).
- Operations: `roadmap_add`, `roadmap_remove`, `roadmap_remove_section`, `progress_append`, `active_context_append`.
- Parameters: union of roadmap and append_entry params, with operation-specific validation.

### Step 2: Implement consolidated dispatcher

- Create `update_memory_bank(operation=..., ...)` that routes to existing roadmap/append_entry logic.
- Preserve exact behavior of both tools; no semantic changes.
- Return format: match existing roadmap/append_entry result shapes per operation.

### Step 3: Register new tool, deprecate old ones

- Register `update_memory_bank` in tool_categories.py.
- Add deprecation shims for `roadmap` and `append_entry` that delegate to `update_memory_bank` with appropriate operation mapping.

### Step 4: Update callers

- Update implement prompt, memory-bank-updater agent, commit pipeline, and any Synapse agents.
- Replace `roadmap(operation="add_entry", ...)` with `update_memory_bank(operation="roadmap_add", ...)` (or equivalent).
- Replace `append_entry(operation="progress", ...)` with `update_memory_bank(operation="progress_append", ...)`.
- Update AGENTS.md, CLAUDE.md, memory-bank-workflow.mdc.

### Step 5: Remove deprecated tools

- Remove `roadmap` and `append_entry` from MCP registration (or keep as shims during transition).
- Update TOOL_CATEGORIES.

### Step 6: Tool documentation

- Write `update_memory_bank` docstring per tool-description-altitude-rubric.
- Update docs/api/tools.md.

### Step 7: Verification

- Run full pre-commit and commit pipeline.
- Verify memory bank updates (roadmap, progress, activeContext) work correctly.
- Confirm tool count reduced by 1.

## Testing Strategy

- **Coverage target**: ≥ 95% for new/modified code.
- **Unit tests**: Test each operation (roadmap_add, roadmap_remove, roadmap_remove_section, progress_append, active_context_append) produces correct file mutations.
- **Integration tests**: Test implement Step 5 (memory bank update) and commit pipeline Steps 5–6.
- **Regression**: Existing roadmap and append_entry tests must pass (or be migrated to test update_memory_bank).
- **AAA pattern**: All tests follow Arrange-Act-Assert.

## Dependencies

- None.

## Success Criteria

- Single `update_memory_bank` tool provides all roadmap and append_entry functionality.
- `roadmap` and `append_entry` removed (or thin shims).
- All callers migrated.
- Tool count reduced by 1.
- Memory bank workflows (implement, commit) pass.

## Risks & Mitigation

- **Risk**: Parameter schema becomes complex. **Mitigation**: Use operation-specific validation; document each operation clearly in tool description.
- **Risk**: Breaking memory bank updates. **Mitigation**: Keep shims during transition; comprehensive test coverage.
