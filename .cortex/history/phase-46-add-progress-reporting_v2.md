# Phase 46 Add Progress Reporting to Long-Running MCP Tools

**Status**: PLANNING  
**Created**:226-20
**Priority**: Medium  
**Estimated Effort**: 16-24urs

## Goal

Add progress reporting to long-running MCP tools using FastMCP's `Context.report_progress()` capability. This will improve user experience by providing real-time feedback during operations that take longer than 10econds.

## Context

### Current State

- **FastMCP Version**: 2.14(migrated in Phase 41)
- **Total Tools**: 53+ MCP tools across 21+ modules
- **Timeout Categories**:
  - `MCP_TOOL_TIMEOUT_FAST`:60le operations)
  - `MCP_TOOL_TIMEOUT_MEDIUM`: 120s (validation, parsing)
  - `MCP_TOOL_TIMEOUT_COMPLEX`: 300 (context optimization, progressive loading)
  - `MCP_TOOL_TIMEOUT_VERY_COMPLEX`: 600(refactoring, comprehensive analysis)
  - `MCP_TOOL_TIMEOUT_EXTERNAL`: 120s (git, external commands)
- **Tool Wrapper**: All tools use `@mcp_tool_wrapper(timeout=...)` from `cortex.core.mcp_stability`
- **No Progress Reporting**: Currently no tools use `ctx.report_progress()`

### FastMCP Context Capability

