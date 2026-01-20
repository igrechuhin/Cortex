# Phase 34: Ensure All Cortex MCP Tools Have Reasonable Timeouts

## Status

- **Status**: PLANNING
- **Priority**: HIGH
- **Start Date**: 2026-01-16
- **Target Completion**: 2026-01-17

## Goal

Ensure all Cortex MCP tools run with reasonable timeouts to prevent hanging operations and improve system reliability.

## Problem Statement

Currently, many Cortex MCP tools do not have explicit timeout protection, which can lead to:

1. **Hanging Operations**: Tools that perform long-running operations (file I/O, network requests, complex computations) can hang indefinitely
2. **Resource Exhaustion**: Without timeouts, tools can consume resources indefinitely, blocking other operations
3. **Poor User Experience**: Users have no way to know if a tool is working or hung, leading to frustration
4. **System Instability**: Hanging tools can cause connection issues and server instability

**Recent Examples**:

- Phase 31: `validate(check_type="timestamps")` hung due to blocking `glob()` operation
- Some tools use `asyncio.wait_for()` directly instead of centralized timeout mechanism
- Only a few tools use `@mcp_tool_wrapper(timeout=...)` decorator

**Impact**:

- Tools can hang indefinitely, blocking MCP server
- No consistent timeout strategy across all tools
- Difficult to diagnose and recover from hanging operations
- Poor reliability and user experience

## Current State Analysis

### Existing Timeout Infrastructure

1. **Timeout Constants** (`src/cortex/core/constants.py`):
   - `MCP_TOOL_TIMEOUT_SECONDS = 300` (5 minutes) - Default timeout for MCP tools
   - `GIT_OPERATION_TIMEOUT_SECONDS = 30` - Timeout for git operations
   - `LOCK_TIMEOUT_SECONDS = 30` - File lock timeout

2. **Timeout Mechanisms** (`src/cortex/core/mcp_stability.py`):
   - `@mcp_tool_wrapper(timeout=...)` - Decorator to add timeout protection
   - `with_mcp_stability(func, timeout=...)` - Function wrapper for timeout protection
   - `execute_tool_with_stability(func, timeout=...)` - Convenience wrapper

3. **Tools Currently Using Timeouts**:
   - `markdown_operations.py`: `fix_markdown_lint` uses `@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_SECONDS)`
   - `mcp_stability.py`: Example tool uses `@mcp_tool_wrapper(timeout=60.0)`
   - Some tools use `asyncio.wait_for()` directly (e.g., `_run_command()` in `markdown_operations.py`)

### Tools Missing Timeout Protection

Based on grep analysis, found **37 MCP tool definitions** (`@mcp.tool()`), but only **2-3 tools** use `@mcp_tool_wrapper()`:

**Tools without timeout wrapper**:

- `phase1_foundation_rollback.py`: `rollback_file_version`
- `analysis_operations.py`: `analyze`
- `phase5_execution.py`: `apply_refactoring`, `provide_feedback`
- `pre_commit_tools.py`: `execute_pre_commit_checks`, `fix_quality_issues`
- `refactoring_operations.py`: `suggest_refactoring`
- `phase1_foundation_stats.py`: `get_memory_bank_stats`
- `rules_operations.py`: `rules`
- `phase4_optimization_handlers.py`: `optimize_context`, `load_progressive_context`, `summarize_content`, `get_relevance_scores`
- `file_operations.py`: `manage_file`
- `phase1_foundation_dependency.py`: `get_dependency_graph`
- `phase8_structure.py`: `check_structure_health`, `get_structure_info`
- `configuration_operations.py`: `configure`
- `link_parser_operations.py`: `parse_file_links`
- `synapse_tools.py`: `get_synapse_rules`, `get_synapse_prompts`, `update_synapse_rule`, `update_synapse_prompt`, `sync_synapse`
- `link_validation_operations.py`: `validate_links`
- `validation_operations.py`: `validate`
- `phase1_foundation_version.py`: `get_version_history`
- `link_graph_operations.py`: `get_link_graph`
- `connection_health.py`: `check_mcp_connection_health`
- `transclusion_operations.py`: `resolve_transclusions`
- `phase1_foundation_cleanup.py`: `cleanup_metadata_index`

**Total**: ~35 tools missing explicit timeout protection

## Approach

### Strategy

