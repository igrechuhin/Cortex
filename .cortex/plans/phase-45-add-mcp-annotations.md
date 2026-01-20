# Phase 45: Add Comprehensive MCP Annotations

**Status**: PLANNING  
**Created**: 2026-01-17  
**Priority**: Medium  
**Estimated Effort**: 12-15 hours

## Overview

Add MCP annotations to all Cortex MCP tools to improve discoverability, usability, and semantic clarity for client applications. MCP annotations provide metadata about tool behavior (read-only, destructive, idempotent, etc.) without consuming token context in LLM prompts.

**Reference**: <https://gofastmcp.com/servers/tools#mcp-annotations>

## Context

### Current State

- **53+ tools** across 34+ files
- All tools use `@mcp.tool()` decorator without annotations
- Tools are wrapped with `@mcp_tool_wrapper()` for stability (timeouts, failure protocol)
- FastMCP 2.0 in use (migrated in Phase 41)
- Return types are mixed: `dict[str, object]`, `TypedDict`, and some Pydantic models

### Related Work

- **Phase 41**: FastMCP 2.0 migration completed
- **Phase 43**: Reconsider tools registration (Tools vs Resources semantic alignment)
- **Phase 44**: Migrate to Pydantic structured output (ongoing)
- **Phase 29**: Track MCP tool usage (no annotations currently tracked)

## Goals

1. **Add MCP annotations** to all 53+ tools with appropriate metadata
2. **Improve tool discoverability** for client applications
3. **Enable better tool categorization** (read-only, destructive, idempotent, etc.)
4. **Maintain backward compatibility** with existing tool behavior
5. **Document annotation patterns** for future tools

## MCP Annotations Reference

### Standard Annotations

From FastMCP documentation:

1. **`title`** (str): Human-readable title for the tool
   - Example: `"Calculate Sum"`, `"Search Products"`

2. **`readOnlyHint`** (bool): Indicates tool only reads data (no side effects)
   - `True`: Tool is read-only (GET-like)
   - `False`: Tool may modify state (POST-like)
   - Default: `False`

3. **`destructiveHint`** (bool): Indicates tool may cause destructive changes
   - `True`: Tool can delete, overwrite, or permanently modify data
   - `False`: Tool is safe or only creates/updates
   - Default: `False`

4. **`idempotentHint`** (bool): Indicates tool produces same result for repeated calls
   - `True`: Calling with same parameters produces identical results
   - `False`: Tool may produce different results on repeated calls
   - Default: `False`

5. **`openWorldHint`** (bool): Indicates tool accesses external data sources
   - `True`: Tool accesses external APIs, databases, or network resources
   - `False`: Tool only accesses internal/local data
   - Default: `False`

### Annotation Patterns

```python
# Read-only query tool
@mcp.tool(
    annotations={
        "title": "Get Memory Bank Statistics",
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False
    }
)

# Safe write operation (creates/updates, not destructive)
@mcp.tool(
    annotations={
        "title": "Manage Memory Bank File",
        "readOnlyHint": False,
        "destructiveHint": False,  # write operation, but safe
        "idempotentHint": False,   # write creates new version
        "openWorldHint": False
    }
)

# Destructive operation
@mcp.tool(
    annotations={
        "title": "Rollback File Version",
        "readOnlyHint": False,
        "destructiveHint": True,  # overwrites current version
        "idempotentHint": False,
        "openWorldHint": False
    }
)

# External API call
@mcp.tool(
    annotations={
        "title": "Execute Pre-Commit Checks",
        "readOnlyHint": False,
        "destructiveHint": False,  # may modify files, but safe
        "idempotentHint": False,
        "openWorldHint": True      # runs external commands
    }
)
```

## Implementation Plan

### Phase 1: Tool Categorization (Analysis)

**Goal**: Categorize all 53+ tools by their behavior patterns

**Tasks**:

1. Audit all tools in `src/cortex/tools/` directory
2. Categorize each tool by:
   - **Read-only** (queries, stats, validation checks)
   - **Safe writes** (create, update, append operations)
   - **Destructive** (delete, overwrite, rollback operations)
   - **External** (network calls, subprocess execution)
   - **Idempotent** (same inputs = same outputs)
3. Create annotation mapping spreadsheet/document

**Files to Review**:

