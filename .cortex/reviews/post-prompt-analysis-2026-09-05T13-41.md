---
title: "Post-Prompt Analysis: Do Loop for Usage-Pattern Analytics"
component: synapse
work_type: investigation
status: stable
priority: normal
---

## Post-Prompt Analysis

Calling prompt: `/cortex/do-loop`. One iteration, one plan, roadmap drained. Single goal held throughout;
no unrelated work bundled in.

## Context Effectiveness

Not re-read this pass. The prior post-prompt run (2026-09-05T13-02) recorded the current figures:
298 sessions, 1,649 entries, 42% average budget utilisation, `projectBrief.md` loaded in 330 of 331 calls
at 0.483 relevance. Nothing in this pass changes them.

## Session Optimization

`cortex://analysis` with `analysis_target: usage_patterns` returned an empty payload — `access_frequency`,
`co_access_patterns`, `task_patterns`, and `unused_files` all empty. This is a stale-process artifact, not a
regression: the running MCP server imported `pattern_analyzer` before this pass rewrote it. Running the new
projection directly against this repository through the project virtualenv returns 9,695 access records,
7 files in `access_frequency`, 21 co-access pairs, and 1,390 task patterns. The fix is correct; the server
process is behind it.

Recurring pattern worth recording: the same stale-import effect was noted on 2026-08-31 for the prediction
grading hook. Any pass that changes a module already imported by the running server needs an operator restart
before its effect is observable through `cortex://` resources, and a verification step that reads a resource
will falsely report failure until then.

## Tools Optimization

Not run separately. The `tools` target reads through the same stale process, and in this repository the old
hardcoded path and the new package-relative one resolve to the same directory, so the read would not have
distinguished them. The subagent's in-pass check reported 14 tools with `tools_dir` resolved from the imported
package; `get_tools_dir()` in `health_check_operations.py` was confirmed present by direct read.

## Improvements Router

No Skill, Plan, or Rule artifact emitted. The one finding above is an operator action (restart the MCP server),
not a durable behaviour change.

Deferred, unchanged from the prior run: `projectBrief.md` low-relevance loading, and seven memory-bank files
over the 500-word compression threshold (`log.md` at 8,799 words, `activeContext.md` at 3,558).
