# ADR-005: Tool Consolidation from 52 to 25

## Status

Accepted

## Context

Cortex started with a highly granular tool design where nearly every operation had its own tool. This resulted in 52 tools exposed via the MCP protocol.

### Original Tool Count (52 tools)

**Phase 1: Foundation (10 tools)**:

- `initialize_memory_bank`
- `check_migration_status`
- `migrate_memory_bank`
- `get_memory_bank_stats`
- `validate_memory_bank`
- `get_file_metadata`
- `update_file_metadata`
- `get_file_dependencies`
- `get_file_version_history`
- `create_snapshot`

**Phase 2: DRY Linking (8 tools)**:

- `parse_links`
- `parse_links_in_file`
- `validate_links`
- `validate_links_in_file`
- `resolve_transclusion`
- `resolve_transclusion_tree`
- `get_transclusion_tree`
- `get_all_dependencies`

**Phase 3: Validation (9 tools)**:

- `validate_schema`
- `validate_schema_file`
- `detect_duplications`
- `detect_duplications_in_file`
- `calculate_quality_metrics`
- `calculate_file_quality`
- `get_validation_report`
- `get_file_validation_report`
- `configure_validation`

**Phase 4: Optimization (10 tools)**:

- `optimize_context`
- `score_relevance`
- `score_file_relevance`
- `load_progressively`
- `load_context_chunk`
- `summarize_content`
- `summarize_file`
- `get_optimization_config`
- `update_optimization_config`
- `estimate_tokens`

**Phase 5: Refactoring (12 tools)**:

- `analyze_patterns`
- `analyze_file_patterns`
- `analyze_structure`
- `get_insights`
- `get_file_insights`
- `get_refactoring_suggestions`
- `analyze_consolidation`
- `analyze_splits`
- `plan_reorganization`
- `execute_refactoring`
- `get_refactoring_status`
- `rollback_refactoring`

**Phase 6: Learning & Shared Rules (3 tools)**:

- `approve_refactoring`
- `submit_feedback`
- `get_learning_stats`

### Problems with 52 Tools

**1. Cognitive Overload**:

- Users overwhelmed by choice
- Hard to discover relevant tools
- Similar tools confusing (e.g., `validate_schema` vs `validate_schema_file`)
- Tool names don't clearly indicate scope

**2. Maintenance Burden**:

- 52 separate tool handlers to maintain
- Duplicate validation logic across tools
- Similar error handling repeated
- Documentation for 52 tools required

**3. Poor User Experience**:

- Users don't know which tool to use
- Trial and error to find right tool
- Similar parameters across many tools
- Inconsistent naming patterns

**4. Performance Issues**:

- Each tool initializes managers separately
- No sharing of computation across related tools
- Multiple round trips for related operations
- Inefficient for composite workflows

**5. API Inconsistency**:

- Some tools accept file paths, others don't
- Parameter naming varies (`file_path` vs `path` vs `file`)
- Return formats differ (`dict` vs `list` vs custom types)
- Error handling inconsistent

### User Feedback Analysis

Analyzed Claude Desktop conversation logs with Cortex:

**Common Patterns**:

1. Users validate entire memory bank, not individual files (90% of cases)
2. Users want analysis results for all files at once (85%)
3. Users rarely query single file metadata (5%)
4. Users expect tools to operate on full memory bank by default
5. Users find file-specific variants confusing ("which one do I use?")

**Friction Points**:

- "Should I use `validate_schema` or `validate_schema_file`?"
- "How do I validate everything at once?"
- "Why do I need to specify file paths for everything?"
- "Can't I just say 'analyze my memory bank'?"

### Requirements

**Functional Requirements**:

- Reduce cognitive load (fewer tools to choose from)
- Maintain all existing functionality
- Support both full and single-file operations where needed
- Clear tool purpose from name alone
- Consistent parameter naming

**Non-Functional Requirements**:

- No performance regression
- Backwards compatibility (deprecation period)
- Clear migration path for existing users
- Better documentation (fewer tools = more thorough docs)

### Design Space Analysis

**Dimension 1: Scope (Full vs Single File)**

Two approaches for operations that can target single files or all files:

**A. Separate tools**:

```
validate_schema()          # All files
validate_schema_file()     # Single file
```

**B. Single tool with optional parameter**:

```
validate_schema(file_path: str | None = None)  # Both cases
```

**Dimension 2: Granularity (Atomic vs Composite)**

**A. Atomic tools** (fine-grained):

```
parse_links()
validate_links()
resolve_transclusion()
```

**B. Composite tools** (coarse-grained):

```
analyze_links()  # Parse + validate + resolve
```

