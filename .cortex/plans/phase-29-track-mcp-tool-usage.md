# Phase 29: Track MCP Tool Usage for Optimization

**Status**: PLANNING  
**Created**: 2026-01-16  
**Priority**: Medium  
**Estimated Effort**: 40-60 hours

## Goal

Implement comprehensive tracking of Cortex MCP tool usage to collect real-world usage statistics. Use this data to optimize the number of published tools by identifying unused or rarely-used tools that can be deprecated, consolidated, or removed.

## Context

### Current State

- Cortex MCP server has **54 tools + 7 prompts** (61 total) registered via `@mcp.tool()` decorators
- Tools are organized across 21+ modules in `src/cortex/tools/`
- No current mechanism to track which tools are actually being used
- All tools are published regardless of usage frequency
- Tool registration happens via FastMCP decorators in `cortex.server.mcp`

### Problem Statement

Without usage tracking, we cannot:

- Identify unused tools that add maintenance overhead
- Understand which tools are most critical to users
- Make data-driven decisions about tool deprecation
- Optimize tool discovery and organization
- Measure the impact of tool changes

### Business Value

- **Reduced Maintenance**: Remove or deprecate unused tools to reduce code complexity
- **Better UX**: Focus development on frequently-used tools
- **Data-Driven Decisions**: Use real usage data instead of assumptions
- **Performance**: Fewer tools = faster tool discovery and registration
- **Documentation**: Understand actual tool usage patterns for better documentation

## Approach

### High-Level Strategy

1. **Instrumentation Layer**: Add usage tracking to tool execution without modifying tool implementations
2. **Data Collection**: Capture tool name, timestamp, parameters (anonymized), success/failure, execution time
3. **Storage**: Persist usage data to `.cortex/.cache/usage/` directory with JSON files
4. **Analytics**: Provide MCP tools to query and analyze usage statistics
5. **Optimization Recommendations**: Generate reports identifying candidates for deprecation/removal

### Design Principles

- **Non-Intrusive**: Tracking should not affect tool performance or behavior
- **Privacy-Conscious**: Anonymize parameters, respect user privacy
- **Low Overhead**: Minimal performance impact on tool execution
- **Configurable**: Allow users to opt-out or configure tracking granularity
- **Backward Compatible**: Existing tools continue to work without modification

## Implementation Steps

### Step 1: Design Usage Tracking Architecture

**Tasks**:

- Design data model for usage events (tool name, timestamp, duration, success, error type)
- Design storage format (JSON files with daily/hourly rotation)
- Design anonymization strategy for parameters (hash sensitive data, remove PII)
- Design aggregation strategy (daily/weekly/monthly summaries)
- Define retention policy (e.g., 90 days of detailed data, 1 year of aggregated data)

**Deliverables**:

- Architecture document in `docs/architecture/tool-usage-tracking.md`
- Data model specification (TypedDict schemas)
- Storage format specification

**Estimated Time**: 4-6 hours

### Step 2: Implement Usage Tracking Manager

**Location**: `src/cortex/managers/usage_tracker.py`

**Tasks**:

- Create `UsageTracker` manager class with async methods
- Implement event recording: `record_tool_usage(tool_name, duration, success, error_type)`
- Implement parameter anonymization: `_anonymize_params(params) -> dict[str, object]`
- Implement storage: `_persist_event(event)` to JSON files
- Implement file rotation: Daily files in `.cortex/.cache/usage/YYYY-MM-DD.json`
- Implement aggregation: Generate daily/weekly summaries
- Add configuration: Enable/disable tracking, retention period, anonymization level

**Key Methods**:

```python
class UsageTracker:
    async def record_tool_usage(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error_type: str | None = None,
        params_hash: str | None = None
    ) -> None
    
    async def get_usage_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        tool_name: str | None = None
    ) -> dict[str, object]
    
    async def get_unused_tools(
        self,
        days: int = 90,
        min_usage_count: int = 0
    ) -> list[str]
```

**Deliverables**:

- `UsageTracker` manager class
- Unit tests (90%+ coverage)
- Integration with manager initialization

**Estimated Time**: 8-10 hours

### Step 3: Implement Tool Execution Wrapper

**Location**: `src/cortex/core/tool_wrapper.py`

**Tasks**:

