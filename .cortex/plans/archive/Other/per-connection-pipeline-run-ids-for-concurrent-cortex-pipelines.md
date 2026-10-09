---
status: DONE
---

# Problem

All concurrent MCP server processes in one project resolve ONE durable pipeline session id from `.cortex/.session/.active-session.json` (by design, for restart resume). Sibling sessions running `/cortex` pipelines therefore interleave phase events in a single run window: `resume` can attach a live sibling's run, and phase/task files collide under `.cortex/.session/{pipeline_id}/`.

# Context

- Fixed in 95c6796c (2026-10-08): agent identity (`CORTEX_SESSION_ID`) is now per-process and the registry is sibling-safe. The pipeline domain intentionally kept the shared marker.
- `pipeline_handoff_session.get_session_id` (env > marker > mint) is the single resolution point; `pipeline_handoff_io` stores state under `.cortex/.session/{id}/{pipeline}/`.
- TradeWing runs 3+ sibling sessions per project routinely.

# Approach

1. Decide identity ownership: per-connection pipeline id with explicit resume of an incomplete run (marker becomes a resume hint, not live identity), or lock-scoped single-writer pipeline with sibling exclusion via the task-lock registry.
2. Extend `build_resume_plan` to enumerate incomplete runs and disambiguate by age/pipeline rather than adopting any matching run.
3. Guard `pipeline_handoff(init)` against adopting a run another live session owns (cross-check the session registry / lock registry).

# Acceptance

- Two processes running `init` for the same pipeline concurrently produce distinct run state and never share a run window.
- Restart of one process resumes ITS incomplete run, not a sibling's.
- Regression tests: concurrent init across processes; resume after simulated restart picks the owned run.

# Non-goals

- Changing the agent-domain session registry (done in 95c6796c).

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