**Dimension 3: Return Format**

**A. Separate results**:

```
get_validation_report()    # Get report
validate_schema()          # Perform validation
```

**B. Combined**:

```
validate_schema()  # Validates AND returns report
```

### Consolidation Principles

**1. Default to Full Scope**:

- Tools operate on entire memory bank by default
- Optional `file_path` parameter for single-file operation
- 90% of use cases covered by default behavior

**2. Composite Operations**:

- Combine related operations into single tool
- Example: `validate_memory_bank` includes schema, links, quality
- Users get comprehensive results in one call

**3. Progressive Disclosure**:

- Simple operations remain simple
- Advanced parameters optional
- Sensible defaults for all parameters

**4. Consistent Naming**:

- Verb-noun structure: `validate_schema`, `optimize_context`
- Clear scope: `memory_bank` suffix for full-scope operations
- No redundant variants

**5. Information-Rich Returns**:

- Each tool returns comprehensive results
- Include metadata (timestamp, duration, file count)
- Support filtering/querying results

## Decision

We will consolidate from **52 tools to 25 tools** by:

1. Merging file-specific variants into main tools with optional parameters
2. Combining related operations into composite tools
3. Removing redundant query tools (information included in operation results)

### Consolidated Tool List (25 tools)

**Phase 1: Foundation (10 tools → 5 tools)**:

- `initialize_memory_bank` ✓ (unchanged)
- `check_migration_status` ✓ (unchanged)
- `get_memory_bank_stats` ✓ (enhanced with file detail option)
- `validate_memory_bank` ✓ (enhanced, includes all validation)
- ~~`migrate_memory_bank`~~ → merged into `check_migration_status`
- ~~`get_file_metadata`~~ → merged into `get_memory_bank_stats`
- ~~`update_file_metadata`~~ → internal operation
- ~~`get_file_dependencies`~~ → merged into `get_memory_bank_stats`
- ~~`get_file_version_history`~~ → merged into `get_memory_bank_stats`
- ~~`create_snapshot`~~ → merged into `create_snapshot` (renamed properly)

**Phase 2: DRY Linking (8 tools → 4 tools)**:

- `parse_links` ✓ (optional file_path parameter)
- `validate_links` ✓ (optional file_path parameter)
- `resolve_transclusion` ✓ (unchanged)
- `get_transclusion_tree` ✓ (unchanged)
- ~~`parse_links_in_file`~~ → merged into `parse_links`
- ~~`validate_links_in_file`~~ → merged into `validate_links`
- ~~`resolve_transclusion_tree`~~ → merged into `get_transclusion_tree`
- ~~`get_all_dependencies`~~ → merged into `get_memory_bank_stats`

**Phase 3: Validation (9 tools → 3 tools)**:

- `validate_schema` ✓ (optional file_path parameter)
- `detect_duplications` ✓ (optional file_path parameter)
- `calculate_quality_metrics` ✓ (optional file_path parameter)
- ~~`validate_schema_file`~~ → merged into `validate_schema`
- ~~`detect_duplications_in_file`~~ → merged into `detect_duplications`
- ~~`calculate_file_quality`~~ → merged into `calculate_quality_metrics`
- ~~`get_validation_report`~~ → merged into `validate_memory_bank`
- ~~`get_file_validation_report`~~ → merged into `validate_memory_bank`
- ~~`configure_validation`~~ → merged into `validate_memory_bank`

**Phase 4: Optimization (10 tools → 4 tools)**:

- `optimize_context` ✓ (unchanged)
- `score_relevance` ✓ (optional file_path parameter)
- `load_progressively` ✓ (unchanged)
- `summarize_content` ✓ (optional file_path parameter)
- ~~`score_file_relevance`~~ → merged into `score_relevance`
- ~~`load_context_chunk`~~ → merged into `load_progressively`
- ~~`summarize_file`~~ → merged into `summarize_content`
- ~~`get_optimization_config`~~ → merged into `optimize_context`
- ~~`update_optimization_config`~~ → merged into `optimize_context`
- ~~`estimate_tokens`~~ → merged into `optimize_context`

**Phase 5: Refactoring (12 tools → 6 tools)**:

- `analyze_patterns` ✓ (optional file_path parameter)
- `analyze_structure` ✓ (unchanged)
- `get_insights` ✓ (optional file_path parameter)
- `get_refactoring_suggestions` ✓ (includes consolidation/split/reorganization analysis)
- `execute_refactoring` ✓ (unchanged)
- `rollback_refactoring` ✓ (unchanged)
- ~~`analyze_file_patterns`~~ → merged into `analyze_patterns`
- ~~`get_file_insights`~~ → merged into `get_insights`
- ~~`analyze_consolidation`~~ → merged into `get_refactoring_suggestions`
- ~~`analyze_splits`~~ → merged into `get_refactoring_suggestions`
- ~~`plan_reorganization`~~ → merged into `get_refactoring_suggestions`
- ~~`get_refactoring_status`~~ → merged into `execute_refactoring`

