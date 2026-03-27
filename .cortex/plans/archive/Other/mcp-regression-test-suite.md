# Plan: MCP Server Regression Test Suite — Concurrent Subagent and Serialization Tests

**Slug**: mcp-regression-test-suite
**Component**: mcp-server
**Work type**: improvement
**Priority**: high
**Status**: PENDING
**Created**: 2026-03-26

---

## Goal

Create regression tests for the top 3 recurrent MCP failure patterns (concurrent subagent saturation, serialization mismatches, CWD resolution) to eliminate the 6+ multi-session debugging cycles.

## Context

MCP server issues were the single largest time sink: ~8 sessions on MCP stability. Specific recurrent failures:

1. Concurrent subagents saturating connections
2. `pipeline_handoff` serialization expecting string but getting JSON
3. CWD resolution returning wrong project when running via uvx

These need regression tests, not just documentation.

## Implementation Steps

1. Read existing MCP tests in `tests/` directory to understand current coverage
2. Create `tests/test_mcp_regression.py` with tests for:
   - **Concurrent tool saturation**: simulate 5+ simultaneous tool calls, verify no disconnections
   - **Serialization roundtrip**: test pipeline_handoff write/read with string and JSON object payloads
   - **CWD resolution**: test project root resolution when running via uvx vs local dev
   - **Graceful degradation**: test server handles missing `list_roots` without crashing
   - **Sequential prompt execution**: verify fix prompts execute sequentially, not in parallel
3. Use pytest-asyncio for async tests
4. Add descriptive docstrings per test documenting which past failure it prevents
5. Run `run_quality_gate()` after creation
6. Register in CI by verifying tests are discovered by existing pytest config

## Verification

- `tests/test_mcp_regression.py` exists with 5+ test functions
- All tests have docstrings naming the failure scenario
- Tests pass

## Testing

- `run_quality_gate()` passes
- `python -m pytest tests/test_mcp_regression.py -v` shows all tests collected and passing