- `src/cortex/tools/__init__.py` (tool registry)
- All `src/cortex/tools/*.py` files (34+ files)

**Estimated Time**: 2-3 hours

### Phase 2: Annotation Helper Utilities

**Goal**: Create reusable utilities for consistent annotation patterns

**Tasks**:

1. Create `src/cortex/core/mcp_annotations.py` with:
   - Annotation type definitions (TypedDict or dataclass)
   - Helper functions for common patterns:
     - `read_only_annotations(title: str) -> dict`
     - `safe_write_annotations(title: str) -> dict`
     - `destructive_annotations(title: str) -> dict`
     - `external_annotations(title: str) -> dict`
   - Validation function to ensure annotations are valid

**Example**:

```python
from typing import TypedDict

class ToolAnnotations(TypedDict, total=False):
    """MCP tool annotations."""
    title: str
    readOnlyHint: bool
    destructiveHint: bool
    idempotentHint: bool
    openWorldHint: bool

def read_only_annotations(title: str) -> ToolAnnotations:
    """Create annotations for read-only tools."""
    return {
        "title": title,
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    }
```

**Estimated Time**: 1 hour

### Phase 3: Add Annotations to Core Tools (Priority 1)

**Goal**: Add annotations to most frequently used tools

**Priority Tools** (based on usage patterns):

1. **File Operations** (`file_operations.py`):
   - `manage_file` - Safe write (write creates new version)
2. **Stats & Analytics** (`phase1_foundation_stats.py`):
   - `get_memory_bank_stats` - Read-only, idempotent
3. **Validation** (`validation_operations.py`):
   - `validate` - Read-only, idempotent
4. **Analysis** (`analysis_operations.py`):
   - `analyze_usage_patterns` - Read-only, idempotent
   - `analyze_structure` - Read-only, idempotent
   - `analyze_insights` - Read-only, idempotent
5. **Configuration** (`configuration_operations.py`):
   - `configure` - Safe write (updates config)
6. **Version History** (`phase1_foundation_version.py`):
   - `get_version_history` - Read-only, idempotent
   - `rollback_file_version` - Destructive (overwrites current version)

**Estimated Time**: 2-3 hours

### Phase 4: Add Annotations to Secondary Tools (Priority 2)

**Goal**: Add annotations to remaining tools

**Tools by Category**:

**Read-Only Tools**:

- `get_dependency_graph` - Read-only, idempotent
- `get_link_graph` - Read-only, idempotent
- `parse_file_links` - Read-only, idempotent
- `validate_links` - Read-only, idempotent
- `resolve_transclusions` - Read-only, idempotent
- `get_relevance_scores` - Read-only, idempotent
- `get_memory_bank_stats` - Read-only, idempotent
- `get_version_history` - Read-only, idempotent
- `get_structure_info` - Read-only, idempotent
- `check_structure_health` - Read-only, idempotent
- `check_mcp_connection_health` - Read-only, idempotent
- `get_synapse_rules` - Read-only, idempotent, open-world (reads from git)
- `get_synapse_prompts` - Read-only, idempotent, open-world (reads from git)

**Safe Write Tools**:

- `manage_file` (write operation) - Safe write, not idempotent
- `configure` - Safe write, not idempotent
- `fix_markdown_lint` - Safe write (fixes files), not idempotent
- `fix_quality_issues` - Safe write (fixes files), not idempotent
- `fix_roadmap_corruption` - Safe write (fixes files), not idempotent
- `cleanup_metadata_index` - Safe write (removes stale entries), not idempotent
- `apply_refactoring` - Safe write (applies refactoring), not idempotent
- `provide_feedback` - Safe write (records feedback), not idempotent
- `update_synapse_rule` - Safe write, open-world (writes to git)
- `update_synapse_prompt` - Safe write, open-world (writes to git)

**Destructive Tools**:

- `rollback_file_version` - Destructive (overwrites current version)
- `apply_refactoring` (with rollback action) - Destructive (restores from snapshot)

**External/Open-World Tools**:

- `execute_pre_commit_checks` - External (runs subprocess commands), not idempotent
- `fix_quality_issues` - External (runs subprocess commands), not idempotent
- `sync_synapse` - External (git pull/push), not idempotent
- `get_synapse_rules` - Open-world (reads from git submodule)
- `get_synapse_prompts` - Open-world (reads from git submodule)
- `update_synapse_rule` - Open-world (writes to git submodule)
- `update_synapse_prompt` - Open-world (writes to git submodule)