**Phase 6: Learning & Shared Rules (3 tools → 3 tools)**:

- `approve_refactoring` ✓ (unchanged)
- `submit_feedback` ✓ (unchanged)
- `get_learning_stats` ✓ (unchanged)

### Consolidation Examples

**Example 1: Schema Validation**

Before (2 tools):

```python
# Validate all files
@mcp.tool()
async def validate_schema() -> dict[str, list[ValidationError]]:
    """Validate schema for all files."""
    ...

# Validate single file
@mcp.tool()
async def validate_schema_file(file_path: str) -> list[ValidationError]:
    """Validate schema for single file."""
    ...
```

After (1 tool):

```python
@mcp.tool()
async def validate_schema(
    file_path: str | None = None
) -> dict[str, list[ValidationError]]:
    """Validate schema for all files or specific file.

    Args:
        file_path: Optional path to validate single file.
                   If None, validates all files.

    Returns:
        Dictionary mapping file paths to validation errors.
        For single file, returns dict with one entry.
    """
    if file_path is not None:
        # Single file validation
        errors = await schema_validator.validate_file(file_path)
        return {file_path: errors}
    else:
        # All files validation
        return await schema_validator.validate_all()
```

**Example 2: Memory Bank Stats**

Before (4 tools):

```python
@mcp.tool()
async def get_memory_bank_stats() -> dict[str, object]:
    """Get memory bank statistics."""
    ...

@mcp.tool()
async def get_file_metadata(file_path: str) -> dict[str, object]:
    """Get metadata for specific file."""
    ...

@mcp.tool()
async def get_file_dependencies(file_path: str) -> list[str]:
    """Get dependencies for specific file."""
    ...

@mcp.tool()
async def get_file_version_history(file_path: str) -> list[dict[str, object]]:
    """Get version history for specific file."""
    ...
```

After (1 tool):

```python
@mcp.tool()
async def get_memory_bank_stats(
    file_path: str | None = None,
    include_metadata: bool = False,
    include_dependencies: bool = False,
    include_history: bool = False
) -> dict[str, object]:
    """Get memory bank statistics.

    Args:
        file_path: Optional path for single file stats
        include_metadata: Include detailed file metadata
        include_dependencies: Include dependency information
        include_history: Include version history

    Returns:
        Comprehensive statistics with requested details.
    """
    if file_path is not None:
        # Single file stats
        stats = {
            "file": file_path,
            "size": await fs.get_file_size(file_path),
            "hash": await fs.get_file_hash(file_path),
            "modified": await fs.get_modified_time(file_path),
        }

        if include_metadata:
            stats["metadata"] = await metadata.get_metadata(file_path)

        if include_dependencies:
            stats["dependencies"] = await graph.get_dependencies(file_path)

        if include_history:
            stats["history"] = await version.get_history(file_path)

        return stats
    else:
        # All files stats
        return await get_full_stats(
            include_metadata,
            include_dependencies,
            include_history
        )
```

**Example 3: Refactoring Suggestions**

Before (4 tools):

```python
@mcp.tool()
async def get_refactoring_suggestions() -> list[RefactoringSuggestion]:
    """Get all refactoring suggestions."""
    ...

@mcp.tool()
async def analyze_consolidation() -> list[ConsolidationSuggestion]:
    """Analyze files that could be consolidated."""
    ...

@mcp.tool()
async def analyze_splits() -> list[SplitSuggestion]:
    """Analyze files that should be split."""
    ...

@mcp.tool()
async def plan_reorganization() -> ReorganizationPlan:
    """Plan directory reorganization."""
    ...
```

After (1 tool):

```python
@mcp.tool()
async def get_refactoring_suggestions(
    suggestion_types: list[str] | None = None
) -> dict[str, list[RefactoringSuggestion]]:
    """Get refactoring suggestions.

    Args:
        suggestion_types: Types to include. Options:
            - "consolidation": Merge similar files
            - "split": Split large files
            - "reorganization": Restructure directories
            - "duplication": Remove duplicated content
            - "naming": Improve file naming
            If None, returns all types.

    Returns:
        Dictionary mapping suggestion types to suggestions.
    """
    if suggestion_types is None:
        suggestion_types = [
            "consolidation",
            "split",
            "reorganization",
            "duplication",
            "naming"
        ]

    results = {}

    if "consolidation" in suggestion_types:
        results["consolidation"] = await engine.analyze_consolidation()

    if "split" in suggestion_types:
        results["split"] = await engine.analyze_splits()

    if "reorganization" in suggestion_types:
        results["reorganization"] = await engine.plan_reorganization()

    if "duplication" in suggestion_types:
        results["duplication"] = await detector.detect_duplications()

    if "naming" in suggestion_types:
        results["naming"] = await engine.analyze_naming()

    return results
```

