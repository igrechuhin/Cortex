# Session Optimization: Analyze 2026-02-19 Follow-ups

**Status**: PENDING
**Source**: End-of-session analysis report `.cortex/reviews/session-optimization-2026-02-19T21-35.md`

## Goal

Implement the optimization recommendations from the 2026-02-19 end-of-session analysis.

## Recommendations

1. **Implement/analyze prompts** – Add explicit examples: `load_context(task_description='...', token_budget=10000)` for implement and fix/debug so agents do not pass or rely on zero budget.
2. **Memory bank edits** – In analyze and implement prompts, reiterate that roadmap.md (and all memory bank files) must be updated only via Cortex MCP tools (remove_roadmap_entry, add_roadmap_entry, manage_file); do not use Write/StrReplace/ApplyPatch on memory bank paths.
3. **Roadmap sync** – When adding new plans to the repo, ensure each has a corresponding roadmap entry with the plan filename (e.g. "Plan: .cortex/plans/session-optimization-foo.md") so roadmap_sync validation stays valid.

## Implementation Steps

1. Update implement and analyze prompts with explicit load_context budget examples and memory-bank-only MCP edit reminders.
2. Add roadmap sync guidance (link new plans in roadmap) to create-plan or implement prompts as needed.
3. Verify roadmap_sync and context-effectiveness after changes.
