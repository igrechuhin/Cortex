# Post-Prompt Analysis

Session: fb7d5600d0e0 — `/cortex/do` closing the 3 Review Follow-Up Gaps on
`analyze-experience-graph-queries` (now COMPLETE, archived).

## Context Effectiveness

311 calls analyzed this session (avg token utilization 32.9%, avg relevance
0.418). No anomalies specific to this session; matches the project-wide
historical pattern already tracked (average ~37% budget utilization).

## Session Optimization

Single-goal session (closing the 3 named review gaps); no scope drift.

Mistake pattern observed and self-corrected inline: initial plan risked
adding a new top-level `@mcp.tool()` for the analytics queries, which would
have breached `MAX_REGISTERED_TOOLS = 13` (a hard governance cap enforced by
`tests/tools/test_tool_categories_governance.py`, already at exactly 13/13
registered tools). Caught during pre-implementation exploration by reading
`src/cortex/tools/structure/categories.py` before delegating; the
implementation instead added 4 new operations to the existing
`pipeline_handoff` tool, following the precedent already set by its
`resume` operation (`pipeline_handoff_resume.py`).

Root cause: the plan's gap wording ("register an MCP tool") is generic
enough to invite a new top-level tool by default; the actual constraint
(fixed tool budget, consolidate into existing tools) lives only in a
code comment and a governance test, not in the plan or in
`cortex://rules`.

**Recommendation (process)**: when a plan/gap says "register an MCP tool,"
check `src/cortex/tools/structure/categories.py`'s `MAX_REGISTERED_TOOLS`
and current count *before* deciding whether to add a new tool vs. a new
operation on an existing one. No rule file currently states this
explicitly — candidate for a short addition to `mcp-development`-flavoured
rules content, but skipped this session since it's a narrow, low-frequency
pattern (one prior occurrence) and doesn't yet meet the bar for a
standalone Synapse rule/skill.

Second observation: `pipeline_handoff`'s cumulative phase state
(`pipeline.json`) was reset mid-session after a ~21-minute `implement-code`
subagent call — phases `select`/`code` (and later `review`) disappeared from
`pipeline_handoff(operation="read")` even though the session id was stable.
This matches the already-tracked, already-fixed
`pipeline_handoff_phase_state_loss` issue; the fix
(`pipeline_handoff_session.py`) is in the tree but this session's MCP server
process appears to be running pre-fix bytecode. No new investigation filed
per the operator's explicit instruction — recovered from in-transcript data
each time and continued. No action needed beyond an MCP server restart to
pick up the already-merged fix.

## Tools Optimization

No new tool registered this session (by design — see above). Tool budget
unchanged at 13/13 (at cap). No dead tools or duplicates identified in this
session's tool usage.

## Report Location

Saved to: `.cortex/reviews/post-prompt-analysis-2026-07-20T18-31.md`

## Post-Prompt Hook Result

| Artifact Type | Produced | Location or Notes |
|---------------|----------|-------------------|
| Skill         | No       | Pattern too narrow/low-frequency for a standalone skill this session |
| Plan          | No       | No new bugs/features surfaced beyond the completed plan |
| Rule          | No       | Tool-budget-before-registering-a-tool guidance noted above but deferred — single occurrence, existing governance test already catches it at gate time |

Compaction skipped (not required for this prompt) — multiple memory-bank
files remain flagged as compression candidates (`activeContext.md`,
`progress.md`, `systemPatterns.md`, `techContext.md`, `productContext.md`,
`.claude/CLAUDE.md`); this is a pre-existing, already-tracked condition
across many prior sessions, not new to this one. Recommend a dedicated
`/cortex/analyze` or `compress_memory_bank()` pass rather than folding it
into this scoped gap-closure session.
