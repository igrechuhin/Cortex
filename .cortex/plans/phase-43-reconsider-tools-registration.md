# Phase 43: Reconsider Tools Registration - Transform Tools to Resources

**Status**: PLANNING  
**Created**: 2026-01-17  
**Priority**: Medium  
**Estimated Effort**: 20-30 hours

## Goal

Reconsider and optimize MCP tool registration by transforming read-only operations from Tools to Resources, aligning with MCP protocol best practices. Resources are like GET endpoints (load information into LLM context), while Tools are like POST endpoints (execute code or produce side effects).

## Context

### User-Provided Context

The user has read the FastMCP documentation (<https://gofastmcp.com/getting-started/welcome#what-is-mcp>) and identified that MCP servers can:

- **Expose data through Resources** (think of these sort of like GET endpoints; they are used to load information into the LLM's context)
- **Provide functionality through Tools** (sort of like POST endpoints; they are used to execute code or otherwise produce a side effect)
- **Define interaction patterns through Prompts** (reusable templates for LLM interactions)

### Current State

- Cortex MCP server has **53+ tools** all registered as `@mcp.tool()` decorators
- **0 Resources** currently registered (verified via `list_mcp_resources()`)
- All operations, whether read-only or write operations, are exposed as Tools
- FastMCP 2.0 migration completed (Phase 41), which supports both Tools and Resources
- Tools are organized across 21+ modules in `src/cortex/tools/`

### Problem Statement

Current tool registration doesn't align with MCP protocol semantics:

1. **Semantic Misalignment**: Read-only operations (like `get_memory_bank_stats`, `get_version_history`) are registered as Tools when they should be Resources
2. **Protocol Best Practices**: MCP protocol distinguishes between Resources (GET-like) and Tools (POST-like) for good reason - better semantic clarity
3. **Performance**: Resources may have different caching/optimization opportunities than Tools
4. **API Clarity**: Clearer distinction between read operations (Resources) and write operations (Tools) improves API usability

### Business Value

- **Protocol Compliance**: Align with MCP protocol best practices and semantic intent
- **API Clarity**: Clearer distinction between read and write operations
- **Performance**: Potential optimization opportunities for read-only Resources
- **Documentation**: Better API documentation with proper Resource vs Tool categorization
- **Future-Proofing**: Align with MCP protocol evolution and FastMCP 2.0 capabilities

## Approach

### High-Level Strategy

1. **Audit Phase**: Categorize all 53+ tools as Resource vs Tool candidates
2. **Design Phase**: Design Resource API using FastMCP 2.0 syntax, handle hybrid operations
3. **Implementation Phase**: Implement Resources for read-only operations
4. **Migration Phase**: Migrate read-only Tools to Resources with backward compatibility
5. **Verification Phase**: Test all Resources work correctly, verify Tools still work

### Decision Criteria

**Resource Candidates (Read-Only, No Side Effects):**

- Operations that only read data
- No file writes or modifications
- No configuration changes
- No state mutations
- Load information into LLM context
- Examples: `get_memory_bank_stats`, `get_version_history`, `parse_file_links`, `validate_links`, `analyze`

**Tool Candidates (Write Operations, Side Effects):**

- Operations that write files
- Operations that modify configuration
- Operations that change state
- Operations that execute actions
- Examples: `manage_file` (write), `configure` (update), `apply_refactoring`, `rollback_file_version`

**Hybrid Operations (Need Special Handling):**

- Operations that can do both read and write based on parameters
- Examples: `manage_file` (read vs write), `configure` (view vs update)
- Strategy: Split into separate Resource (read) and Tool (write) operations, or use operation parameter

## Implementation Steps

### Step 1: Audit All Tools (4-6 hours)

#### Task 1.1: Inventory All Tools

- List all 53+ tools currently registered
- Document each tool's purpose and operation type
- Create spreadsheet or markdown table with categorization

#### Task 1.2: Categorize Each Tool

- For each tool, determine:
  - Is it read-only? → Resource candidate
  - Does it have side effects? → Tool candidate
  - Is it hybrid? → Needs special handling
- Document decision rationale for each tool

#### Task 1.3: Identify Hybrid Operations

- List tools that can do both read and write
- Examples:
  - `manage_file`: read operation → Resource, write operation → Tool
  - `configure`: view → Resource, update → Tool
- Design strategy for each hybrid operation

**Deliverables:**

- Complete tool inventory with categorization
- Decision matrix (Resource vs Tool vs Hybrid)
- List of hybrid operations with proposed handling strategy

### Step 2: Design Resource API (3-4 hours)

#### Task 2.1: Research FastMCP 2.0 Resource Support

- Verify FastMCP 2.0 supports `@mcp.resource()` decorator
- Review FastMCP 2.0 documentation for Resource API
- Check existing codebase for any Resource examples
- Test Resource registration syntax

#### Task 2.2: Design Resource API Pattern

- Define Resource decorator pattern (e.g., `@mcp.resource()`)
- Design Resource response format (should match current Tool responses for compatibility)
- Define Resource URI/identifier pattern
- Document Resource vs Tool naming conventions

#### Task 2.3: Design Hybrid Operation Strategy

- For `manage_file`: Split into `get_file` (Resource) and `write_file` (Tool)?
- For `configure`: Split into `get_config` (Resource) and `update_config` (Tool)?
- Or: Keep single operation but register as both Resource and Tool?
- Document recommended approach

#### Task 2.4: Plan Backward Compatibility

- Strategy A: Keep Tools as-is, add Resources alongside (gradual migration)
- Strategy B: Transform immediately, maintain Tool aliases temporarily
- Strategy C: Version bump with breaking changes
- Recommend approach and document migration path

**Deliverables:**

- Resource API design document
- FastMCP 2.0 Resource syntax verification
- Hybrid operation handling strategy
- Backward compatibility plan

### Step 3: Implement Resources (8-12 hours)

#### Task 3.1: Create Resource Registration Infrastructure

- Add Resource registration support to `server.py`
- Create Resource decorator wrapper (if needed)
- Update tool registration system to support Resources
- Add Resource listing/querying capabilities

#### Task 3.2: Transform Read-Only Tools to Resources

- Start with Phase 1 Foundation tools:
  - `get_memory_bank_stats` → Resource
  - `get_version_history` → Resource
  - `get_dependency_graph` → Resource
  - `manage_file` (read operation) → Resource
- Continue with Phase 2 Linking tools:
  - `parse_file_links` → Resource
  - `resolve_transclusions` → Resource
  - `validate_links` → Resource
  - `get_link_graph` → Resource
- Continue with Phase 3 Validation tools:
  - `validate` (all check types) → Resource
- Continue with Phase 4 Optimization tools:
  - `optimize_context` → Resource
  - `load_progressive_context` → Resource
  - `get_relevance_scores` → Resource
  - `summarize_content` → Resource
- Continue with Phase 5 Analysis tools:
  - `analyze` → Resource
  - `suggest_refactoring` → Resource
  - `get_refactoring_suggestions` → Resource
- Continue with other read-only tools:
  - `get_structure_info` → Resource
  - `check_structure_health` (read-only mode) → Resource
  - `rules` (get_relevant) → Resource
  - `get_synapse_rules` → Resource
  - `get_synapse_prompts` → Resource

#### Task 3.3: Handle Hybrid Operations

- Implement split operations for hybrid tools:
  - `get_file` (Resource) and `write_file` (Tool) for `manage_file`
  - `get_config` (Resource) and `update_config` (Tool) for `configure`
- Or implement parameter-based registration
- Update function signatures and implementations

#### Task 3.4: Update Tool Registrations

- Keep write operations as Tools:
  - `rollback_file_version` → Tool
  - `apply_refactoring` → Tool
  - `provide_feedback` → Tool
  - `configure` (update) → Tool
  - `fix_quality_issues` → Tool
  - `fix_markdown_lint` → Tool
  - `sync_synapse` → Tool
  - `update_synapse_rule` → Tool
  - `update_synapse_prompt` → Tool
  - `check_structure_health` (with cleanup) → Tool
  - `rules` (index) → Tool
- Verify all Tools still work correctly

**Deliverables:**

- Resource implementations for all read-only operations
- Updated Tool registrations for write operations
- Hybrid operation implementations
- All tests passing

### Step 4: Update Tests and Documentation (4-6 hours)

#### Task 4.1: Add Resource Tests

- Create test infrastructure for Resources
- Add tests for each Resource operation
- Verify Resource responses match expected format
- Test Resource listing and querying

#### Task 4.2: Update Existing Tests

- Update tests that call read-only operations to use Resources
- Update tests that call write operations to use Tools
- Verify all existing tests still pass
- Add tests for hybrid operation splits

#### Task 4.3: Update Documentation

- Update API documentation to distinguish Resources vs Tools
- Update tool reference documentation
- Add Resource usage examples
- Update architecture documentation
- Update migration guide (if breaking changes)

**Deliverables:**

- Comprehensive Resource test suite
- Updated API documentation
- Migration guide (if needed)
- All tests passing

### Step 5: Verification and Migration (2-4 hours)

#### Task 5.1: Verify Resource Functionality

- Test all Resources work correctly via MCP protocol
- Verify Resource responses are properly formatted
- Test Resource listing and discovery
- Verify Resource caching (if applicable)

#### Task 5.2: Verify Tool Functionality

- Test all Tools still work correctly
- Verify write operations function as expected
- Test hybrid operation splits
- Verify backward compatibility (if maintained)

#### Task 5.3: Performance Testing

- Compare Resource vs Tool performance (if measurable)
- Verify no performance regressions
- Test Resource caching benefits (if applicable)

#### Task 5.4: Client Compatibility

- Test with existing MCP clients
- Verify Resources are discoverable
- Verify Tools are still callable
- Document any breaking changes

**Deliverables:**

- Verification test results
- Performance comparison (if applicable)
- Client compatibility report
- Migration completion confirmation

## Technical Design

### Resource Registration Pattern

```python
# Example: Read-only operation as Resource
@mcp.resource()
async def get_memory_bank_stats(
    project_root: str | None = None,
    include_token_budget: bool = True,
    include_refactoring_history: bool = False,
    refactoring_days: int = 90,
) -> dict[str, object]:
    """Get overall Memory Bank statistics and analytics.
    
    This is a Resource (GET endpoint) that loads information into LLM context.
    No side effects, read-only operation.
    """
    # Implementation...
```

### Tool Registration Pattern (Write Operations)

```python
# Example: Write operation as Tool
@mcp.tool()
async def rollback_file_version(
    file_name: str,
    version: int,
    project_root: str | None = None,
) -> dict[str, object]:
    """Rollback a Memory Bank file to a previous version.
    
    This is a Tool (POST endpoint) that executes code and produces side effects.
    Modifies file system, creates new version.
    """
    # Implementation...
```

### Hybrid Operation Strategy

#### Option A: Split Operations (Recommended)

```python
# Resource for read
@mcp.resource()
async def get_file(
    file_name: str,
    project_root: str | None = None,
    include_metadata: bool = False,
) -> dict[str, object]:
    """Read a Memory Bank file (Resource)."""
    # Read implementation...

# Tool for write
@mcp.tool()
async def write_file(
    file_name: str,
    content: str,
    project_root: str | None = None,
    change_description: str | None = None,
) -> dict[str, object]:
    """Write a Memory Bank file (Tool)."""
    # Write implementation...
```

#### Option B: Parameter-Based (Alternative)

```python
# Single operation, registered as both Resource and Tool
@mcp.resource()
@mcp.tool()
async def manage_file(
    file_name: str,
    operation: Literal["read", "write", "metadata"],
    content: str | None = None,
    project_root: str | None = None,
) -> dict[str, object]:
    """Manage Memory Bank file operations.
    
    When operation="read" or "metadata": Resource (read-only)
    When operation="write": Tool (side effects)
    """
    # Implementation...
```

### FastMCP 2.0 Resource Syntax

Need to verify FastMCP 2.0 Resource decorator syntax. Based on FastMCP 2.0 patterns:

- Resources may use `@mcp.resource()` decorator
- Resources may have different response format requirements
- Resources may support URI-based identification
- Resources may have caching mechanisms

## Dependencies

- **FastMCP 2.0**: Already migrated (Phase 41), supports Resources
- **MCP Protocol**: Resources are part of MCP specification
- **Existing Tools**: All 53+ tools need to be audited and potentially migrated
- **Tests**: Comprehensive test suite needs updates
- **Documentation**: API documentation needs updates

## Success Criteria

1. ✅ All read-only operations registered as Resources
2. ✅ All write operations remain as Tools
3. ✅ Hybrid operations properly handled (split or parameter-based)
4. ✅ All Resources work correctly via MCP protocol
5. ✅ All Tools still work correctly
6. ✅ Backward compatibility maintained (if strategy chosen)
7. ✅ All tests passing
8. ✅ Documentation updated
9. ✅ No performance regressions
10. ✅ Client compatibility verified

## Risks & Mitigation

### Risk 1: FastMCP 2.0 Resource Support Unknown

- **Impact**: High - Cannot implement Resources if not supported
- **Mitigation**: Verify Resource support in FastMCP 2.0 documentation and codebase first (Step 2.1)
- **Fallback**: If Resources not supported, document as future enhancement, focus on Tool optimization

### Risk 2: Breaking Changes for Existing Clients

- **Impact**: Medium - Clients may break if Tools removed
- **Mitigation**: Maintain backward compatibility (keep Tools as aliases, or gradual migration)
- **Fallback**: Version bump with migration guide

### Risk 3: Hybrid Operations Complexity

- **Impact**: Medium - Some operations do both read and write
- **Mitigation**: Split into separate Resource and Tool operations (cleaner API)
- **Fallback**: Keep as Tools with clear documentation

### Risk 4: Performance Unknown

- **Impact**: Low - Resources may not have performance benefits
- **Mitigation**: Measure before/after performance, document findings
- **Fallback**: Semantic correctness is primary goal, performance is secondary

### Risk 5: Large Scope (53+ Tools)

- **Impact**: Medium - Many tools to audit and migrate
- **Mitigation**: Prioritize high-impact tools first, migrate incrementally
- **Fallback**: Focus on most commonly used read-only tools first

## Timeline

- **Step 1 (Audit)**: 4-6 hours
- **Step 2 (Design)**: 3-4 hours
- **Step 3 (Implementation)**: 8-12 hours
- **Step 4 (Tests/Docs)**: 4-6 hours
- **Step 5 (Verification)**: 2-4 hours

**Total Estimated Effort**: 21-32 hours (3-4 days)

## Notes

### User-Provided Context (FastMCP Resources vs Tools)

The user has provided the following context that should be attached to this plan:

1. **FastMCP Documentation Reference**: <https://gofastmcp.com/getting-started/welcome#what-is-mcp>
   - Resources are like GET endpoints (load information into LLM context)
   - Tools are like POST endpoints (execute code or produce side effects)
   - Prompts define interaction patterns

2. **Current Tool Registration**: All 53+ tools are registered as `@mcp.tool()` decorators
   - No Resources currently registered
   - FastMCP 2.0 migration completed (Phase 41)

3. **Project Context**:
   - Cortex is an MCP Memory Bank server
   - Comprehensive tool suite across 10 phases
   - Focus on protocol compliance and best practices

### Related Work

- **Phase 41**: FastMCP 2.0 Migration - Completed, enables Resource support
- **Phase 29**: Track MCP Tool Usage - May provide data on which tools are read-only vs write
- **Phase 7.10**: Tool Consolidation - Previous tool optimization work

### Open Questions

1. Does FastMCP 2.0 support `@mcp.resource()` decorator? (Need to verify)
2. What is the Resource response format? (May differ from Tool format)
3. Should we maintain backward compatibility or do breaking changes?
4. How do clients discover Resources vs Tools? (MCP protocol specification)
5. Are there performance benefits to Resources? (Unknown, need to measure)

### Future Enhancements

- Resource caching mechanisms (if supported by MCP protocol)
- Resource versioning (if applicable)
- Resource access control (if needed)
- Resource metadata and documentation (beyond Tool documentation)
