# Ideas from claude-mem to Improve Cortex MCP

**Source**: [claude-mem](https://github.com/thedotmack/claude-mem) — Claude Code plugin for persistent memory, compression, and context injection.  
**Created**: 2026-02-02  
**Status**: Ideas / future enhancements (not a committed roadmap item).

## Summary

claude-mem automatically captures tool usage, compresses it with AI, and injects relevant context into future sessions. Cortex already has memory bank, usage tracking, load_context, and progressive context. This document maps claude-mem concepts to Cortex and suggests concrete improvements.

---

## 1. Three-Layer Search Workflow (High Value)

**claude-mem**: Token-efficient 3-layer pattern:

1. **search** — Compact index with IDs (~50–100 tokens/result)
2. **timeline** — Chronological context around interesting results
3. **get_observations** — Fetch full details only for filtered IDs (~500–1,000 tokens/result)

**Cortex today**: `load_context` and `load_progressive_context` return full content in one shot. No “light index then fetch by ID” pattern.

**Idea for Cortex**:

- Add a **search/index** layer over usage events, context logs, or memory bank:
  - Tool: e.g. `search_usage` or `search_context_history` returning compact entries with stable IDs (and optional short summaries).
- Add **fetch by ID**:
  - Resource or tool: e.g. `cortex://usage/event/{id}` or `get_usage_event(ids=[...])` to load full details only for selected IDs.
- Optionally add **timeline**:
  - Tool: e.g. `get_usage_timeline(around_id=..., limit=...)` for chronological context around a given event.

**Benefit**: Same “filter first, fetch later” discipline as claude-mem; large token savings when scanning many events or history.

---

## 2. Observation-Level Storage and Citations

**claude-mem**: Stores “observations” (tool use + result summaries), each with an ID. Citations reference past observations by ID; API supports `GET /api/observation/{id}`.

**Cortex today**: `ToolUsageEvent` has tool_name, timestamp, duration_ms, success, error_type, params_hash. No observation ID, no result summary, no citation surface.

**Idea for Cortex**:

- Assign **stable IDs** to usage events (or to a new “observation” entity that includes optional result summary).
- Expose **by-ID read** via resource: e.g. `cortex://usage/observation/{id}` (aligns with Phase 43 resource API).
- Optionally store **compressed/summarized result** per observation (e.g. for load_context outcomes, refactoring results) for later retrieval.
- Document **citation format** in prompts: “reference observation #123” with link to resource or tool that resolves #123.

**Benefit**: Agents and users can refer to specific past tool outcomes; supports audits and continuity across sessions.

---

## 3. Progressive Disclosure in Documentation and Prompts

**claude-mem**: “Progressive disclosure” — layered retrieval with token cost visibility; docs describe context engineering and priming strategy.

**Cortex today**: `load_context` / `load_progressive_context` and token budgets exist; docs and prompts don’t consistently teach “index → timeline → full fetch” or token-cost visibility.

**Idea for Cortex**:

- Add a **short “context workflow”** section to CLAUDE.md or docs:
  - Prefer search/index first, then fetch by ID; use progressive load when appropriate; mention token budgets.
- In prompts that use usage or history:
  - Recommend “search → select IDs → get_usage_event(ids=[...])” (or equivalent) instead of “dump all”.
- Optionally add **token estimates** in tool responses (e.g. “~N tokens” for current payload) where feasible.

**Benefit**: Aligns agent behavior with token-efficient patterns; matches claude-mem’s philosophy.

---

## 4. Semantic / Hybrid Search Over History

**claude-mem**: Chroma vector DB + SQLite FTS5 for hybrid semantic + keyword search over observations.

**Cortex today**: `search_tools_and_scripts` is keyword-style over tool/script names. Relevance scoring for files (e.g. load_context) is in-repo; no vector DB or semantic search over usage/observations.

**Idea for Cortex** (longer-term):

- **Keyword search** over usage/context logs (e.g. by task_description, tool_name, error_type) using existing storage + simple FTS or grep.
- **Optional semantic layer**: If adding observation summaries, consider embeddings + vector search (e.g. Chroma or in-process) for “find past sessions/observations similar to this task.”
- Keep **optional**: Cortex stays dependency-light; semantic search can be behind a feature flag or extra dependency.

**Benefit**: “Find past work like this” without scanning full history; improves continuity.

---

## 5. Privacy / Exclusion Tags

**claude-mem**: `<private>` tags exclude sensitive content from storage.

**Cortex today**: No generic “exclude from storage” mechanism for tool inputs/outputs or memory bank content.

**Idea for Cortex**:

- Document a **convention** (e.g. `<private>...</private>` or `<!-- private -->`) in memory bank or prompts so agents know not to persist or repeat sensitive blocks.
- Optionally: In tools that persist user content (e.g. session scripts, summaries), **strip or redact** content between such tags before writing.
- Keep implementation minimal (convention + optional stripping) to avoid scope creep.

**Benefit**: Reduces risk of leaking secrets or PII into usage/history.

---

## 6. Context Injection Configuration

**claude-mem**: Fine-grained control over what context gets injected (e.g. by type, recency, project).

**Cortex today**: `load_context` has strategy and token_budget; config has optimization/validation settings. No explicit “injection policy” (what to auto-load at session start or after certain events).

**Idea for Cortex**:

- Extend **optimization or config** with optional “context injection” policy:
  - E.g. “always include memory bank core files,” “include last N load_context task types,” “max tokens for auto-injected usage summary.”
- If Cortex ever supports **session-start hooks** or **resources** that clients auto-read:
  - Align injected content with this policy (e.g. `cortex://memory-bank/stats` + optional `cortex://usage/recent`).

**Benefit**: Predictable, configurable context for new sessions without hardcoding in every client.

---

## 7. Web Viewer / HTTP API (Optional)

**claude-mem**: Worker service with HTTP API and web viewer (e.g. port 37777) for observations, search, timeline.

**Cortex today**: MCP server only; optional CLI (e.g. health_check). No HTTP API or UI.

**Idea for Cortex**:

- **Low priority**: Add optional **read-only HTTP API** (e.g. `/usage`, `/usage/event/{id}`, `/structure/info`) for dashboards or scripts.
- Even lighter: **document** how to query usage JSON (e.g. `.cortex/usage/events/`) with jq or scripts so power users can build their own “viewer.”
- Only consider a real web UI if there’s clear demand; otherwise keep Cortex as MCP + CLI.

**Benefit**: Optional observability and debugging without forcing a new server on all users.

---

## 8. Lifecycle Hooks (Reference Only)

**claude-mem**: SessionStart, UserPromptSubmit, PostToolUse, Stop, SessionEnd hooks drive capture and injection.

**Cortex today**: MCP has no standard “session start/end” hooks; tool use is wrapped (e.g. mcp_tool_wrapper) for timeout and usage recording.

**Idea for Cortex**:

- **No direct port**: Hooks are plugin/IDE-specific. Cortex can still:
  - **Record** after each tool use (already done).
  - Expose **resources** that clients or prompts can read at “session start” (e.g. `cortex://memory-bank/stats`, `cortex://usage/recent`).
- Document in **prompts** that “at session start, consider reading cortex://memory-bank/stats and recent usage” so clients that support resource preloading get similar benefit.

**Benefit**: Session continuity via convention and resources rather than Cortex implementing a hook runtime.

---

## Priority Overview

| Idea                          | Effort | Value   | Fit with Phase 43 / roadmap     |
|-------------------------------|--------|---------|----------------------------------|
| 3-layer search workflow       | Medium | High    | Aligns with resources + usage    |
| Observation IDs + citations  | Medium | High    | Fits resource API (cortex://usage/…) |
| Progressive disclosure docs  | Low    | Medium  | Doc/prompt only                  |
| Semantic/hybrid search        | High   | Medium  | Optional / later                 |
| Privacy tags                  | Low    | Medium  | Convention + optional strip      |
| Context injection config      | Low–Med| Medium  | Config + prompts                |
| Web viewer / HTTP API         | High   | Low–Med | Optional                         |
| Lifecycle hooks               | N/A    | —       | Reference; use resources/prompts |

---

## Next Steps (If Pursued)

1. **Short term**: (3) Progressive disclosure in docs and prompts; (5) document `<private>` convention.
2. **With Phase 43**: (2) Observation IDs + `cortex://usage/observation/{id}`; (1) search/index + fetch-by-ID for usage.
3. **Later**: (4) optional semantic search; (6) context injection config; (7) optional HTTP API if needed.

---

## References

- [claude-mem GitHub](https://github.com/thedotmack/claude-mem)
- Cortex: Phase 43 resource API design (`.cortex/plans/phase-43-resource-api-design.md`), usage tracking (Phase 29), `load_context` / `load_progressive_context`, `get_tool_usage_report` / `get_tool_usage_stats`.