- Create decorator/wrapper to instrument `@mcp.tool()` functions
- Wrap tool execution with timing and error tracking
- Extract tool name from function metadata
- Anonymize parameters before recording
- Record usage event after tool execution (success or failure)
- Handle async and sync tools uniformly
- Ensure wrapper doesn't break tool signatures or return values

**Implementation Pattern**:

```python
def track_tool_usage(func: Callable) -> Callable:
    """Decorator to track MCP tool usage."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        success = True
        error_type = None
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            success = False
            error_type = type(e).__name__
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            tool_name = func.__name__
            await usage_tracker.record_tool_usage(
                tool_name, duration_ms, success, error_type
            )
    return wrapper
```

**Challenges**:

- FastMCP decorator order (tracking decorator must wrap `@mcp.tool()`)
- Parameter extraction and anonymization
- Async/sync compatibility
- Error handling without breaking tool behavior

**Deliverables**:

- Tool wrapper/decorator implementation
- Integration guide for existing tools
- Unit tests

**Estimated Time**: 10-12 hours

### Step 4: Integrate Tracking into Tool Registration

**Tasks**:

- Modify `cortex.server` to wrap all `@mcp.tool()` registrations
- OR: Create tool registration helper that automatically adds tracking
- Ensure all 54 tools are tracked without manual changes
- Test that tool behavior is unchanged
- Verify tracking works for both sync and async tools

**Approach Options**:

**Option A: Decorator Chain**

```python
from cortex.core.tool_wrapper import track_tool_usage

@mcp.tool()
@track_tool_usage
async def my_tool(...):
    ...
```

**Option B: Registration Wrapper**

```python
def register_tracked_tool(mcp_server, func):
    """Register tool with automatic usage tracking."""
    tracked_func = track_tool_usage(func)
    mcp_server.tool()(tracked_func)
```

**Option C: FastMCP Monkey-Patch**

- Intercept FastMCP's tool registration to add tracking automatically
- Most transparent but requires framework knowledge

**Deliverables**:

- Integration implementation
- All tools automatically tracked
- Tests verifying tracking works

**Estimated Time**: 6-8 hours

### Step 5: Create Usage Analytics MCP Tools

**Location**: `src/cortex/tools/usage_analytics.py`

**Tasks**:

- Create `get_tool_usage_stats` MCP tool:
  - Query usage statistics for date range
  - Filter by tool name
  - Return counts, success rates, average duration, error rates
- Create `get_unused_tools` MCP tool:
  - Identify tools with zero or minimal usage
  - Configurable threshold (e.g., < 5 uses in 90 days)
  - Return list with last usage date
- Create `get_tool_usage_report` MCP tool:
  - Generate comprehensive usage report
  - Include top/bottom tools by usage
  - Include trends (increasing/decreasing usage)
  - Export to markdown or JSON
- Create `get_optimization_recommendations` MCP tool:
  - Analyze usage patterns
  - Recommend tools for deprecation
  - Recommend tools for consolidation
  - Provide reasoning based on usage data

**Tool Signatures**:

```python
@mcp.tool()
async def get_tool_usage_stats(
    start_date: str | None = None,  # YYYY-MM-DD
    end_date: str | None = None,
    tool_name: str | None = None
) -> dict[str, object]:
    """Get usage statistics for MCP tools."""

@mcp.tool()
async def get_unused_tools(
    days: int = 90,
    min_usage_count: int = 0
) -> dict[str, object]:
    """Identify unused or rarely-used tools."""

@mcp.tool()
async def get_tool_usage_report(
    format: str = "markdown",  # "markdown" | "json"
    include_recommendations: bool = True
) -> dict[str, object]:
    """Generate comprehensive usage report."""

@mcp.tool()
async def get_optimization_recommendations(
    min_usage_threshold: int = 5,
    days: int = 90
) -> dict[str, object]:
    """Get recommendations for tool optimization."""
```

**Deliverables**:

- 4 new MCP tools for usage analytics
- Comprehensive unit tests
- Documentation with examples

**Estimated Time**: 8-10 hours

### Step 6: Add Configuration and Privacy Controls

**Location**: `.cortex/config/usage_tracking.json`

**Tasks**:

- Create configuration file for usage tracking
- Options:
  - `enabled`: bool (default: true)
  - `anonymize_params`: bool (default: true)
  - `retention_days`: int (default: 90)
  - `aggregation_enabled`: bool (default: true)
  - `opt_out_tools`: list[str] (tools to exclude from tracking)
