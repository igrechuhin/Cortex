---
id: add-anthropic-prompt-cache-control
title: "Add Anthropic Prompt Cache-Control to MCP Resource Responses"
status: PENDING
priority: MEDIUM
created: 2026-04-03
area: Features & Enhancements
tags: [caching, prompt-caching, anthropic, tokens, mcp-resources, cost, latency]
---

## Goal

Reduce Anthropic API input-token costs and latency for Claude Code / Cursor sessions by injecting
`cache_control` markers into the high-reuse MCP resource responses (`cortex://rules`,
`cortex://context`). These two resources contain static-or-slowly-changing content that is read at
the start of every non-trivial session and currently re-billed at full input-token price every time.

With Anthropic prompt caching, cache-read tokens cost 0.1× base price (90% discount). Break-even
is 1 cache read for the 5-min TTL tier and 2 reads for the 1-hour tier. Both resources are read
multiple times per session, so break-even is trivially reached.

## Context

### Why this matters

Cortex is an MCP server — it does not call the Anthropic API directly. The IDE client (Claude
Code, Cursor) makes the actual API call. However, the **content returned by MCP resources is
included verbatim in the client's API request**. If that content carries `cache_control` metadata,
the client forwards it to the API, enabling server-side KV caching.

FastMCP supports returning structured `TextContent` objects (not just plain strings) from resource
handlers. A `TextContent` with `annotations` carrying `{"cache_control": {"type": "ephemeral"}}`
is forwarded by Claude Code / Cursor MCP clients as `cache_control` in the `content[]` block of
the messages array sent to the Anthropic API.

**Important caveat**: Claude Code's MCP client passes resource content as `user` message blocks.
The Anthropic API only caches prefixes of the prompt. For caching to apply, the resource content
must appear in a stable prefix position — i.e., it must be read early in the conversation before
tool calls or dynamic content are appended. Because Cortex resources are read at session start
(before implementation work), this condition is met in practice.

### Resources eligible for caching

| Resource | URI | Avg tokens | Changes how often |
|----------|-----|------------|-------------------|
| `cortex://rules` | `get_relevant_rules()` | ~8,000–15,000 | Once per sync (infrequent) |
| `cortex://context` | `load_context()` | up to 100,000 | Once per task / phase |

Both exceed the 1,024-token minimum for Anthropic caching eligibility.

The `cortex://structure` and `cortex://health/connection` resources are small and change
frequently; they are not candidates.

### FastMCP resource return types

FastMCP resource handlers may return:

- `str` — plain text (current behavior)
- `list[TextContent | ImageContent | EmbeddedResource]` — structured content with annotations

To attach `cache_control`, change the return type to `list[TextContent]` and set:

```python
from mcp.types import TextContent
TextContent(type="text", text=payload, annotations={"cache_control": {"type": "ephemeral", "ttl": "1h"}})
```

The `ttl: "1h"` extended TTL is appropriate here because:

- `cortex://rules` content changes only when rules files are edited (rare within a session)
- `cortex://context` content is stable within a task phase

Both tiers can coexist in the same session; the longer-TTL entry must appear first (rules before
context in the typical session call order).

### Cost model (illustrative)

Assume `cortex://rules` = 10,000 tokens, read 3× per session on claude-sonnet-4-6 ($3/1M input):

- Without caching: 3 × 10,000 × $3/1M = $0.090
- With caching (1 write at 2×, 2 reads at 0.1×): (10,000 × $6/1M) + 2 × (10,000 × $0.30/1M)
  = $0.060 + $0.006 = $0.066 — **27% saving per session on just this one resource**

At scale (thousands of sessions), the saving is significant.

## Implementation Steps

### Step 1 — Verify FastMCP passes TextContent annotations through to API

Before any code changes, confirm the claim that FastMCP forwards `TextContent.annotations` as
`cache_control` in the API request. This requires a small spike:

- Read FastMCP source (`src/mcp/server/fastmcp/resources/`) — specifically how resource return
  values are serialised into the MCP `resources/read` response
- Check whether the Claude Code MCP client passes resource content annotations through to the
  Anthropic API `messages.create` call
