# MCP Tool Timeout Strategy

## Overview

All Cortex MCP tools are protected with timeout mechanisms to prevent hanging operations and improve system reliability. This document describes the timeout strategy, categories, and how to select appropriate timeouts for new tools.

## Timeout Infrastructure

### Centralized Timeout Mechanism

All MCP tools use the `@mcp_tool_wrapper(timeout=...)` decorator from `cortex.core.mcp_stability` to add timeout protection. This provides:

- **Timeout enforcement**: Operations that exceed their timeout are automatically cancelled
- **Resource limits**: Concurrent operations are limited to prevent resource exhaustion
- **Connection stability**: Connection health checks and recovery mechanisms
- **Clear error messages**: Timeout errors provide actionable information

### Timeout Constants

Timeout values are defined in `cortex.core.constants`:

```python
MCP_TOOL_TIMEOUT_FAST = 60          # Fast operations (30-60s)
MCP_TOOL_TIMEOUT_MEDIUM = 120        # Medium operations (60-120s)
MCP_TOOL_TIMEOUT_COMPLEX = 300      # Complex operations (120-300s)
MCP_TOOL_TIMEOUT_VERY_COMPLEX = 600  # Very complex operations (300-600s)
MCP_TOOL_TIMEOUT_EXTERNAL = 120     # External operations (30-120s)
```

## Timeout Categories

### Fast Operations (60 seconds)

**Use for**: Simple, quick operations that should complete in under a minute.

**Examples**:

- Simple file reads/writes
- Metadata queries
- Configuration operations
- Health checks
- Structure information retrieval

**Tools using this category**:

- `check_mcp_connection_health`
- `check_structure_health`
- `get_structure_info`
- `configure`

### Medium Operations (120 seconds)

**Use for**: Operations that involve validation, parsing, or moderate file processing.

**Examples**:

- File operations with validation
- Link parsing and validation
- Dependency graph construction
- Version history queries
- Metadata cleanup

**Tools using this category**:

- `manage_file`
- `parse_file_links`
- `validate_links`
- `get_dependency_graph`
- `get_version_history`
- `get_link_graph`
- `rollback_file_version`
- `cleanup_metadata_index`
- `fix_roadmap_corruption`

### Complex Operations (300 seconds / 5 minutes)

**Use for**: Operations that process multiple files, perform complex analysis, or involve significant computation.

**Examples**:

- Context optimization
- Progressive loading
- Transclusion resolution
- Validation across all files
- Content summarization
- Relevance scoring

**Tools using this category**:

- `load_context`
- `load_progressive_context`
- `resolve_transclusions`
- `validate`
- `summarize_content`
- `get_relevance_scores`

### Very Complex Operations (600 seconds / 10 minutes)

**Use for**: Operations that perform comprehensive analysis, refactoring, or large-scale processing.

**Examples**:

- Refactoring analysis and execution
- Comprehensive analysis operations
- Large-scale file operations
- Rules indexing and retrieval

**Tools using this category**:

- `suggest_refactoring`
- `apply_refactoring`
- `analyze`
- `get_memory_bank_stats`
- `provide_feedback`
- `rules`

### External Operations (120 seconds)

**Use for**: Operations that interact with external systems, run commands, or perform network requests.

**Examples**:

- Git operations
- External command execution
- Network requests
- Pre-commit checks

**Tools using this category**:

- `sync_synapse`
- `update_synapse_rule`
- `update_synapse_prompt`
- `get_synapse_rules`
- `get_synapse_prompts`
- `execute_pre_commit_checks`
- `fix_quality_issues`

## How to Add Timeout to a New Tool

### Step 1: Import Required Modules

```python
from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM  # or appropriate category
from cortex.core.mcp_stability import mcp_tool_wrapper
from cortex.server import mcp
```

### Step 2: Apply Decorator

Add the `@mcp_tool_wrapper(timeout=...)` decorator immediately after `@mcp.tool()`:

```python
@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def my_new_tool(...) -> str:
    """Tool description."""
    # Tool implementation
    ...
```

### Step 3: Select Appropriate Timeout

Choose the timeout category based on operation complexity:

- **Fast (60s)**: Simple queries, health checks, config operations
- **Medium (120s)**: File operations, parsing, validation
- **Complex (300s)**: Multi-file processing, optimization, analysis
- **Very Complex (600s)**: Comprehensive analysis, refactoring
- **External (120s)**: Git, commands, network requests

## Internal Operations

For internal operations (not MCP tools) that use `asyncio.wait_for()`, use timeout constants from `cortex.core.constants`:

```python
from cortex.core.constants import GIT_OPERATION_TIMEOUT_SECONDS

async def _run_git_command(cmd: list[str]) -> dict[str, object]:
    process = await asyncio.wait_for(
        asyncio.create_subprocess_exec(*cmd, ...),
        timeout=GIT_OPERATION_TIMEOUT_SECONDS,
    )
    ...
```

## Timeout Behavior

### Successful Completion

When an operation completes within its timeout:

- Result is returned normally
- No timeout error is raised
- Connection health is maintained

### Timeout Exceeded

When an operation exceeds its timeout:

- `TimeoutError` is raised with clear message
- Operation is cancelled automatically
- Connection health is checked
- Error message includes timeout value and operation name

### Error Messages

Timeout errors follow this format:

```text
MCP tool <tool_name> exceeded timeout of <timeout>s
```

## Troubleshooting

### Tool Times Out Prematurely

**Symptoms**: Tool fails with `TimeoutError` even for simple operations.

**Solutions**:

1. Check if timeout value is appropriate for operation complexity
2. Verify operation isn't blocking on I/O unnecessarily
3. Consider increasing timeout if operation legitimately needs more time
4. Check for infinite loops or deadlocks in operation logic

### Tool Hangs Despite Timeout

**Symptoms**: Tool hangs indefinitely even with timeout wrapper.

**Possible Causes**:

1. Operation is blocking event loop (synchronous I/O)
2. Timeout wrapper not applied correctly
3. Operation is in infinite loop before timeout check

**Solutions**:

1. Ensure all I/O operations are async
2. Verify `@mcp_tool_wrapper()` is applied correctly
3. Check operation logic for infinite loops
4. Use `asyncio.timeout()` for internal async operations

### Timeout Value Too Long

**Symptoms**: Tools take too long to fail, poor user experience.

**Solutions**:

1. Review timeout category selection
2. Consider if operation can be optimized
3. Break large operations into smaller chunks
4. Use progressive loading for large datasets

## Best Practices

1. **Always use timeout wrapper**: Every `@mcp.tool()` should have `@mcp_tool_wrapper(timeout=...)`
2. **Choose appropriate category**: Match timeout to operation complexity
3. **Use constants**: Never hardcode timeout values, use constants from `cortex.core.constants`
4. **Test timeout behavior**: Verify tools timeout correctly in tests
5. **Document timeout selection**: Add comments explaining why a specific timeout was chosen
6. **Monitor timeout errors**: Track timeout frequency to optimize timeout values

## Verification

To verify all tools have timeout protection:

```bash
# Count tools with timeout wrapper
find src/cortex/tools -name "*.py" -exec grep -l "@mcp_tool_wrapper" {} \; | wc -l

# Count tools without timeout wrapper
find src/cortex/tools -name "*.py" -exec grep -l "@mcp.tool()" {} \; | wc -l

# These counts should match
```

## Related Documentation

- `cortex.core.mcp_stability`: Timeout implementation details
- `cortex.core.constants`: Timeout constant definitions
- Phase 34 Plan: Implementation details and rationale