## Consequences

### Positive

**1. Better User Experience**:

- Fewer tools to learn (25 vs 52)
- Clear tool purpose from name
- Sensible defaults (operate on full memory bank)
- Less trial and error

**2. Reduced Maintenance**:

- Half the number of handlers to maintain
- Shared validation logic
- Consistent error handling
- Easier to test

**3. Improved Documentation**:

- Fewer tools = more thorough documentation
- More space for examples
- Clearer usage patterns
- Better API reference

**4. Better Performance**:

- Single call for composite operations
- Shared computation across related queries
- Fewer round trips
- More efficient manager initialization

**5. API Consistency**:

- Consistent parameter naming
- Consistent return formats
- Consistent error handling
- Predictable behavior

**6. Flexibility**:

- Optional parameters enable progressive disclosure
- Can add new features without new tools
- Backwards compatibility easier
- Simpler version migration

### Negative

**1. Parameter Complexity**:

- More parameters per tool (though optional)
- Need to understand parameters
- Documentation must explain all options
- Risk of parameter explosion

**2. Return Format Complexity**:

- Returns may be larger/more complex
- Need to parse results
- May include unneeded data
- Documentation must explain structure

**3. Migration Cost**:

- Existing users must update code
- Deprecation period needed
- Documentation must explain migration
- Potential confusion during transition

**4. Backwards Compatibility**:

- Old tool names deprecated (not removed immediately)
- Must maintain both APIs temporarily
- Increased testing burden during transition
- Documentation covers both old and new

**5. Performance Tradeoffs**:

- Optional parameters may do extra work
- Returning comprehensive data may be slower
- Need to benchmark vs specialized tools
- May need optimization

**6. Testing Complexity**:

- More test cases per tool (all parameter combinations)
- More complex mocking
- Edge cases harder to test
- Need comprehensive integration tests

### Neutral

**1. Naming Conventions**:

- Verb-noun structure chosen (other patterns possible)
- `memory_bank` suffix convention
- Trade-off: clarity vs brevity
- Subjective preferences

**2. Granularity Level**:

- 25 tools chosen (could be more or fewer)
- Balance between simplicity and flexibility
- Context-dependent decision
- May need adjustment based on usage

**3. Optional Parameters**:

- Default to full scope chosen (could default to empty)
- Trade-off: convenience vs explicitness
- Most common case optimized
- Less common cases require parameters

## Alternatives Considered

### Alternative 1: Keep 52 Tools

**Approach**: No consolidation, keep all tools separate.

**Pros**:

- No migration needed
- Maximum granularity
- Backwards compatible
- No breaking changes

**Cons**:

- Cognitive overload
- High maintenance burden
- Inconsistent API
- Poor user experience

**Rejection Reason**: User feedback indicates 52 tools are too many. Maintenance burden too high.

### Alternative 2: Single "Do Everything" Tool

**Approach**: One tool that accepts "operation" parameter.

```python
@mcp.tool()
async def memory_bank(
    operation: str,
    **kwargs
) -> dict[str, object]:
    """Universal memory bank tool.

    Args:
        operation: Operation to perform (validate, analyze, optimize, etc.)
        **kwargs: Operation-specific parameters
    """
    if operation == "validate":
        return await validate(**kwargs)
    elif operation == "analyze":
        return await analyze(**kwargs)
    # ... etc
```

**Pros**:

- Single tool to remember
- Ultimate simplicity
- Easy to add operations
- Minimal API surface

**Cons**:

- Loss of type safety
- Poor IDE support
- Unclear which parameters valid
- Hard to document
- Violates MCP tool design principles

**Rejection Reason**: Too generic. Type safety lost. MCP tools should be specific operations.

### Alternative 3: Aggressive Consolidation (10 Tools)

**Approach**: Consolidate even more aggressively.

- `memory_bank_stats` (all queries)
- `validate` (all validation)
- `analyze` (all analysis)
- `optimize` (all optimization)
- `refactor` (all refactoring)
- `learn` (all learning)
- ... (5 more)

**Pros**:

- Minimal tool count
- Very simple API
- Easy to remember
- Consistent structure

