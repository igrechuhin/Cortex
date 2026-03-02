# Plan: Implement query_usage Resources for 11 Uncovered Query Types

**Status**: PENDING
**Priority**: Medium
**Type**: Feature / MCP protocol alignment
**Effort**: 4–8 hours
**Created**: 2026-03-02

## Goal

Implement MCP resources for the 11 `query_usage` query types that currently have no `cortex://` resource. Per [tools-to-resources-conversion-analysis](../../docs/architecture/tools-to-resources-conversion-analysis.md), these are read-only operations exposed only via the `query_usage` tool; adding resources enables clients that support resource fetching to load usage data without tool calls.

## Context

- **Source**: Tools-to-Resources Conversion Analysis (plan-tools-to-resources-analysis.md) identified 11 query types without resources.
- **Pattern**: Existing resources (stats, unused, report, optimization-recommendations, observation) in `usage_analytics.py` follow: `@mcp.resource(uri="cortex://usage/...")`, `@ensure_usage_context`, `@mcp_resource_wrapper`, thin wrapper calling handler with default params.
- **Client constraints**: Prefer path segments over query strings; use defaults for optional params.

## Uncovered Query Types and Proposed URIs

| query_type | Proposed URI | Required Params | Default Params | Notes |
|------------|--------------|-----------------|----------------|-------|
| anomalies | cortex://usage/anomalies/{hours} | hours (in path) | hours=24 | High priority |
| tool_description_optimization | cortex://usage/tool-optimization/{tool_name} | tool_name | days=90 | High priority |
| events | cortex://usage/events | none | limit=50, recent | Medium |
| search | cortex://usage/search/{query} | query (URL-encoded) | limit=50 | Medium; query in path |
| timeline | cortex://usage/timeline/{around_id} | around_id | — | Medium |
| production_monitoring | cortex://usage/production-monitoring | none | — | Low |
| token_efficiency | cortex://usage/token-efficiency | none | — | Low |
| redundancy | cortex://usage/redundancy | none | — | Low |
| session_continuity | cortex://usage/session-continuity | none | — | Low |
| tool_frequency | cortex://usage/tool-frequency | none | — | Low |
| tool_classification | cortex://usage/tool-classification | none | — | Low |

## Implementation Steps

### Step 1: Implement High-Priority Resources (anomalies, tool_description_optimization)

1. Add `cortex://usage/anomalies/{hours}` resource in `usage_analytics.py` (or appropriate module).
2. Add `cortex://usage/tool-optimization/{tool_name}` resource.
3. Follow pattern: `@mcp.resource`, `@ensure_usage_context`, `@mcp_resource_wrapper`, call handler with defaults.
4. Write unit tests for each resource (JSON shape, status success).

### Step 2: Implement Medium-Priority Resources (events, search, timeline)

1. Add `cortex://usage/events` — no required params; use limit=50.
2. Add `cortex://usage/search/{query}` — query URL-encoded in path; limit=50 default.
3. Add `cortex://usage/timeline/{around_id}` — around_id required (or use a sentinel for "recent" if supported).
4. Write unit tests.

### Step 3: Implement Low-Priority Resources (remaining 6)

1. Add resources for: production_monitoring, token_efficiency, redundancy, session_continuity, tool_frequency, tool_classification.
2. Each uses no required path params; all optional params use sensible defaults from config or handler.
3. Write unit tests.

### Step 4: Update Documentation

1. Update `docs/architecture/tools-to-resources-conversion-analysis.md` — mark new resources as implemented.
2. Update `docs/api/tools.md` — add new URIs to the resource reference table (if present).
3. Ensure naming-conventions.md reflects any new URI patterns.

### Step 5: Integration and Verification

1. Verify resource and tool return equivalent data for same logical request (integration tests).
2. Run full test suite and quality gate.
3. Confirm no regressions in existing query_usage tool behavior.

## Dependencies

- USAGE_HANDLERS in `query_handlers.py` — handlers for each query type must exist.
- `ensure_usage_context`, `mcp_resource_wrapper`, `resolve_project_root_async`, `get_tool_optimization_config` (for config-driven defaults).

## Success Criteria

- [ ] All 11 resources implemented and registered.
- [ ] Each resource returns valid JSON for documented URIs.
- [ ] Unit tests for each new resource (≥95% coverage for new code).
- [ ] Integration test: resource and tool return equivalent data for same request.
- [ ] Documentation updated.
- [ ] All tests pass; quality gate passes.

## Testing Strategy

- **Unit tests**: Each resource handler returns JSON with expected keys (status, etc.); test with mock ctx.
- **Integration tests**: Compare `query_usage(query_type="anomalies", hours=24)` with `cortex://usage/anomalies/24` payload (structure and key fields).
- **Coverage**: Target ≥95% for new resource handlers.
- **AAA pattern**: Arrange-Act-Assert for all tests.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| URI length limits for search | Use path segment; URL-encode query; document max length |
| Handler params differ from defaults | Document default behavior in resource docstring |
| Timeline requires around_id | If no "recent" mode, document that around_id is required |

## References

- [tools-to-resources-conversion-analysis](../../docs/architecture/tools-to-resources-conversion-analysis.md)
- [docs/api/tools.md](../../docs/api/tools.md)
- [naming-conventions.md](../../docs/architecture/naming-conventions.md)
- `src/cortex/tools/usage/usage_analytics.py` — existing resource pattern
- `src/cortex/tools/usage/query_handlers.py` — USAGE_HANDLERS
