# Claude-mem Inspired Improvements (Usage Search, Observations, Progressive Disclosure)

**Status**: COMPLETE (Steps 1–11 completed 2026-02-11)  
**Created**: 2026-02-02  
**Priority**: Future enhancement (after Phase 43)  
**Estimated Effort**: 15–25 hours (phased)  
**Source**: [claude-mem](https://github.com/thedotmack/claude-mem); ideas doc: `.cortex/plans/claude-mem-ideas-for-cortex.md`

## Goal

Improve Cortex MCP with token-efficient usage search, observation-level storage with citations, progressive disclosure in docs and prompts, and  privacy/convention improvements—inspired by claude-mem’s persistent memory and context injection patterns.

## Context

### Why This Plan

claude-mem captures tool usage, compresses it with AI, and injects relevant context into future sessions. Cortex already has memory bank, usage tracking (Phase 29), `load_context`, and `load_progressive_context`. This plan turns the ideas in `.cortex/plans/claude-mem-ideas-for-cortex.md` into an actionable implementation sequence.

### Current State

- **Usage**: `ToolUsageEvent` has tool_name, timestamp, duration_ms, success, error_type, params_hash; events persisted under `.cortex/usage/` or config path; no stable observation ID or result summary.
- **Context**: `load_context` / `load_progressive_context` return full content; no “search index then fetch by ID” pattern.
- **Docs/prompts**: No consistent “context workflow” or token-cost visibility; no privacy convention.

### Dependencies

- **Phase 43 (Reconsider tools registration)**: Resource API (`cortex://` URIs, `mcp_resource_wrapper`) enables observation-by-ID resources (e.g. `cortex://usage/observation/{id}`). Implement observation IDs and usage resources after or in parallel with Phase 43 Step 3+.

## Approach

1. **Short-term (docs/convention)**: Progressive disclosure section in CLAUDE.md/docs; document `<private>` convention; no new tools.
2. **With Phase 43**: Observation IDs for usage events; resource `cortex://usage/observation/{id}`; search_usage (compact index) + get_usage_events(ids=[...]);  get_usage_timeline(around_id, limit).
3. **Later**:  keyword/semantic search over usage; context injection config;  HTTP API or “query usage with jq” docs.

## Implementation Steps

Implementation order: execute steps in sequence. Dependencies between steps are called out below.

### Step 1: Progressive Disclosure in Documentation (Low Effort)

**Deliverable**: Short “context workflow” and token-awareness in CLAUDE.md and/or docs.

- Add a subsection (e.g. “Context loading workflow”) that recommends: prefer search/index first when querying usage or history, then fetch by ID; use `load_progressive_context` when appropriate; respect token budgets.
- In prompts that reference usage or history (e.g. commit, implement-next-roadmap-step), add a note: prefer “search → select IDs → get_usage_event(ids=[...])” once that API exists; avoid “dump all” patterns.
- ly add token estimates in tool responses (e.g. “~N tokens” for current payload) where feasible and non-intrusive.

**Success**: CLAUDE.md and at least one doc or prompt updated; wording reviewable in PR.

**Dependencies**: None.

**Status**: COMPLETED 2026-02-10 — CLAUDE.md context workflow and implement-next-roadmap-step prompt confirm progressive disclosure guidance.

---

### Step 2: Document Privacy / Exclusion Convention (Low Effort)

**Deliverable**: Convention for excluding sensitive content from storage and repetition.

- Document a convention (e.g. `<private>...</private>` or `<!-- private -->`) in memory bank docs or Synapse prompts so agents know not to persist or repeat sensitive blocks.
- In tools that persist user content (e.g. session scripts, summaries), add  stripping/redaction of content between these tags before writing. Keep scope minimal (convention first; stripping behind config if implemented).

**Success**: Convention documented; stripping implemented only if scoped and tested.

**Dependencies**: None.

**Status**: COMPLETED 2026-02-10 — Privacy convention documented in CLAUDE.md (and AGENTS.md) for `<private>` / `<!-- private -->` blocks.

---

### Step 3: Assign Stable IDs to Usage Events (Medium Effort)

**Deliverable**: Every persisted usage event has a stable, readable ID (e.g. UUID or date-based id); existing events get IDs on next read or via one-time backfill.

- Extend `ToolUsageEvent` (or persistence schema) with an `id` field; assign ID at persist time.
- Ensure IDs are unique and stable (same event same ID on re-read).
- Backfill: either assign IDs when loading existing JSON files or run a one-time migration script; document in plan or release notes.

**Success**: All new events have IDs; existing data backfilled or documented as best-effort.

**Dependencies**: None (Phase 43 not required for ID assignment).

**Status**: COMPLETED 2026-02-10 — Implemented `id` on `ToolUsageEvent`, persisted IDs for new events, and added deterministic UUIDv5-based backfill in `usage_tracker` with tests.

---

### Step 4: Resource cortex://usage/observation/{id} (Medium Effort)

**Deliverable**: Read observation by ID via MCP resource, aligned with Phase 43 resource API.

- Register resource template `cortex://usage/observation/{id}` (or equivalent) using `mcp.resource()` and `mcp_resource_wrapper`.
- Handler: resolve `id` to stored event (and result summary if added); return JSON or text; 404 if not found.
- Follow Phase 43 decorator stack and URI scheme; document in resource API design.

**Success**: Client can read observation by ID via resource; 404 for unknown ID; tests for success and 404.

**Dependencies**: Phase 43 Step 3 (resource registration) and Step 3 (observation IDs).

**Status**: COMPLETED 2026-02-10 — Implemented `get_usage_observation` MCP tool and `cortex://usage/observation/{id}` resource backed by `UsageTracker.get_event_by_id`, with tests for success and not-found cases.

---

### Step 5: search_usage Tool — Compact Index (Medium Effort)

**Deliverable**: MCP tool `search_usage` (or `search_context_history`) that returns a compact list of usage/context entries with IDs and short summaries (e.g. tool_name, timestamp, one-line summary), without full payloads.

- Define response shape: list of `{ id, tool_name, timestamp, summary? }` (and other compact fields as needed).
- Implement search over persisted usage (and context logs): filter by date range, tool_name, success/failure; sort by time; limit results.
- Return only compact fields to keep token cost low (~50–100 tokens per result).

**Success**: Tool returns compact index; filters and limit work; tests for response shape and filtering.

**Dependencies**: Step 3 (IDs). Phase 43 (tool-only).

**Status**: COMPLETED 2026-02-10 — Implemented `search_usage` MCP tool with compact index results and tests.

---

### Step 6: get_usage_events(ids=[...]) Tool or Resource (Medium Effort)

**Deliverable**: Fetch full details only for selected observation IDs.

- Option A: MCP tool `get_usage_events(ids=[...])` returning full event(s) for given IDs.
- Option B: Multiple resource reads `cortex://usage/observation/{id}` (from Step 4); document “batch by multiple reads” in prompts.
- Prefer one primary path (tool or resource) and document it in progressive disclosure docs.

**Success**: Client can fetch full details for a set of IDs without loading all history; tests for multiple IDs and missing IDs.

**Dependencies**: Step 3, Step 4 (if resource path).

**Status**: COMPLETED 2026-02-11 — Implemented get_usage_events MCP tool backed by UsageTracker.get_events_by_ids, with tests and quality gate passing.

---

### Step 7: get_usage_timeline (Lower Priority)

**Deliverable**: Tool or resource that returns chronological context around a given observation (e.g. “N events before and after this id”).

- Implement `get_usage_timeline(around_id=..., limit=...)` (or equivalent) returning compact entries in time order.
- Enables “what happened around this observation?” without full scan.

**Success**: Timeline around an ID returns correct order and limit; tests added.

**Dependencies**: Step 3, Step 5.

**Status**: COMPLETED 2026-02-11 — Implemented `UsageTracker.get_usage_timeline` and `get_usage_timeline` MCP tool with tests and quality gate passing.

---

### Step 8: Result Summary per Observation (Medium Effort)

**Deliverable**: ly store a short result summary (e.g. for load_context, refactoring) with each observation for retrieval and future semantic search.

- Design: `result_summary` or similar field; populated for selected tools (e.g. load_context, apply_refactoring) if config enabled.
- Keep storage and computation minimal; consider feature flag or config.

**Success**: When enabled, selected tools persist a short summary; retrieval includes it via usage analytics tools; tests cover on/off and presence/absence for persistence and retrieval paths.

**Dependencies**: Step 3; precursor to semantic search (Step 9).

**Status**: COMPLETED 2026-02-11 — Added optional `result_summary` field to `ToolUsageEvent`, gated configuration for enabled tools, persisted summaries in `UsageTracker.record_tool_usage`, and extended usage analytics tools and tests so summaries round-trip correctly when present.

---

### Step 9: Keyword / Semantic Search Over Usage

**Deliverable**: Search usage/context by keyword (task_description, tool_name, error_type); ly add semantic search (embeddings + vector DB) behind feature flag.

- Keyword: implement search over existing persisted fields (e.g. task_description, tool_name, error_type) via simple filter or FTS if available.
- Semantic: only if needed; use  dependency (e.g. Chroma) and feature flag; document in techContext.

**Success**: Keyword search returns relevant observations; semantic layer, if added, is  and documented.

**Dependencies**: Step 3, Step 5; Step 8 helpful for semantic.

---

### Step 10: Context Injection Configuration

**Deliverable**: “context injection” policy in config (e.g. always include memory bank core files, last N task types, max tokens for usage summary).

- Extend optimization or config schema with policy; document in config docs.
- If clients auto-read resources at session start, align with this policy (e.g. `cortex://memory-bank/stats`, `cortex://usage/recent`).

**Success**: Config schema and docs updated; behavior used by load_context or resources if implemented.

**Dependencies**: Phase 43 resources.

---

### Step 11: Document Querying Usage JSON

**Deliverable**: Short doc or README section on how to query usage event files (e.g. `.cortex/usage/events/` or config path) with jq or scripts.

- Enables power users to build custom dashboards or scripts without adding an HTTP API.

**Success**: Doc exists and points to correct paths and example jq/scripts.

**Dependencies**: None.

---

## Plan Dependencies

- **Phase 43**: Required for Step 4 (resource `cortex://usage/observation/{id}`); recommended before or in parallel with Steps 4–6.
- **Internal**: Step 3 before Steps 4, 5, 6, 7; Step 5 before Step 6; Step 8 before Step 9.

## Success Criteria

- Progressive disclosure and privacy convention documented (Steps 1–2).
- Usage events have stable IDs; observation readable by ID via resource (Steps 3–4).
- Token-efficient workflow available: search_usage (index) → get_usage_events(ids) or resource read (Steps 5–6).
- Timeline (Step 7), result summary (Step 8), keyword/semantic search (Step 9), context injection config (Step 10), usage-query docs (Step 11).

## Technical Design

- **IDs**: UUID or `{date}-{index}` per file; uniqueness within and across files as needed.
- **Storage**: Keep existing usage event JSON layout; add `id` (and `result_summary`) to schema; backfill strategy documented.
- **Resources**: Follow Phase 43 design (`cortex://`, `mcp_resource_wrapper`, `ensure_usage_context`); template resource `cortex://usage/observation/{id}`.
- **Tools**: `search_usage` (and `get_usage_timeline`) return compact structures; `get_usage_events(ids=[...])` returns full events; all with timeout wrappers and usage tracking.

## Testing Strategy (MANDATORY)

- **Coverage target**: Minimum 95% for all new/updated code paths (ID assignment, search, fetch, resource handler, summary/timeline).
- **Unit tests**:
  - ID assignment: assign ID at persist; id stable on re-read; backfill logic if present.
  - search_usage: response shape, filters (date, tool_name, success), limit, empty result.
  - get_usage_events: multiple IDs, single ID, missing ID (skip or error per spec).
  - Resource handler: resolve id to event; 404 for unknown id; JSON shape.
  - get_usage_timeline: order, limit, around_id.
  - Privacy stripping: if implemented, strip/redact between tags; no strip when disabled.
- **Integration tests**: End-to-end: record event → search_usage → get_usage_events(ids) or read resource; verify content and IDs.
- **Edge cases**: Empty store, malformed id, very large ids list (limit or reject).
- **AAA**: All tests follow Arrange-Act-Assert.
- **Pydantic v2**: Use BaseModel and model_validate_json for MCP tool/resource response assertions where applicable.

## Risks & Mitigation

- **Storage growth**: Result summaries and IDs add little; document retention or pruning if needed.
- **Backfill cost**: One-time backfill for existing events; run offline or on first read; document in release notes.
- **Phase 43 timing**: Steps 4–6 can be implemented as tools-only first; add resources when Phase 43 is ready.

## Timeline

- **Steps 1–2**: 1–2 hours (docs/convention).
- **Steps 3–6**: 8–12 hours (IDs, resource, search, fetch).
- **Steps 7–11**: 6–11 hours (timeline, summary, search, config, docs).

Total estimate: 15–25 hours phased.

## Notes

- Ideas and priority table remain in `.cortex/plans/claude-mem-ideas-for-cortex.md`; this plan is the implementation counterpart.
- Lifecycle hooks (session start/end) are not implemented; document “at session start, consider reading cortex://memory-bank/stats and recent usage” in prompts instead.
- Web UI / HTTP API deferred unless there is clear demand; Step 11 (docs for jq/scripts) suffices for power users.