**Complex Tools** (may have multiple behaviors):

- `optimize_context` - Read-only, idempotent
- `load_progressive_context` - Read-only, idempotent
- `summarize_content` - Safe write (creates summary), not idempotent
- `suggest_refactoring` - Read-only, idempotent
- `check_structure_health` (with cleanup) - Safe write (performs cleanup), not idempotent

**Estimated Time**: 4-5 hours

### Phase 5: Testing & Validation

**Goal**: Ensure annotations are correctly applied and don't break functionality

**Tasks**:

1. Run existing test suite to ensure no regressions
2. Verify annotations are properly serialized in MCP protocol
3. Test with MCP client to verify annotations are exposed correctly
4. Update documentation with annotation patterns

**Test Files**:

- `tests/tools/test_*.py` (all tool tests)
- Integration tests in `tests/integration/`

**Estimated Time**: 2-3 hours

### Phase 6: Documentation

**Goal**: Document annotation patterns and guidelines

**Tasks**:

1. Update `docs/api/tools.md` with annotation information
2. Add annotation guidelines to `docs/guides/advanced/extension-development.md`
3. Create annotation decision tree/flowchart
4. Update tool registration examples

**Estimated Time**: 1-2 hours

## Tool Annotation Mapping

### File Operations (`file_operations.py`)

- `manage_file`:
  - **read**: `readOnlyHint=True`, `idempotentHint=True`
  - **write**: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`
  - **metadata**: `readOnlyHint=True`, `idempotentHint=True`

### Foundation Tools (`phase1_foundation_*.py`)

- `get_memory_bank_stats`: `readOnlyHint=True`, `idempotentHint=True`
- `get_version_history`: `readOnlyHint=True`, `idempotentHint=True`
- `rollback_file_version`: `readOnlyHint=False`, `destructiveHint=True`, `idempotentHint=False`
- `get_dependency_graph`: `readOnlyHint=True`, `idempotentHint=True`
- `cleanup_metadata_index`: `readOnlyHint=False`, `destructiveHint=False` (removes stale entries), `idempotentHint=False`

### Validation Tools (`validation_operations.py`)

- `validate`: `readOnlyHint=True`, `idempotentHint=True` (same inputs = same validation results)

### Analysis Tools (`analysis_operations.py`)

- `analyze_usage_patterns`: `readOnlyHint=True`, `idempotentHint=True`
- `analyze_structure`: `readOnlyHint=True`, `idempotentHint=True`
- `analyze_insights`: `readOnlyHint=True`, `idempotentHint=True`

### Configuration Tools (`configuration_operations.py`)

- `configure`: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`

### Link Operations (`link_*.py`)

- `parse_file_links`: `readOnlyHint=True`, `idempotentHint=True`
- `validate_links`: `readOnlyHint=True`, `idempotentHint=True`
- `get_link_graph`: `readOnlyHint=True`, `idempotentHint=True`

### Transclusion Operations (`transclusion_operations.py`)

- `resolve_transclusions`: `readOnlyHint=True`, `idempotentHint=True`

### Optimization Tools (`phase4_optimization_handlers.py`)

- `optimize_context`: `readOnlyHint=True`, `idempotentHint=True`
- `load_progressive_context`: `readOnlyHint=True`, `idempotentHint=True`
- `summarize_content`: `readOnlyHint=False`, `destructiveHint=False` (creates summary), `idempotentHint=False`
- `get_relevance_scores`: `readOnlyHint=True`, `idempotentHint=True`

### Refactoring Tools (`refactoring_operations.py`)

- `suggest_refactoring`: `readOnlyHint=True`, `idempotentHint=True`
- `apply_refactoring`:
  - **approve**: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`
  - **apply**: `readOnlyHint=False`, `destructiveHint=False` (applies refactoring), `idempotentHint=False`
  - **rollback**: `readOnlyHint=False`, `destructiveHint=True` (restores from snapshot), `idempotentHint=False`
- `provide_feedback`: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`

### Markdown Operations (`markdown_operations.py`)

- `fix_markdown_lint`: `readOnlyHint=False`, `destructiveHint=False` (fixes files), `idempotentHint=False`

### Pre-Commit Tools (`pre_commit_tools.py`)