- Instrument with a single test resource that returns a `TextContent` with a `cache_control`
  annotation; observe whether `cache_creation_input_tokens` > 0 in the API response

If FastMCP does NOT forward annotations, document the gap and pivot to Step 1-alt.

**Step 1-alt (fallback)**: If annotation forwarding is not supported, the alternative is to embed
a sentinel comment at the top of the resource payload:

```text
<!-- cache_control: ephemeral ttl=1h -->
```

This is a no-op for the API but could be used by a thin wrapper layer. Document as
a "not yet actionable — pending IDE/FastMCP support" note and mark the plan as BLOCKED.

### Step 2 — Add `TextContent` return type to `cortex://rules`

Modify `get_relevant_rules()` in `src/cortex/tools/synapse/rules_operations.py`:

- Change return type from `str` to `list[TextContent]`
- Wrap the existing `str` payload in `TextContent(type="text", text=payload, annotations={...})`
- Use `cache_control: {type: "ephemeral", ttl: "1h"}` (1-hour TTL — rules are session-stable)
- Keep `@mcp_resource_wrapper` and `@ensure_usage_context` decorators unchanged
- Verify that `mcp_resource_wrapper` handles `list[TextContent]` return type (may need to unwrap
  the inner value before returning; check wrapper implementation)

Files:

- `src/cortex/tools/synapse/rules_operations.py` — modify `get_relevant_rules()`
- `src/cortex/tools/synapse/rules_operations.py` — add `from mcp.types import TextContent` import

### Step 3 — Add `TextContent` return type to `cortex://context`

Modify `load_context()` in `src/cortex/tools/optimization/handlers.py`:

- Same pattern as Step 2
- Use `cache_control: {type: "ephemeral"}` (5-min TTL — context may change between phases within
  a session, so the shorter TTL is more conservative)
- The 5-min TTL breaks even after 1 cache read, which is always reached within a session

Files:

- `src/cortex/tools/optimization/handlers.py` — modify `load_context()`
- `src/cortex/tools/optimization/handlers.py` — add `from mcp.types import TextContent` import

### Step 4 — Verify `mcp_resource_wrapper` compatibility

`mcp_resource_wrapper` is a decorator applied to resource handlers. Check whether it:

- Expects `str` return from wrapped function and wraps it in `TextContent` itself
- OR passes return value through unchanged

File: `src/cortex/core/mcp_wrappers.py` (or wherever `mcp_resource_wrapper` is defined — locate
with Grep).

If the wrapper forces `str` serialisation, either:
(a) Add a `raw=True` mode that bypasses str-forcing, or
(b) Move the `TextContent` wrapping to after the wrapper call (module-level post-processing)

### Step 5 — Add server-side TTL increase for `MCP_RESOURCE_CACHE_TTL_SECONDS`

The in-process Cortex resource cache TTL is currently 30 seconds
(`MCP_RESOURCE_CACHE_TTL_SECONDS`). Increase to 300 seconds for the rules and context resources
so repeated reads within a session are served from Cortex's own cache, reducing MCP round-trips.

This is independent of Anthropic-side `cache_control` and provides a benefit even if Step 1 shows
that annotation forwarding is not yet supported.

File: `src/cortex/core/constants.py`

- Increase `MCP_RESOURCE_CACHE_TTL_SECONDS` from 30 to 300

Or (more surgical): add a separate constant `MCP_STATIC_RESOURCE_CACHE_TTL_SECONDS = 300` and
apply it specifically to the rules and context resource handlers.

### Step 6 — Unit tests

- Test `get_relevant_rules()` returns `list[TextContent]` with `annotations` containing
  `cache_control` key
- Test `load_context()` returns `list[TextContent]` with `annotations` containing `cache_control`
- Test that `TextContent.text` equals the payload string returned before this change (no data loss)
- Test that `mcp_resource_wrapper` does not strip annotations (regression)

### Step 7 — Run quality gate and verify

Run `run_quality_gate()` to confirm 0 regressions. Manually invoke `cortex://rules` via MCP
inspector or a test client and confirm the response carries `cache_control` annotations.

## Verification Checklist

