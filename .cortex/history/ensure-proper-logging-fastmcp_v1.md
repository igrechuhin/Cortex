# Development Plan: Ensure Proper Logging According to FastMCP Context

## Status

Planning

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

According toFastMCP Context Logging documentation](<https://gofastmcp.com/servers/context#logging>):

- Logs are sent back to the client via MCP protocol (not just stderr)
- Provides structured logging with metadata (request_id, client_id, etc.)
- Better integration with client-side debugging and monitoring
- Supports different log levels: `debug`, `info`, `warning`, `error`
- Can be accessed via `CurrentContext()` dependency or `get_context()` function

## Scope

### In Scope

- All MCP tool functions (`@mcp.tool()` decorated functions)
- Helper functions called from tools (using `get_context()`)
- Error handling and exception logging
- Operation entry/exit logging
- Progress and state change logging
- Middleware logging (if applicable)

### Out of Scope

- Server startup/shutdown logging (can remain as standard Python logging)
- Internal manager/business logic logging (can remain as standard Python logging for server-side debugging)
- Test-only logging

## Success Criteria

1. **All tools use Context logging** for client-visible messages:
   - Entry logging: `ctx.info("Starting operation X")`
   - Progress logging: `ctx.info("Processing item Y of Z")`
   - Warning logging: `ctx.warning("Non-critical issue: ...")`
   - Error logging: `ctx.error("Operation failed: ...")` or `ToolError` for fatal errors2 **Helper functions** use `get_context()` for logging when not passed `ctx` parameter

2. **Structured logging** with metadata (request_id, tool_name, etc.) where applicable

3. **No ad-hoc print statements** or discarded exception traces
5nsistent logging format** across all tools

6ts updated** to verify Context logging behavior

1. **Documentation updated** with logging guidelines

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

- `await ctx.debug(message, extra=[object Object])` - Detailed diagnostics
- `await ctx.info(message, extra=[object Object]})` - General operation progress
- `await ctx.warning(message, extra={})` - Deprecated usage or risk conditions
- `await ctx.error(message, extra={})` - Errors that allow continuation

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

### Phase 1: Audit and Analysis (Week1#### Step10.1 Audit Current Logging Usage

- ] Scan all tool files in `src/cortex/tools/` to identify:
  - Current logging patterns (`logger.debug`, `logger.info`, `logger.warning`, `logger.error`)
  - Error handling patterns
  - Missing logging in critical paths
  - Print statements or other ad-hoc logging

#### Step 1.2: Identify Tool Functions

-t all `@mcp.tool()` decorated functions

- [ ] Document current logging approach for each tool
- ] Identify helper functions that need `get_context()` access

#### Step1.3: Define Logging Guidelines

-Create `docs/development/logging-guidelines.md` with:

- When to use each log level
- Required metadata fields (request_id, tool_name, etc.)
- Message format standards
- Context logging vs standard logging decision tree

### Phase 2: Core Refactoring (Week2)

#### Step 2.1: Update Server Configuration

-Check if `mask_error_details` should be enabled in `src/cortex/server.py`

- [ ] Verify FastMCP version supports `CurrentContext()` dependency injection
- [ ] Test Context access in a sample tool

#### Step2.2 Create Logging Helper Utilities

- [ ] Create `src/cortex/core/context_logging.py` with:
  - Helper functions for common logging patterns
  - Context-aware logging wrapper
  - Metadata extraction utilities

#### Step 23efactor Core Tools

Start with high-priority tools:

- [ ] `file_operations.py` - `manage_file`
- [ ] `validation_operations.py` - `validate`
- sis_operations.py` - `analyze`
- ] `configuration_operations.py` - `configure`

For each tool:

- [ ] Add `ctx: CurrentContext` parameter (or use `get_context()` in helpers)
- [ ] Replace `logger.info()` with `ctx.info()` for client-visible messages
- [ ] Replace `logger.warning()` with `ctx.warning()` for warnings
-place `logger.error()` with `ctx.error()` for non-fatal errors
- [ ] Use `ToolError` for fatal errors that should stop execution
- ] Keep `logger.debug()` for server-side detailed diagnostics

#### Step 2.4: Update Helper Functions

- [ ] Identify helper functions called from tools
- ] Update to use `get_context()` for logging when needed
- [ ] Ensure context is only accessed during request context

### Phase 3omplete Tool Migration (Week 2 Step 31 Refactor Remaining Tools

- ] `markdown_operations.py`
- ] `rules_operations.py`
- [ ] `phase1foundation_*.py` tools
- [ ] `phase2king.py` tools
- ] `phase3_validation.py` tools
- ] `phase4_optimization.py` tools
- ] `phase5*.py` tools
- ] `phase8_structure.py` tools
- ] `synapse_tools.py`
- [ ] `pre_commit_tools.py`

#### Step 3.2pdate Error Handling

- [ ] Review `src/cortex/core/mcp_failure_handler.py`
- ] Ensure it uses Context logging for client notifications
- [ ] Update exception handling to use `ctx.error()` where appropriate

### Phase 4ting and Validation (Week 3)

#### Step 4.1: Update Unit Tests

- [ ] Update test fixtures to mock `CurrentContext`
- tests to verify Context logging calls
- [ ] Test `get_context()` in helper functions
-erify error logging behavior

#### Step 4.2: Integration Tests

- [ ] Test tools with real Context objects
- [ ] Verify logs appear in client responses
- [ ] Test error scenarios and logging

#### Step 43 Manual Testing

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

#### Step 5.3Final Verification

- ] Run full test suite
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
- `phase3validation.py`
- `phase4_optimization.py` (multiple files)
- `phase5_*.py` (multiple files)
- `phase8tructure.py`
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

### Risk 2: Missing Context

**Risk**: Context not available in some execution paths  
**Mitigation**:

- Always check if context exists before using: `ctx = get_context(); if ctx: ...`
- Fall back to standard logging if context unavailable
- Document when Context is available (only during request handling)

### Risk3ensitive Information Exposure

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

### Risk5 Version Compatibility

**Risk**: `CurrentContext()` dependency injection may not be available in current version  
**Mitigation**:

- Check FastMCP version and API availability
- Use `get_context()` as fallback if dependency injection not available
- Test with actual FastMCP version in use

## Timeline

- **Week1 Audit, analysis, and guidelines definition
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
- ll helper functions use `get_context()` when needed
- [ ] Test coverage maintained or improved
- [ ] No breaking changes to tool APIs
- umentation complete and accurate
- [ ] All linting/type checks pass

## Notes

- This plan maintains the hybrid approach: Context logging for clients, standard logging for server-side debugging
- The `mcp_tool_wrapper` decorator may need updates to support Context injection
- Consider creating a helper decorator that automatically injects Context if not present