- `execute_pre_commit_checks`: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`, `openWorldHint=True` (runs subprocess)
- `fix_quality_issues`: `readOnlyHint=False`, `destructiveHint=False` (fixes files), `idempotentHint=False`, `openWorldHint=True` (runs subprocess)

### Structure Tools (`phase8_structure.py`)

- `get_structure_info`: `readOnlyHint=True`, `idempotentHint=True`
- `check_structure_health`:
  - **check-only**: `readOnlyHint=True`, `idempotentHint=True`
  - **with cleanup**: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`

### Connection Health (`connection_health.py`)

- `check_mcp_connection_health`: `readOnlyHint=True`, `idempotentHint=False` (state may change)

### Rules Operations (`rules_operations.py`)

- `rules` (index): `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`
- `rules` (get_relevant): `readOnlyHint=True`, `idempotentHint=True`

### Synapse Tools (`synapse_*.py`)

- `get_synapse_rules`: `readOnlyHint=True`, `idempotentHint=True`, `openWorldHint=True` (reads from git)
- `get_synapse_prompts`: `readOnlyHint=True`, `idempotentHint=True`, `openWorldHint=True` (reads from git)
- `sync_synapse`: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`, `openWorldHint=True` (git pull/push)
- `update_synapse_rule`: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`, `openWorldHint=True` (writes to git)
- `update_synapse_prompt`: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`, `openWorldHint=True` (writes to git)

### Execution Tools (`phase5_execution.py`)

- Tools in this module (review individually)

## Implementation Notes

### Decorator Order

Current pattern:

```python
@mcp.tool()
@mcp_tool_wrapper(timeout=...)
async def tool_function(...):
    ...
```

With annotations:

```python
@mcp.tool(
    annotations={
        "title": "Tool Title",
        "readOnlyHint": True,
        ...
    }
)
@mcp_tool_wrapper(timeout=...)
async def tool_function(...):
    ...
```

### Conditional Annotations

Some tools have different behaviors based on parameters (e.g., `manage_file` with `operation="read"` vs `operation="write"`). For these:

- Use the **most permissive** annotation (e.g., if tool can write, set `readOnlyHint=False`)
- Document parameter-specific behavior in docstring
- Consider splitting into separate tools if behavior is significantly different

### Title Guidelines

- Use clear, descriptive titles
- Match tool function name or primary purpose
- Keep titles concise (50 chars or less recommended)
- Use title case (e.g., "Get Memory Bank Statistics")

## Success Criteria

1. ✅ All 53+ tools have appropriate MCP annotations
2. ✅ Annotations are validated and consistent across tools
3. ✅ No regressions in existing functionality
4. ✅ Documentation updated with annotation patterns
5. ✅ Helper utilities created for future tool development
6. ✅ Annotations are properly exposed via MCP protocol

## Risks & Mitigations

### Risk 1: Annotation Inconsistency

- **Mitigation**: Use helper functions for common patterns, code review checklist

### Risk 2: Breaking Changes

- **Mitigation**: Annotations are additive metadata, shouldn't break existing clients

### Risk 3: Performance Impact

- **Mitigation**: Annotations are static metadata, minimal performance impact

### Risk 4: Maintenance Overhead

- **Mitigation**: Document patterns clearly, use helper functions, add to code review checklist

## Dependencies

- FastMCP 2.0 (already migrated in Phase 41)
- Existing tool structure (no breaking changes required)

## Related Plans

- **Phase 43**: Reconsider tools registration (Tools vs Resources)
- **Phase 44**: Migrate to Pydantic structured output
- **Phase 29**: Track MCP tool usage (could track annotation usage)

## Timeline

- **Phase 1**: Tool Categorization - 2-3 hours
- **Phase 2**: Annotation Helper Utilities - 1 hour
- **Phase 3**: Core Tools Annotations - 2-3 hours
- **Phase 4**: Secondary Tools Annotations - 4-5 hours
- **Phase 5**: Testing & Validation - 2-3 hours
- **Phase 6**: Documentation - 1-2 hours

**Total Estimated Time**: 12-15 hours

## Next Steps

1. Review and approve this plan
2. Begin Phase 1: Tool Categorization
3. Create annotation helper utilities
4. Systematically add annotations to all tools
5. Test and validate
6. Update documentation
