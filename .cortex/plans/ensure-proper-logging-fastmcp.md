# Development Plan: Ensure Proper Logging According to FastMCP Context

## Status

Phase 3 complete (2026-01-31). All tools now use optional ctx and log_client for entry/exit/error logging. Remaining: Phase 3.2 (error handling review), Phase 4 (tests), Phase 5 (docs). Some function-length/file-size quality violations remain in synapse_tools, phase5_execution, pre_commit_tools, refactoring_operations, file_operations; tracked for follow-up.

## Goal

Audit, standardize, and enhance logging throughout the Cortex codebase to align with FastMCP's Context-based logging best practices. This will ensure that server tools, resources, and middleware provide clear, structured, actionable log messages to clients, improve observability, and aid in debugging and error tracing.

## Background

### Current State

- **Logging System**: Uses standard Python `logging.getLogger(__name__)` throughout the codebase
- **Log Output**: Logs are sent to `stderr` (stdout is reserved for MCP protocol)
- **FastMCP Version**: FastMCP 2 (using `fastmcp<3` from requirements.txt)
- **Context Logging**: **Not currently used** - no usage of `ctx.debug()`, `ctx.info()`, `ctx.warning()`, or `ctx.error()`
- **Tool Pattern**: Tools use `@mcp.tool()` and `@mcp_tool_wrapper()` decorators

### FastMCP Context Logging Benefits