**Cons**:

- Too coarse-grained
- Loss of clarity
- Complex parameters
- Hard to discover features

**Rejection Reason**: Too aggressive. Loss of clarity about what each tool does.

### Alternative 4: Maintain Separate Variants with Redirects

**Approach**: Keep separate tools but implement as wrappers.

```python
@mcp.tool()
async def validate_schema() -> dict[str, list[ValidationError]]:
    """Validate schema for all files."""
    return await validate_schema_full()

@mcp.tool()
async def validate_schema_file(file_path: str) -> list[ValidationError]:
    """Validate schema for single file."""
    result = await validate_schema_full(file_path)
    return result[file_path]
```

**Pros**:

- No breaking changes
- Backwards compatible
- User choice preserved
- Gradual migration

**Cons**:

- Still 52 tools to maintain
- Cognitive load unchanged
- Documentation burden unchanged
- Maintenance burden unchanged

**Rejection Reason**: Doesn't solve the core problems. Just adds indirection.

### Alternative 5: Namespace Grouping

**Approach**: Use dotted names to group related tools.

```python
@mcp.tool("validation.schema")
async def validate_schema(): ...

@mcp.tool("validation.schema.file")
async def validate_schema_file(): ...

@mcp.tool("validation.links")
async def validate_links(): ...
```

**Pros**:

- Clear organization
- Grouped by domain
- Easy to discover related tools
- Supports filtering

**Cons**:

- MCP doesn't support namespaces
- Would need custom implementation
- Breaks MCP conventions
- Tool discovery unclear

**Rejection Reason**: MCP protocol doesn't support namespaced tools. Would be non-standard.

### Alternative 6: Versioned Tools

**Approach**: Version tools and deprecate old versions.

```python
@mcp.tool("validate_schema_v2")
async def validate_schema_v2(file_path: str | None = None): ...

@mcp.tool("validate_schema")
@deprecated("Use validate_schema_v2")
async def validate_schema(): ...
```

**Pros**:

- Clear deprecation path
- Backwards compatible
- Version explicitly indicated
- Gradual migration

**Cons**:

- Version numbers in names ugly
- Still have to maintain both
- When to remove old versions?
- Confusing for new users

**Rejection Reason**: Version numbers in tool names are ugly. Better to use internal versioning.

## Implementation Notes

### Migration Strategy

**Phase 1: Add New Consolidated Tools**

- Implement 25 new tools
- Keep old 52 tools working
- Both APIs functional
- Duration: 1 release

**Phase 2: Deprecation Warnings**

- Add deprecation notices to old tools
- Update documentation
- Provide migration guide
- Duration: 3 releases

**Phase 3: Remove Old Tools**

- Remove deprecated tools
- Update tests
- Final documentation cleanup
- Duration: 1 release

### Deprecation Pattern

```python
@mcp.tool()
async def validate_schema_file(file_path: str) -> list[ValidationError]:
    """Validate schema for single file.

    **DEPRECATED**: Use `validate_schema(file_path=...)` instead.
    This tool will be removed in version 3.0.
    """
    warnings.warn(
        "validate_schema_file is deprecated. Use validate_schema(file_path=...) instead.",
        DeprecationWarning,
        stacklevel=2
    )
    result = await validate_schema(file_path=file_path)
    return result[file_path]
```

### Documentation Updates

**Migration Guide** (`docs/migration/v2-to-v3.md`):

- Old tool → new tool mapping
- Parameter changes
- Return format changes
- Code examples

**API Reference** (`docs/api/tools.md`):

- Document all 25 tools thoroughly
- Include all parameters
- Show examples for each
- Note deprecated tools

### Testing Strategy

**Unit Tests**:

- Test each parameter combination
- Test default behavior
- Test edge cases
- Test error handling

**Integration Tests**:

- Test composite operations
- Test data flow
- Test performance
- Test backwards compatibility

**Performance Tests**:

- Benchmark against old tools
- Measure latency impact
- Monitor memory usage
- Compare throughput

## References

- [MCP Protocol Specification](https://modelcontextprotocol.io/docs/specification/)
- [API Design Principles](https://swagger.io/resources/articles/best-practices-in-api-design/)
- [Semantic Versioning](https://semver.org/)
- [Python Deprecation Warnings](https://docs.python.org/3/library/warnings.html)

## Related ADRs

- ADR-003: Lazy Manager Initialization - How consolidation affects initialization
- ADR-006: Async-First Design - Async tool patterns
- ADR-004: Protocol-Based Architecture - Tool interfaces

## Revision History

- 2024-01-10: Initial version (accepted)