- [ ] FastMCP forwards `TextContent.annotations` to MCP `resources/read` response (Step 1)
- [ ] Claude Code MCP client passes resource annotations to Anthropic API as `cache_control` (Step 1)
- [ ] `cortex://rules` response is `list[TextContent]` with `cache_control: ephemeral, ttl: 1h` (Step 2)
- [ ] `cortex://context` response is `list[TextContent]` with `cache_control: ephemeral` (Step 3)
- [ ] `mcp_resource_wrapper` does not strip `TextContent` annotations (Step 4)
- [ ] `MCP_RESOURCE_CACHE_TTL_SECONDS` (or equivalent) raised to 300s for static resources (Step 5)
- [ ] Unit tests for both resources pass and assert annotations present (Step 6)
- [ ] `run_quality_gate()` passes after all changes (Step 7)
- [ ] `cache_creation_input_tokens` > 0 observed in first API call; `cache_read_input_tokens` > 0
  in subsequent calls (manual verification — optional but ideal)

## Dependencies

- `src/cortex/tools/synapse/rules_operations.py`
- `src/cortex/tools/optimization/handlers.py`
- `src/cortex/core/constants.py`
- `src/cortex/core/mcp_wrappers.py` (location TBC via Grep)
- FastMCP library (`mcp` package) — specifically resource serialisation path
- Claude Code MCP client behaviour (annotation forwarding — verify in Step 1)

## Blockers / Risks

1. **FastMCP may not forward `TextContent.annotations`**: The MCP spec supports annotations on
   `TextContent`, but FastMCP's resource serialiser may not include them in the wire response.
   Step 1 is a mandatory spike before committing to Steps 2–4.
2. **Claude Code MCP client may not pass annotations to Anthropic API**: Even if FastMCP forwards
   annotations, the IDE client may strip them. Step 1 covers this.
3. **`mcp_resource_wrapper` may coerce return type to `str`**: Step 4 addresses this.

If any of these blockers are confirmed, the plan should be updated to status BLOCKED with a note
describing what upstream change is needed (FastMCP issue / Claude Code feature request).

## Success Criteria

1. `cortex://rules` and `cortex://context` carry `cache_control` annotations in MCP responses
2. `cache_creation_input_tokens` > 0 on first session read (confirmed via API usage field)
3. `cache_read_input_tokens` > 0 on second+ session read of same content
4. No regression: all existing tests pass; `run_quality_gate()` returns `preflight_passed: true`
5. In-process resource cache TTL raised to 300s for static resources

## Partial Progress Log

- 2026-04-03: Step 1 spike — FastMCP `FunctionResource.read()` only returns `str` | `bytes`; `list[TextContent]` is JSON-serialized, not wire-preserved. Cache hints are applied via `@mcp.resource(meta=...)` → `ReadResourceContents.meta` → `_meta` on `resources/read`. Wrapper passes return through unchanged. — files: `src/cortex/core/constants.py`, `src/cortex/tools/synapse/rules_operations.py`, `src/cortex/tools/optimization/handlers.py`, `tests/unit/test_mcp_resource_cache_control.py`
- 2026-04-03: Steps 2–6 partial — `CORTEX_*_RESOURCE_READ_META`, `MCP_STATIC_RESOURCE_CACHE_TTL_SECONDS` + `TTLCache` for rules/context, governance tests. — files: same + `tests/unit/test_mcp_resource_cache_control.py`

## Testing Strategy

- Unit: `get_relevant_rules()` returns `list[TextContent]`; `annotations["cache_control"]["type"] == "ephemeral"`
- Unit: `load_context()` returns `list[TextContent]`; `annotations["cache_control"]["type"] == "ephemeral"`
- Unit: text content of both equals the pre-change string payload (no data mutation)
- Integration: call `cortex://rules` twice in sequence; assert second call is served from Cortex
  in-process cache (TTL check)
- Manual/E2E: start a session, read `cortex://rules`, inspect Anthropic API response for
  `cache_creation_input_tokens` > 0; read again, assert `cache_read_input_tokens` > 0
- Regression: full suite via `run_quality_gate()` after all changes
