---
title: "Post-Prompt Analysis: Plan Creation for Usage-Pattern Analytics"
component: synapse
work_type: investigation
status: stable
priority: normal
---

## Post-Prompt Analysis

Calling prompt: `/cortex/plan`. Single goal: register a finite plan to make `cortex://analysis` return real
`usage_patterns` and `tools` data. No source files were edited.

## Context Effectiveness

`cortex://analysis` (default `context` target) returned data. Current session: 1 call, 946-token budget fully
utilised, 2 files selected (`activeContext.md`, `roadmap.md`), average relevance 0.0 for the bootstrap record.
Aggregate: 298 sessions, 1,649 entries. Learned patterns: average 42% budget utilisation (~16k tokens unused per
call); `projectBrief.md` loaded in 330 of 331 calls at 0.483 average relevance, flagged "consider excluding for
most tasks". Role recommendations exist for debugging, feature, and planning, all at a 10,000-token budget, all
with low average relevance. No zero-budget warnings.

Token budget: seven files over the 500-word compression threshold, `log.md` (8,637 words) and `activeContext.md`
(3,380 words) the largest. Compaction was not run — this was a plan-only pass.

## Session Optimization

Not run. Step 5 sets `analysis_target: usage_patterns`, which reads `.cortex/access-log.json`; that file has no
writer in `src/`, so the target returns empty by construction. This is the exact defect the plan registered in
this session addresses, and running the step would only reproduce it. No mistake patterns or tool anomalies were
observed in this session; no multi-goal scope risk — one goal, one plan, no source edits.

## Tools Optimization

Not run, same reason. Step 6 sets `analysis_target: tools`, which routes to health-check tool analysis against
`project_root/src/cortex/tools`. That path exists in this repository, so the target would return real numbers
here but reports zero in any consuming project. Also covered by the registered plan.

## Improvements Router

One plan was already created this session and covers every finding above:
`.cortex/plans/wire-usage-pattern-analytics-to-session-logs-and-package-relative-tool-analysis.md`. No Skill or
Rule artifact is warranted — the gap is a missing write path in Cortex, not agent behaviour.

Deferred, not registered: `projectBrief.md` is loaded almost every call at low relevance, and memory-bank
compression candidates are accumulating. Both are context-budget work, unrelated to this session's goal.