- Add configuration management to `UsageTracker`
- Respect opt-out settings
- Add privacy notice/documentation

**Configuration Schema**:

```json
{
  "enabled": true,
  "anonymize_params": true,
  "retention_days": 90,
  "aggregation_enabled": true,
  "opt_out_tools": [],
  "min_duration_ms": 0.0
}
```

**Deliverables**:

- Configuration file and schema
- Configuration management in `UsageTracker`
- Privacy documentation

**Estimated Time**: 4-6 hours

### Step 7: Implement Data Aggregation and Cleanup

**Tasks**:

- Implement daily aggregation: Summarize hourly data into daily stats
- Implement weekly aggregation: Summarize daily data into weekly stats
- Implement monthly aggregation: Summarize weekly data into monthly stats
- Implement cleanup job: Remove old detailed data based on retention policy
- Add background task or on-demand aggregation
- Optimize storage: Compress old data, use efficient formats

**Deliverables**:

- Aggregation logic
- Cleanup job
- Storage optimization

**Estimated Time**: 6-8 hours

### Step 8: Testing and Validation

**Tasks**:

- Unit tests for `UsageTracker` (90%+ coverage)
- Unit tests for tool wrapper
- Integration tests: Verify tracking works for all tools
- Performance tests: Measure overhead (target: < 1ms per tool call)
- Privacy tests: Verify parameter anonymization
- End-to-end tests: Full workflow from tool call to analytics report
- Test data cleanup and aggregation

**Test Coverage Requirements**:

- `UsageTracker`: 90%+ coverage
- Tool wrapper: 90%+ coverage
- Analytics tools: 90%+ coverage
- Integration: All tools tracked correctly

**Deliverables**:

- Comprehensive test suite
- Performance benchmarks
- Test documentation

**Estimated Time**: 8-10 hours

### Step 9: Documentation and Examples

**Tasks**:

- Document usage tracking architecture
- Document configuration options
- Document privacy considerations
- Create usage analytics examples
- Update main README with usage tracking info
- Create guide for interpreting usage reports

**Deliverables**:

- Architecture documentation
- Configuration guide
- Privacy policy
- Usage examples
- Analytics guide

**Estimated Time**: 4-6 hours

## Technical Design

### Data Model

```python
class ToolUsageEvent(TypedDict):
    """Single tool usage event."""
    tool_name: str
    timestamp: str  # ISO 8601
    duration_ms: float
    success: bool
    error_type: str | None
    params_hash: str | None  # Hash of anonymized parameters

class ToolUsageStats(TypedDict):
    """Aggregated usage statistics."""
    tool_name: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    error_types: dict[str, int]  # error_type -> count
    first_used: str  # ISO 8601
    last_used: str  # ISO 8601
```

### Storage Structure

```
.cortex/
└── .cache/
    └── usage/
        ├── events/
        │   ├── 2026-01-16.json
        │   ├── 2026-01-17.json
        │   └── ...
        ├── aggregated/
        │   ├── daily/
        │   │   ├── 2026-01.json
        │   │   └── ...
        │   ├── weekly/
        │   │   ├── 2026-W03.json
        │   │   └── ...
        │   └── monthly/
        │       ├── 2026-01.json
        │       └── ...
        └── index.json  # Metadata about stored data
```

### Integration Points

1. **Tool Registration**: Wrap `@mcp.tool()` decorators
2. **Manager Initialization**: Add `UsageTracker` to manager container
3. **Configuration**: Use `.cortex/config/usage_tracking.json`
4. **Storage**: Use `.cortex/.cache/usage/` directory
5. **Analytics**: New MCP tools in `usage_analytics.py`

## Dependencies

### Internal Dependencies

- **Manager System**: `UsageTracker` must integrate with `ManagerContainer`
- **Path Resolution**: Use `get_cortex_path()` for cache directory
- **Configuration System**: Use existing config management patterns
- **File System**: Use `FileSystemManager` for file operations (optional, or direct aiofiles)

### External Dependencies

- **FastMCP**: Must work with existing `@mcp.tool()` decorator system
- **Python 3.13+**: Use modern type hints and features
- **aiofiles**: For async file I/O (already in dependencies)

### No Dependencies On

- External analytics services
- Database systems (JSON files only)
- Network services (local storage only)

## Success Criteria

### Functional Requirements