According to [FastMCP Context documentation](https://gofastmcp.com/servers/context#what-is-context), the `Context` object provides:

- **Progress Reporting**: `await ctx.report_progress(progress=50, total=100)` - Update clients on long-running operations
- **Access Methods**:
  - `CurrentContext()` - Dependency injection (preferred for FastMCP 2.14  - `get_context()` - Function to retrieve context from nested calls

### Problem Statement

Long-running tools (especially those with `COMPLEX` or `VERY_COMPLEX` timeouts) can take 5-10 minutes to complete. Users have no visibility into:

- Whether the tool is still running
- What stage of execution it's in
- Estimated completion time
- Progress percentage

This leads to:

- User uncertainty during long operations
- Inability to cancel operations that appear hung
- Poor user experience for complex operations

### Business Value

- **Better UX**: Users see real-time progress during long operations
- **Reduced Anxiety**: Clear feedback prevents users from thinking tools are hung
- **Improved Debugging**: Progress reports help identify slow stages
- **Professional Polish**: Modern MCP servers should provide progress feedback

## Approach

### High-Level Strategy

1 **Identify Candidate Tools**: Tools with timeouts ≥ 120(MEDIUM, COMPLEX, VERY_COMPLEX)
2. **Set Progress Threshold**: Report progress for tools running longer than 10conds3 **Implement Progress Reporting**: Add `ctx.report_progress()` calls at key execution stages
4. **Two-Tier Approach**:

- **Automatic**: Enhance `mcp_tool_wrapper` to report progress for long-running tools
- **Manual**: Add explicit progress reports in tool implementation functions
5Testing**: Verify progress reporting works correctly with FastMCP clients

### Progress Reporting Threshold

**Decision**: Use **10 seconds** as the threshold for starting progress reports.

**Rationale**:

- User-suggested threshold
- FastMCP documentation recommends progress for "long-running operations"
- 10seconds is long enough to warrant feedback but short enough to be useful
- Aligns with timeout categories (MEDIUM=120s, COMPLEX=30VERY_COMPLEX=600s)

### Tool Categorization

**Tools Requiring Progress Reporting** (timeout ≥ 1201Tools (300)**:

- `optimize_context` - Context optimization
- `load_progressive_context` - Progressive context loading
- `summarize_content` - Content summarization
- `get_relevance_scores` - Relevance scoring
- `resolve_transclusions` - Transclusion resolution
- `validate_links` - Link validation (all files)
- `validate` - Comprehensive validation

2*VERY_COMPLEX Tools (600)**:

- `suggest_refactoring` - Refactoring suggestions
- `apply_refactoring` - Refactoring execution
- `analyze` - Memory Bank analysis
- `sync_synapse` - Synapse synchronization

1. **MEDIUM Tools (120** - Consider on case-by-case basis:
   - `manage_file` - File operations with validation
   - `validate_links` - Link validation (single file)
   - `get_dependency_graph` - Dependency graph construction

## Implementation Plan

### Step 1 Add Progress Reporting Helper Utilities

**Location**: `src/cortex/core/progress.py` (new file)

**Tasks**:

- Create `ProgressReporter` class to manage progress reporting
- Handle context retrieval (`CurrentContext()` or `get_context()`)
- Provide convenience methods for common progress patterns
- Handle cases where context is unavailable (tests, non-MCP contexts)

**Implementation Pattern**:

```python
from fastmcp import CurrentContext
from typing import Optional
import time

class ProgressReporter:
    Helper for reporting progress in MCP tools."""
    
    def __init__(self, total_steps: int = 100, tool_name: str = ""):
        self.total_steps = total_steps
        self.current_step = 0 self.tool_name = tool_name
        self._start_time: Optional[float] =null 
    async def start(self) -> None:
        "art progress reporting."""
        self._start_time = time.perf_counter()
        await self.report(0, "Starting operation...")
    
    async def report(self, progress: int, message: str = ) -> None:
        """Report progress.
        
        Args:
            progress: Progress value (0-100) or step number (0_steps)
            message: Optional progress message
        "        try:
            ctx = CurrentContext()
            if ctx:
                # Normalize progress to 0-100
                if progress > self.total_steps:
                    progress_pct = 100                else:
                    progress_pct = int((progress / self.total_steps) * 10)
                
                await ctx.report_progress(
                    progress=progress_pct,
                    total=10
                    message=f"{self.tool_name}: {message}" if message else null             )
        except Exception:
            # Context not available (tests, non-MCP contexts) - silently ignore
            pass
    
    async def step(self, message: str = "") -> None:
        ort next step."""
        self.current_step +=1        await self.report(self.current_step, message)
    
    async def complete(self, message: str = "Complete") -> None:
        "Report completion."
        await self.report(10essage)
```

**Deliverables**:

- `ProgressReporter` class with helper methods
- Unit tests (90 coverage)
- Documentation

**Estimated Time**: 4-6### Step 2: Enhance `mcp_tool_wrapper` with Automatic Progress Reporting

**Location**: `src/cortex/core/mcp_stability.py`

**Tasks**:

- Add optional `enable_progress` parameter to `mcp_tool_wrapper`
- Track execution time and report progress at intervals (every 10conds)
- Report progress automatically for tools with timeouts ≥ 120vide generic progress messages ("Processing...", "50% complete", etc.)

**Implementation Pattern**:

```python
def mcp_tool_wrapper(
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
    enforce_failure_protocol: bool = True,
    enable_progress: bool | None = None,  # None = auto-detect based on timeout
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
   ecorator for MCP tools with optional progress reporting.
    
    Args:
        timeout: Maximum execution time in seconds
        enforce_failure_protocol: If True, enforce MCP tool failure protocol
        enable_progress: If True, enable progress reporting. If null auto-enable
            for timeouts >= 120nds.
     # Auto-enable progress for long-running tools
    if enable_progress is None:
        enable_progress = timeout >= 1200    
    # ... existing wrapper code ...
    
    @functools.wraps(underlying_func)
    async def wrapper(*args: object, **kwargs: object) -> T:
     ped function with stability protections and progress reporting."""
        tool_name = underlying_func.__name__
        
        if enable_progress:
            # Start progress reporting
            start_time = time.perf_counter()
            progress_interval = 10  # Report every10econds
            
            async def report_progress_task():
         round task to report progress periodically."""
                try:
                    ctx = CurrentContext()
                    if ctx:
                        while True:
                            await asyncio.sleep(progress_interval)
                            elapsed = time.perf_counter() - start_time
                            if elapsed >= timeout:
                                break
                            
                            # Calculate progress based on elapsed time
                            progress_pct = min(int((elapsed / timeout) * 10), 95)
                            await ctx.report_progress(
                                progress=progress_pct,
                                total=100,
                                message=f"{tool_name}: Processing... ({progress_pct}%)"
                            )
                except Exception:
                    # Context not available or operation completed
                    pass
            
            # Start progress reporting task
            progress_task = asyncio.create_task(report_progress_task())
        
        try:
            # Execute tool with stability protections
            result = await with_mcp_stability(func_with_timeout, timeout=timeout)
            
            # Report completion
            if enable_progress:
                try:
                    ctx = CurrentContext()
                    if ctx:
                        await ctx.report_progress(
                            progress=100,
                            total=100
                            message=f"{tool_name}: Complete"
                        )
                except Exception:
                    pass
                finally:
                    progress_task.cancel()
            
            # ... existing validation and error handling ...
            return result
        finally:
            if enable_progress:
                progress_task.cancel()
```

**Challenges**:

- Background task management (cancel on completion)
- Context availability checks
- Progress calculation based on elapsed time vs. actual work

**Deliverables**:

- Enhanced `mcp_tool_wrapper` with progress reporting
- Unit tests for progress reporting
- Integration tests

**Estimated Time**:6hours

### Step 3 Add Manual Progress Reports to Complex Tool Implementations

**Location**: Tool implementation files (e.g., `src/cortex/tools/phase4_*.py`)

**Tasks**:

- Identify key execution stages in complex tools
- Add `ProgressReporter` instances at tool entry points
- Report progress at major milestones:
  - Setup/initialization (0-10%)
  - Data loading (1040%)
  - Processing/analysis (40-90)
  - Formatting results (90-100xample Implementation**:

```python
async def optimize_context_impl(
    mgrs: dict[str, object],
    task_description: str,
    token_budget: int | null   strategy: str,
) -> OptimizeContextResult | OptimizeContextErrorResult:
    ementation logic for optimize_context tool."    from cortex.core.progress import ProgressReporter
    
    progress = ProgressReporter(total_steps=4, tool_name="optimize_context")
    await progress.start()
    
    try:
        # Step 1: Setup managers (0-25%)
        await progress.report(0, "Setting up managers...")
        (
            optimization_config,
            context_optimizer,
            metadata_index,
            fs_manager,
        ) = await _setup_optimization_managers(mgrs)
        
        # Step 2: Read files (25
        await progress.report(25, "Reading files...")
        if token_budget is None:
            token_budget = optimization_config.get_token_budget()
        
        files_content, files_metadata = await _read_all_files_for_optimization(
            metadata_index, fs_manager
        )
        
        # Step 3 Optimize context (50-90%)
        await progress.report(50, "Optimizing context...")
        result = await context_optimizer.optimize_context(
            task_description=task_description,
            files_content=files_content,
            files_metadata=files_metadata,
            token_budget=token_budget,
            strategy=strategy,
        )
        
        # Step4: Format results (90100%)
        await progress.report(90rmatting results...")
        formatted = _format_optimization_result(
            task_description, token_budget, strategy, result
        )
        
        await progress.complete("Optimization complete")
        return formatted
    except Exception as e:
        await progress.report(100, f"Error: {str(e)}")
        return OptimizeContextErrorResult(...)
```

**Tools to Update**:

1. `optimize_context_impl` -4stages2d_progressive_context_impl` - 3-5 stages
2. `summarize_content_impl` - 3es
3. `get_relevance_scores_impl` - 3 stages
4. `resolve_transclusions_impl` - 2-3 stages6`validate_links_impl` (all files) -2 stages
5. `suggest_refactoring_impl` - 4 stages8y_refactoring_impl` - 5-6ges

**Deliverables**:

- Progress reporting in 8+ complex tool implementations
- Updated tool handlers to pass progress context
- Integration tests

**Estimated Time**: 6ours

### Step4: Testing and Validation

**Location**: `tests/` directory

**Tasks**:

- Unit tests for `ProgressReporter` class
- Unit tests for enhanced `mcp_tool_wrapper` progress reporting
- Integration tests with FastMCP server
- Mock context for testing
- Verify progress reports are sent correctly
- Test edge cases (context unavailable, rapid completion, etc.)

**Test Strategy**:

```python
# Test ProgressReporter
async def test_progress_reporter():
    reporter = ProgressReporter(total_steps=4, tool_name="test_tool")
    # Mock CurrentContext()
    # Verify report_progress() calls
    
# Test mcp_tool_wrapper progress
async def test_wrapper_progress():
    @mcp.tool()
    @mcp_tool_wrapper(timeout=300, enable_progress=True)
    async def slow_tool():
        await asyncio.sleep(15)  # Trigger progress reports
        return {"status": "success"}
    
    # Mock context and verify progress reports
    
# Test tool implementation progress
async def test_optimize_context_progress():
    # Mock managers and verify progress stages
    result = await optimize_context_impl(...)
    # Verify progress was reported at each stage
```

**Deliverables**:

- Comprehensive test suite (90ge)
- Integration test results
- Performance impact assessment

**Estimated Time**:2urs

## Design Decisions

### Decision 1utomatic vs. Manual Progress Reporting

**Decision**: **Hybrid Approach**

- **Automatic**: `mcp_tool_wrapper` provides generic time-based progress for all long-running tools
- **Manual**: Tool implementations provide detailed stage-based progress for complex operations

**Rationale**:

- Automatic progress ensures all long-running tools have basic feedback
- Manual progress provides meaningful stage information
- Hybrid approach balances coverage and detail

### Decision 2: Progress Threshold

**Decision**: **10 seconds** (user-suggested)

**Rationale**:

- FastMCP documentation recommends progress for "long-running operations"
- 10 seconds is long enough to warrant feedback
- Aligns with timeout categories (tools with 120outs)

### Decision 3s Calculation Method

**Decision**: **Time-based for automatic, Stage-based for manual**

**Rationale**:

- Time-based progress is simple and works for all tools
- Stage-based progress is more accurate and informative
- Tools can override automatic progress with manual reports

### Decision 4: Context Availability Handling

**Decision**: **Silently ignore if context unavailable**

**Rationale**:

- Tools may run in non-MCP contexts (tests, direct calls)
- Progress reporting is a UX enhancement, not a requirement
- Failures should not break tool execution

## Success Criteria

1. ✅ All tools with timeouts ≥ 120eport progress automatically
2omplex tools (COMPLEX, VERY_COMPLEX) have detailed stage-based progress
3Progress reports appear in MCP clients (Claude Desktop, Cursor)
2. ✅ No performance degradation from progress reporting
3. ✅ Tests pass with 90%+ coverage6. ✅ Progress reporting works in both MCP and test contexts

## Risks and Mitigations

### Risk 1: Context Unavailable in Some Scenarios

**Mitigation**: Gracefully handle missing context, don't fail tool execution

### Risk 2erformance Impact

**Mitigation**:

- Use background tasks for automatic progress (non-blocking)
- Limit progress report frequency (every 10s)
- Measure performance impact in tests

### Risk3rogress Reports Not Visible in Clients

**Mitigation**:

- Test with multiple MCP clients (Claude Desktop, Cursor)
- Verify FastMCP 2.140.3progress reporting support
- Document client requirements

### Risk 4: Progress Calculation Inaccuracy

**Mitigation**:

- Use stage-based progress for complex tools (more accurate)
- Time-based progress is approximate but better than nothing
- Allow tools to override automatic progress

## Dependencies

- **FastMCP2.14 Already migrated (Phase 41*CurrentContext()**: Available in FastMCP2.14*MCP Client Support**: Clients must support progress reporting (verify)

## Future Enhancements

1. **Progress Cancellation**: Allow clients to cancel long-running operations
2. **Progress History**: Track progress reports for debugging
3. **Custom Progress Messages**: Allow tools to provide detailed status messages
4. **Progress Analytics**: Analyze which tools take longest and optimize

## References

- [FastMCP Context Documentation](https://gofastmcp.com/servers/context#what-is-context)
- Phase 41: FastMCP 2.0 Migration
- `src/cortex/core/mcp_stability.py` - Tool wrapper implementation
- `src/cortex/core/constants.py` - Timeout constants
- `src/cortex/tools/phase4_*.py` - Complex tool implementations