1. **Audit All Tools**: Identify all MCP tools and categorize by operation type
2. **Define Timeout Categories**: Create timeout categories based on operation complexity
3. **Apply Timeout Wrapper**: Add `@mcp_tool_wrapper(timeout=...)` to all tools with appropriate timeouts
4. **Replace Direct Timeouts**: Replace `asyncio.wait_for()` calls with centralized timeout mechanism where appropriate
5. **Add Timeout Configuration**: Allow per-tool timeout configuration if needed
6. **Test Timeout Behavior**: Verify timeouts work correctly and don't break functionality
7. **Document Timeout Strategy**: Document timeout values and rationale

### Timeout Categories

Based on operation complexity and expected duration:

1. **Fast Operations** (30-60 seconds):
   - Simple file reads/writes
   - Metadata queries
   - Configuration operations
   - Health checks
   - Examples: `get_structure_info`, `check_mcp_connection_health`, `configure`

2. **Medium Operations** (60-120 seconds):
   - File operations with validation
   - Link parsing and validation
   - Dependency graph construction
   - Version history queries
   - Examples: `manage_file`, `parse_file_links`, `validate_links`, `get_dependency_graph`

3. **Complex Operations** (120-300 seconds):
   - Context optimization
   - Progressive loading
   - Transclusion resolution
   - Validation across all files
   - Examples: `optimize_context`, `load_progressive_context`, `resolve_transclusions`, `validate`

4. **Very Complex Operations** (300-600 seconds):
   - Refactoring analysis and execution
   - Comprehensive analysis operations
   - Large-scale file operations
   - Examples: `suggest_refactoring`, `apply_refactoring`, `analyze`, `get_memory_bank_stats`

5. **External Operations** (30-120 seconds):
   - Git operations
   - External command execution
   - Network requests
   - Examples: `sync_synapse`, `update_synapse_rule`, `execute_pre_commit_checks`

### Default Timeout Strategy

- **Default**: Use `MCP_TOOL_TIMEOUT_SECONDS` (300 seconds) for most tools
- **Override**: Use specific timeouts for tools that need different values
- **Minimum**: 30 seconds for any tool (prevents premature timeouts)
- **Maximum**: 600 seconds for very complex operations (prevents indefinite hangs)

## Implementation Steps

### Step 1: Audit All MCP Tools

**Tasks**:

1. Create comprehensive list of all MCP tools with their current timeout status
2. Categorize tools by operation type and expected duration
3. Identify tools using `asyncio.wait_for()` directly
4. Document current timeout behavior for each tool

**Deliverables**:

- Spreadsheet or document listing all tools, their categories, and recommended timeouts
- List of tools using direct `asyncio.wait_for()` calls

**Estimated Time**: 2 hours

### Step 2: Define Timeout Constants

**Tasks**:

1. Add timeout constants to `src/cortex/core/constants.py`:

   ```python
   # MCP Tool Timeout Categories
   MCP_TOOL_TIMEOUT_FAST = 60  # Fast operations (30-60s)
   MCP_TOOL_TIMEOUT_MEDIUM = 120  # Medium operations (60-120s)
   MCP_TOOL_TIMEOUT_COMPLEX = 300  # Complex operations (120-300s)
   MCP_TOOL_TIMEOUT_VERY_COMPLEX = 600  # Very complex operations (300-600s)
   MCP_TOOL_TIMEOUT_EXTERNAL = 120  # External operations (30-120s)
   ```

2. Update `MCP_TOOL_TIMEOUT_SECONDS` documentation to clarify it's the default for most tools

**Deliverables**:

- Updated constants file with timeout categories
- Documentation for timeout selection criteria

**Estimated Time**: 1 hour

### Step 3: Apply Timeout Wrapper to All Tools

**Tasks**:

1. Add `@mcp_tool_wrapper(timeout=...)` decorator to all tools without timeout protection
2. Use appropriate timeout constant based on tool category:
   - Fast operations: `MCP_TOOL_TIMEOUT_FAST`
   - Medium operations: `MCP_TOOL_TIMEOUT_MEDIUM`
   - Complex operations: `MCP_TOOL_TIMEOUT_COMPLEX`
   - Very complex operations: `MCP_TOOL_TIMEOUT_VERY_COMPLEX`
   - External operations: `MCP_TOOL_TIMEOUT_EXTERNAL`
3. Ensure decorator order: `@mcp.tool()` then `@mcp_tool_wrapper(timeout=...)`
4. Update imports to include `mcp_tool_wrapper` and timeout constants

**Files to Modify**:

- `src/cortex/tools/phase1_foundation_rollback.py`
- `src/cortex/tools/analysis_operations.py`
- `src/cortex/tools/phase5_execution.py`
- `src/cortex/tools/pre_commit_tools.py`
- `src/cortex/tools/refactoring_operations.py`
- `src/cortex/tools/phase1_foundation_stats.py`
- `src/cortex/tools/rules_operations.py`
- `src/cortex/tools/phase4_optimization_handlers.py`
- `src/cortex/tools/file_operations.py`
- `src/cortex/tools/phase1_foundation_dependency.py`
- `src/cortex/tools/phase8_structure.py`
- `src/cortex/tools/configuration_operations.py`
- `src/cortex/tools/link_parser_operations.py`
- `src/cortex/tools/synapse_tools.py`
- `src/cortex/tools/link_validation_operations.py`
- `src/cortex/tools/validation_operations.py`
- `src/cortex/tools/phase1_foundation_version.py`
- `src/cortex/tools/link_graph_operations.py`
- `src/cortex/tools/connection_health.py`
- `src/cortex/tools/transclusion_operations.py`
- `src/cortex/tools/phase1_foundation_cleanup.py`

**Deliverables**:

- All tools have timeout protection
- Consistent timeout strategy across codebase

**Estimated Time**: 4 hours

### Step 4: Replace Direct Timeout Calls

**Tasks**:

1. Identify tools using `asyncio.wait_for()` directly
2. Evaluate if they should use `@mcp_tool_wrapper()` instead
3. For internal operations (not MCP tools), keep `asyncio.wait_for()` but ensure consistent timeout values
4. Update `_run_command()` in `markdown_operations.py` to use consistent timeout constants

**Files to Review**:

- `src/cortex/tools/markdown_operations.py`: `_run_command()` uses `asyncio.wait_for()`
- `src/cortex/rules/synapse_repository.py`: `_run_git_command_internal()` uses `asyncio.wait_for()`
- `src/cortex/services/framework_adapters/python_adapter.py`: `_execute_test_command()` uses `asyncio.wait_for()`

**Deliverables**:

- Consistent timeout handling across codebase
- Internal operations use appropriate timeout constants

**Estimated Time**: 2 hours

### Step 5: Add Timeout Configuration Support

**Tasks**:

1. Consider adding per-tool timeout configuration in `.cortex/config/` (optional, future enhancement)
2. Document timeout configuration approach
3. For now, use constants-based approach (simpler, more maintainable)

**Deliverables**:

- Documentation for timeout configuration (if implemented)
- Decision on whether to support per-tool timeouts (likely defer to future phase)

**Estimated Time**: 1 hour (research and documentation)

### Step 6: Test Timeout Behavior

**Tasks**:

1. Create unit tests for timeout behavior:
   - Test that tools timeout correctly when operation exceeds timeout
   - Test that tools complete successfully within timeout
   - Test timeout error messages are clear
2. Create integration tests:
   - Test timeout behavior with actual MCP tool calls
   - Verify timeout doesn't break tool functionality
3. Test edge cases:
   - Very fast operations (should not timeout prematurely)
   - Operations that complete just before timeout
   - Operations that exceed timeout

**Test Files to Create/Update**:

- `tests/unit/test_mcp_stability_timeouts.py` (new)
- Update existing tests to verify timeout behavior

**Deliverables**:

- Comprehensive timeout tests
- All tests passing

**Estimated Time**: 3 hours

### Step 7: Document Timeout Strategy

**Tasks**:

1. Add timeout documentation to `docs/`:
   - Timeout categories and rationale
   - How to select appropriate timeout for new tools
   - How timeout mechanism works
   - Troubleshooting timeout issues
2. Update code comments:
   - Document timeout values in tool definitions
   - Explain timeout selection rationale

**Deliverables**:

- Timeout documentation in `docs/`
- Updated code comments

**Estimated Time**: 2 hours

### Step 8: Verify All Tools Have Timeouts

**Tasks**:

1. Run automated check to verify all `@mcp.tool()` decorators have `@mcp_tool_wrapper()`
2. Create script or test to validate timeout coverage
3. Fix any tools that were missed

**Deliverables**:

- Verification script/test
- All tools confirmed to have timeout protection

**Estimated Time**: 1 hour

## Dependencies

- **Phase 32: Fix MCP Tool Connection Closure Errors** - COMPLETE - Provides connection stability infrastructure
- **Phase 31: Investigate Validate Timestamps Hang** - COMPLETE - Shows importance of timeouts for blocking operations

## Success Criteria