According to [FastMCP Context documentation](https://gofastmcp.com/servers/context):

- **Logging**: Logs are sent back to the client via MCP protocol (not just stderr)
  - Provides structured logging with metadata (request_id, client_id, etc.)
  - Better integration with client-side debugging and monitoring
  - Supports different log levels: `debug`, `info`, `warning`, `error`
- **Progress Reporting**: Update clients on progress of long-running operations
  - Enables progress indicators and better user experience
  - Use `await ctx.report_progress(progress=50, total=100)` for percentage-based progress
- Can be accessed via `CurrentContext()` dependency (FastMCP 2.14+) or `get_context()` function

## Scope

### In Scope

- All MCP tool functions (`@mcp.tool()` decorated functions)
- Helper functions called from tools (using `get_context()`)
- Error handling and exception logging
- Operation entry/exit logging
- Progress reporting for long-running operations (using `ctx.report_progress()`)
- Progress and state change logging
- Middleware logging (if applicable)

### Out of Scope

- Server startup/shutdown logging (can remain as standard Python logging)
- Internal manager/business logic logging (can remain as standard Python logging for server-side debugging)
- Test-only logging

## Success Criteria

1. **All tools use Context logging** for client-visible messages:
   - Entry logging: `await ctx.info("Starting operation X")`
   - Progress logging: `await ctx.info("Processing item Y of Z")`
   - Progress reporting: `await ctx.report_progress(progress=50, total=100)` for long-running operations
   - Warning logging: `await ctx.warning("Non-critical issue: ...")`
   - Error logging: `await ctx.error("Operation failed: ...")` or `ToolError` for fatal errors
2. **Helper functions** use `get_context()` for logging when not passed `ctx` parameter

3. **Structured logging** with metadata (request_id, tool_name, etc.) where applicable

4. **No ad-hoc print statements** or discarded exception traces
5. **Consistent logging format** across all tools
6. **Tests updated** to verify Context logging behavior
7. **Documentation updated** with logging guidelines

## Technical Design

### FastMCP Context API

#### Accessing Context in Tools

```python
from fastmcp import CurrentContext

@mcp.tool()
async def my_tool(
    param: str,
    ctx: CurrentContext,  # Dependency injection (FastMCP214+)
) -> dict:
    ctx.info("Starting my_tool operation")
    # ... tool logic ...
    return {"status": "success"}
```

#### Accessing Context in Helper Functions

```python
from fastmcp import get_context

async def helper_function():
    ctx = get_context()  # Get context from current request
    if ctx:
        ctx.debug("Helper function executing")
```

#### Logging Methods

- `await ctx.debug(message, extra={})` - Detailed diagnostics
- `await ctx.info(message, extra={})` - General operation progress
- `await ctx.warning(message, extra={})` - Deprecated usage or risk conditions
- `await ctx.error(message, extra={})` - Errors that allow continuation

#### Progress Reporting

For long-running operations, use progress reporting to update clients:

- `await ctx.report_progress(progress=50, total=100)` - Report percentage-based progress
- Useful for operations like file processing, batch operations, analysis tasks
- See [FastMCP Progress Reporting documentation](https://gofastmcp.com/servers/context#progress-reporting) for detailed patterns

#### Error Handling

- Use `ctx.error()` for non-fatal errors
- Use `ToolError` from FastMCP for fatal errors that should stop execution
- Ensure error masking is configured: `mcp = FastMCP("cortex", mask_error_details=True)`

### Hybrid Approach

**Recommended Strategy**: Use both Context logging and standard Python logging:

- **Context logging** (`ctx.*`): For client-visible messages, operation progress, warnings, errors
- **Standard Python logging** (`logger.*`): For server-side debugging, internal state, detailed diagnostics

This allows:

- Clients to see operation progress and errors via MCP protocol
- Server administrators to see detailed logs in stderr for debugging

## Implementation Steps

### Phase 1: Audit and Analysis (Week 1) — COMPLETED 2026-01-31

#### Step 1.1: Audit Current Logging Usage — DONE

- [x] Scan all tool files in `src/cortex/tools/` to identify:
  - Current logging patterns (`logger.debug`, `logger.info`, `logger.warning`, `logger.error`)
  - Error handling patterns
  - Missing logging in critical paths
  - Print statements or other ad-hoc logging

#### Step 1.2: Identify Tool Functions

- [ ] List all `@mcp.tool()` decorated functions
- [ ] Document current logging approach for each tool
- [ ] Identify helper functions that need `get_context()` access

#### Step 1.3: Define Logging Guidelines — DONE

- [x] Create `docs/development/logging-guidelines.md` with:

- When to use each log level
- Required metadata fields (request_id, tool_name, etc.)
- Message format standards
- Context logging vs standard logging decision tree

### Phase 2: Core Refactoring (Week 2)

#### Step 2.1: Update Server Configuration

- [ ] Check if `mask_error_details` should be enabled in `src/cortex/server.py`
- [ ] Verify FastMCP version supports `CurrentContext()` dependency injection
- [ ] Test Context access in a sample tool

#### Step 2.2: Create Logging Helper Utilities — DONE

- [x] Create `src/cortex/core/context_logging.py` with:
  - Helper functions for common logging patterns (`log_client`, `report_progress_safe`)
  - Context-aware logging wrapper (log to ctx when present, else std logger)
  - Typed with `Context[ServerSession, object]` for MCP SDK compatibility

#### Step 2.3: Refactor Core Tools — manage_file DONE, validate DONE, analyze DONE, configure DONE, markdown DONE, rules DONE

Start with high-priority tools:

- [x] `file_operations.py` - `manage_file` (optional `ctx: _MCPContext | None`; entry/validation/exit/error logging via `log_client`)
- [x] `validation_operations.py` - `validate` (optional `ctx: MCPContext | None`; entry/invalid check_type/exit/error via `log_client`; unit tests in TestValidateContextLogging)
- [x] `analysis_operations.py` - `analyze` (optional `ctx: MCPContext | None`; entry/invalid target/exit/error via `log_client`; _analyze_run_or_error; unit tests in TestAnalyzeContextLogging) — 2026-01-31
- [x] `configuration_operations.py` - `configure` (optional `ctx: MCPContext | None`; entry/invalid action/invalid component/exit/error via `log_client`; unit tests in TestConfigureContextLogging) — 2026-01-31
- [x] `markdown_operations.py` - `fix_markdown_lint` (optional `ctx: MCPContext | None`; entry/exit/error via `log_client`; unit tests in TestFixMarkdownLintContextLogging) — 2026-01-31
- [x] `roadmap_corruption.py` - `fix_roadmap_corruption` (optional `ctx: MCPContext | None`; entry/warning/exit/error via `log_client`; unit tests in TestFixRoadmapCorruptionContextLogging) — 2026-01-31
- [x] `rules_operations.py` - `rules` (optional `ctx: MCPContext | None`; entry/warning/exit/error via `log_client`; unit tests in TestRulesContextLogging) — 2026-01-31

For each tool:

- [ ] Add `ctx: CurrentContext` parameter (or use `get_context()` in helpers)
- [ ] Replace `logger.info()` with `await ctx.info()` for client-visible messages
- [ ] Replace `logger.warning()` with `await ctx.warning()` for warnings
- [ ] Replace `logger.error()` with `await ctx.error()` for non-fatal errors
- [ ] Add `await ctx.report_progress()` for long-running operations (file processing, batch operations, analysis)
- [ ] Use `ToolError` for fatal errors that should stop execution
- [ ] Keep `logger.debug()` for server-side detailed diagnostics

#### Step 2.4: Update Helper Functions

- [ ] Identify helper functions called from tools
- [ ] Update to use `get_context()` for logging when needed
- [ ] Ensure context is only accessed during request context

### Phase 3: Complete Tool Migration (Week 2 Step 3.1) Refactor Remaining Tools

- [x] `markdown_operations.py` — 2026-01-31
- [x] `rules_operations.py` — 2026-01-31
- [x] `phase1_foundation_*.py` tools — 2026-01-31 (get_version_history, get_memory_bank_stats, get_dependency_graph, rollback_file_version, cleanup_metadata_index; optional ctx and log_client; unit tests TestPhase1FoundationContextLogging, TestCleanupMetadataIndexContextLogging)
- [x] `phase2_linking.py` tools — 2026-01-31 (parse_file_links, validate_links, resolve_transclusions, get_link_graph; optional ctx and log_client; unit tests TestPhase2LinkingContextLogging)
- [x] `phase3_validation.py` tools — 2026-01-31 (N/A: 0 tools; all consolidated)
- [x] `phase4_optimization.py` tools — 2026-01-31 (phase4_optimization_handlers: load_context, load_progressive_context, summarize_content, get_relevance_scores; context_analysis_handlers: analyze_context_effectiveness, get_context_usage_statistics; optional ctx and log_client; TestPhase4OptimizationContextLogging, TestContextAnalysisContextLogging)
- [x] `phase5*.py` tools — 2026-01-31 (phase5_execution: apply_refactoring, provide_feedback; refactoring_operations: suggest_refactoring; optional ctx and log_client; TestPhase5ExecutionContextLogging, TestRefactoringOperationsContextLogging)
- [x] `phase8_structure.py` tools — 2026-01-31 (check_structure_health, get_structure_info; optional ctx and log_client; check_structure_health_impl, _check_structure_health_with_logging; TestPhase8StructureContextLogging)
- [x] `synapse_tools.py` — 2026-01-31 (sync_synapse, update_synapse_rule, get_synapse_rules, get_synapse_prompts, update_synapse_prompt; optional ctx and log_client; TestSynapseToolsContextLogging)
- [x] `pre_commit_tools.py` — 2026-01-31 (execute_pre_commit_checks, fix_quality_issues; optional ctx and log_client; TestPreCommitToolsContextLogging)

#### Step 3.2: Update Error Handling

- [ ] Review `src/cortex/core/mcp_failure_handler.py`
- [ ] Ensure it uses Context logging for client notifications
- [ ] Update exception handling to use `ctx.error()` where appropriate

### Phase 4: Testing and Validation (Week 3)

#### Step 4.1: Update Unit Tests

- [ ] Update test fixtures to mock `CurrentContext`
- [ ] Update tests to verify Context logging calls
- [ ] Test `get_context()` in helper functions
- Verify error logging behavior

#### Step 4.2: Integration Tests

- [ ] Test tools with real Context objects
- [ ] Verify logs appear in client responses
- [ ] Test error scenarios and logging

#### Step 4.3: Manual Testing

- [ ] Test each refactored tool manually
- [ ] Verify log messages appear correctly
- [ ] Check log levels are appropriate

### Phase 5: Documentation and Cleanup (Week 4)

#### Step 5.1 Update Documentation

- [ ] Update `docs/development/logging-guidelines.md`
- [ ] Update `docs/guides/troubleshooting.md` with Context logging info
- [ ] Add examples to tool documentation

#### Step 5.2: Code Review and Cleanup

- [ ] Remove unused logging imports
- Ensure consistent logging patterns
- [ ] Fix any linting/type errors

#### Step 5.3: Final Verification

- [ ] Run full test suite
- [ ] Verify code coverage maintained
- [ ] Check for any remaining standard logging that should be Context logging

## Files to Modify

### Core Files

- `src/cortex/server.py` - Verify FastMCP configuration
- `src/cortex/core/logging_config.py` - May need updates for hybrid approach
- `src/cortex/core/mcp_failure_handler.py` - Add Context logging
- `src/cortex/core/mcp_stability.py` - Add Context logging where appropriate

### Tool Files (All in `src/cortex/tools/`)

- `file_operations.py`
- `validation_operations.py`
- `analysis_operations.py`
- `configuration_operations.py`
- `markdown_operations.py`
- `rules_operations.py`
- `phase1_foundation_*.py` (multiple files)
- `phase2_linking.py`
- `phase3_validation.py`
- `phase4_optimization.py` (multiple files)
- `phase5_*.py` (multiple files)
- `phase8_structure.py`
- `synapse_tools.py`
- `pre_commit_tools.py`

### New Files

- `src/cortex/core/context_logging.py` - Helper utilities
- `docs/development/logging-guidelines.md` - Guidelines document

## Risks and Mitigations

### Risk 1: Too Many Logs

**Risk**: Excessive logging impacting performance or overwhelming clients  
**Mitigation**:

- Use appropriate log levels (debug only for detailed diagnostics)
- Limit log message size
- Use structured logging with filtering capabilities
- Use progress reporting (`ctx.report_progress()`) instead of frequent `ctx.info()` calls for long-running operations

### Risk 2: Missing Context

**Risk**: Context not available in some execution paths  
**Mitigation**:

- Always check if context exists before using: `ctx = get_context(); if ctx: ...`
- Fall back to standard logging if context unavailable
- Document when Context is available (only during request handling)

### Risk 3: Sensitive Information Exposure

**Risk**: Logging sensitive data in client-visible messages  
**Mitigation**:

- Review all `ctx.*` messages for sensitive data
- Use `mask_error_details=True` in FastMCP configuration
- Use `ToolError` for client-facing error messages (sanitized)

### Risk 4: Breaking Changes

**Risk**: Changes break existing functionality  
**Mitigation**:

- Comprehensive testing before and after changes
- Incremental migration (one tool at a time)
- Maintain backward compatibility where possible

### Risk 5: Version Compatibility

**Risk**: `CurrentContext()` dependency injection may not be available in current version  
**Mitigation**:

- Check FastMCP version and API availability
- Use `get_context()` as fallback if dependency injection not available
- Test with actual FastMCP version in use

## Timeline

- **Week 1**: Audit, analysis, and guidelines definition
- **Week 2**: Core refactoring (high-priority tools, helper utilities)
- **Week 3**: Complete tool migration and testing
- **Week 4**: Documentation, cleanup, and final verification

## Dependencies

- FastMCP 2.0+ with Context logging support
- Access to FastMCP documentation
- Existing test infrastructure
- Code review process

## Success Metrics

- [ ] 10% of tools use Context logging for client-visible messages
- [ ] All helper functions use `get_context()` when needed
- [ ] Test coverage maintained or improved
- [ ] No breaking changes to tool APIs
- [ ] Documentation complete and accurate
- [ ] All linting/type checks pass

## Notes

- This plan maintains the hybrid approach: Context logging for clients, standard logging for server-side debugging
- The `mcp_tool_wrapper` decorator may need updates to support Context injection
- Consider creating a helper decorator that automatically injects Context if not present
- **Progress Reporting**: For long-running operations (file processing, batch operations, analysis), use `ctx.report_progress()` instead of frequent log messages. This provides better UX with progress indicators. See [FastMCP Progress Reporting](https://gofastmcp.com/servers/context#progress-reporting) for patterns.
- **Context Availability**: Context is only available during MCP requests. Always check if context exists before using: `ctx = get_context(); if ctx: ...`