- ✅ All 54+ tools automatically tracked without code changes
- ✅ Usage events recorded with < 1ms overhead per tool call
- ✅ Usage statistics queryable via MCP tools
- ✅ Unused tools identifiable via analytics
- ✅ Optimization recommendations generated
- ✅ Configuration allows opt-out and privacy controls
- ✅ Data retention and cleanup working correctly

### Non-Functional Requirements

- ✅ **Performance**: < 1ms overhead per tool call (target: < 0.5ms)
- ✅ **Privacy**: Parameters anonymized, no PII stored
- ✅ **Reliability**: Tracking failures don't break tool execution
- ✅ **Storage**: Efficient storage, automatic cleanup
- ✅ **Test Coverage**: 90%+ coverage for all new code

### Acceptance Criteria

1. **Tracking Works**: All tools generate usage events when called
2. **Analytics Work**: Usage statistics queryable and accurate
3. **Recommendations Work**: Optimization recommendations identify real candidates
4. **Privacy Respected**: No sensitive data in usage logs
5. **Performance Acceptable**: No noticeable slowdown in tool execution
6. **Configuration Works**: Users can opt-out or configure tracking

## Risks & Mitigation

### Risk 1: Performance Impact

**Risk**: Usage tracking adds significant overhead to tool execution  
**Mitigation**:

- Use async I/O with batching
- Write to memory buffer, flush periodically
- Measure and optimize hot paths
- Make tracking optional via configuration

### Risk 2: Privacy Concerns

**Risk**: Usage tracking captures sensitive data in parameters  
**Mitigation**:

- Anonymize all parameters by default
- Hash sensitive values instead of storing
- Allow opt-out per tool
- Document privacy policy clearly

### Risk 3: Integration Complexity

**Risk**: Wrapping 54+ tools is complex and error-prone  
**Mitigation**:

- Use decorator pattern for automatic wrapping
- Comprehensive integration tests
- Gradual rollout (test with subset first)
- Fallback: Manual tracking for problematic tools

### Risk 4: Storage Growth

**Risk**: Usage data grows unbounded  
**Mitigation**:

- Implement retention policy (90 days default)
- Aggregation reduces storage needs
- Automatic cleanup of old data
- Configurable retention period

### Risk 5: FastMCP Compatibility

**Risk**: Tracking wrapper breaks FastMCP tool registration  
**Mitigation**:

- Test with FastMCP framework thoroughly
- Use compatible decorator patterns
- Fallback: Manual registration if needed
- Consult FastMCP documentation

## Timeline

### Phase 1: Foundation (Steps 1-2)

- **Duration**: 12-16 hours
- **Deliverables**: Architecture, `UsageTracker` manager

### Phase 2: Integration (Steps 3-4)

- **Duration**: 16-20 hours
- **Deliverables**: Tool wrapper, integration with all tools

### Phase 3: Analytics (Steps 5-6)

- **Duration**: 12-16 hours
- **Deliverables**: Analytics MCP tools, configuration

### Phase 4: Polish (Steps 7-9)

- **Duration**: 18-24 hours
- **Deliverables**: Aggregation, testing, documentation

### Total Estimated Time: 40-60 hours

## Open Questions

1. **Decorator Order**: How to ensure tracking decorator wraps `@mcp.tool()` correctly?
2. **Parameter Anonymization**: What level of anonymization is appropriate? Hash all params or selective?
3. **Storage Format**: JSON files vs. SQLite? JSON is simpler, SQLite is more efficient for queries.
4. **Aggregation Frequency**: Real-time vs. batch? Background task vs. on-demand?
5. **Opt-Out Mechanism**: Per-tool opt-out or global only?
6. **Error Tracking**: Should we track error details or just error types?

## Notes

- This feature enables data-driven optimization of the MCP tool ecosystem
- Usage data will inform future tool development priorities
- Privacy and performance are critical design considerations
- Consider adding usage tracking to prompts as well (7 prompts currently)
- Future enhancement: Export usage data for cross-project analysis

## Related Plans

- [Phase 27: Script Generation Prevention](../phase-27-script-generation-prevention.md) - May benefit from usage data
- [Phase 21: Health-Check and Optimization Analysis](../phase-21-health-check-optimization.md) - Could integrate usage analytics
- [Phase 20: Code Review Fixes](../phase-20-code-review-fixes.md) - Current active work, should complete first