1. ✅ **All MCP tools have timeout protection**: Every `@mcp.tool()` has `@mcp_tool_wrapper(timeout=...)`
2. ✅ **Appropriate timeout values**: Timeouts match operation complexity (fast/medium/complex/very complex/external)
3. ✅ **Consistent timeout strategy**: All tools use centralized timeout mechanism
4. ✅ **No hanging operations**: Tools timeout gracefully instead of hanging indefinitely
5. ✅ **Clear timeout errors**: Timeout errors provide actionable information
6. ✅ **Comprehensive tests**: Timeout behavior is tested and verified
7. ✅ **Documentation**: Timeout strategy is documented for future reference

## Testing Strategy

### Unit Tests

1. **Timeout Enforcement**:
   - Test that `@mcp_tool_wrapper()` enforces timeout correctly
   - Test that `with_mcp_stability()` raises `TimeoutError` when operation exceeds timeout
   - Test timeout error messages are clear and actionable

2. **Timeout Categories**:
   - Test that different timeout categories work correctly
   - Test that tools complete successfully within their timeout limits

3. **Edge Cases**:
   - Test operations that complete just before timeout
   - Test operations that exceed timeout
   - Test very fast operations don't timeout prematurely

### Integration Tests

1. **MCP Tool Timeouts**:
   - Test actual MCP tool calls with timeout protection
   - Verify timeout doesn't break tool functionality
   - Test timeout behavior with real operations

2. **Timeout Recovery**:
   - Test that timeout errors are handled gracefully
   - Test that tools can be retried after timeout (if applicable)

### Manual Testing

1. **Long-Running Operations**:
   - Manually test tools with long-running operations to verify timeout behavior
   - Verify timeout values are appropriate (not too short, not too long)

2. **User Experience**:
   - Verify timeout errors are clear and actionable
   - Verify tools don't hang indefinitely

## Risks & Mitigation

### Risk 1: Timeout Values Too Short

**Impact**: Tools timeout prematurely, breaking functionality

**Mitigation**:

- Start with conservative timeout values (use existing `MCP_TOOL_TIMEOUT_SECONDS` as default)
- Test tools with realistic workloads to verify timeout values
- Allow per-tool timeout overrides if needed
- Monitor timeout errors in production and adjust values

### Risk 2: Timeout Values Too Long

**Impact**: Tools still hang for too long, poor user experience

**Mitigation**:

- Categorize tools by complexity and use appropriate timeouts
- Set maximum timeout of 600 seconds (10 minutes) for very complex operations
- Monitor tool execution times and adjust timeouts based on actual performance

### Risk 3: Breaking Existing Functionality

**Impact**: Adding timeouts breaks tools that work correctly

**Mitigation**:

- Comprehensive testing before and after timeout implementation
- Start with default timeout (300s) for most tools, then optimize
- Test with realistic workloads to ensure timeouts don't interfere

### Risk 4: Inconsistent Timeout Handling

**Impact**: Some tools use timeouts, others don't, leading to confusion

**Mitigation**:

- Apply timeout wrapper to ALL tools consistently
- Use centralized timeout mechanism (`@mcp_tool_wrapper()`)
- Document timeout strategy clearly
- Create verification script to ensure all tools have timeouts

## Timeline

- **Step 1: Audit All MCP Tools** - 2 hours
- **Step 2: Define Timeout Constants** - 1 hour
- **Step 3: Apply Timeout Wrapper to All Tools** - 4 hours
- **Step 4: Replace Direct Timeout Calls** - 2 hours
- **Step 5: Add Timeout Configuration Support** - 1 hour
- **Step 6: Test Timeout Behavior** - 3 hours
- **Step 7: Document Timeout Strategy** - 2 hours
- **Step 8: Verify All Tools Have Timeouts** - 1 hour

**Total Estimated Time**: 16 hours (2 days)

## Notes

- This phase builds on Phase 32's connection stability infrastructure
- Timeout values can be adjusted based on real-world usage patterns
- Consider adding timeout metrics/telemetry in future phase to optimize timeout values
- Per-tool timeout configuration can be added in future if needed
- Timeout strategy should be reviewed periodically as tools evolve

## Related Phases

- **Phase 32: Fix MCP Tool Connection Closure Errors** - Provides connection stability infrastructure that timeout mechanism uses
- **Phase 31: Investigate Validate Timestamps Hang** - Shows importance of timeouts for blocking operations
- **Phase 19: Fix MCP Server Crash** - Related to overall MCP server stability
