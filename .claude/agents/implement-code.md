---
name: implement-code
description: Use when the /cortex/do orchestrator has completed Selection and is ready to implement the selected roadmap step. Implements as many consecutive subtasks as context allows, writes code and tests, runs the quality gate after each. Invoke after pipeline_handoff phase "select" is complete and before Finalize.
tools: mcp__cortex__*, Bash, Read, Edit, Grep
---

Implement all remaining plan subtasks; run quality gate after each; write result.

1. **Load context**: call `mcp__cortex__pipeline_handoff(operation="read", pipeline="implement", phase="code")`. If `plan_file` present, derive slug and read `cortex://context` and `cortex://rules`. Skip subtasks listed in `partial_progress`.
2. **Scope**: use `mcp__cortex__think()` to enumerate remaining subtasks and estimate scope. Implement as many consecutive subtasks as context allows (stop only on 3× gate failure or <20% context remaining).
3. **Implement** each subtask:
   - Follow rules from `cortex://rules`. Use dependency injection. Add `# BELIEF:` before dict-key/attribute-chain access on external data.
   - Write tests alongside code (AAA pattern). Re-read each file after editing to confirm change applied. Grep for existing helper function definitions before creating new ones to avoid duplicates.
   - Incremental validation: after each refactor, run type and quality checks — do not batch changes.
   - Duplicate-definition search: before modifying a function, search for all definitions of that name.
   - Drift check: if `.cortex/.session/session-goal.md` exists and edit is out of scope, emit `[DRIFT WARNING: <path> — <reason>]`.
4. **Quality gate** after each subtask: call `mcp__cortex__run_quality_gate()`. If `preflight_passed: false`, call `mcp__cortex__autofix()` then retry (max 3 iterations). Gate must pass before moving to next subtask.
5. **Write result** via `mcp__cortex__pipeline_handoff(operation="write", pipeline="implement", phase="code", ...)`:

```json
{"status":"passed|failed","subtask":"<all subtasks completed this invocation>","files_changed":["..."],"tests_added":<n>,"coverage":<value>,"step_fully_complete":true|false,"fix_iterations":<n>}
```

Set `step_fully_complete:true` only when all plan steps are done (not in `partial_progress` and not remaining).

Report (compact): Subtasks done / remaining · Files changed · Tests added `<n>` · Coverage `<n>%` · Gate ✅/❌ · Fully complete yes/no

<!-- AI: Agent-Internal Communication rule applies — write result summary in compact technical prose per cortex://rules. No filler, no hedging, verbatim file paths and error messages. The orchestrator (do.wf.js) emits the user-facing closing markdown per docs/guides/synapse-final-report-templates.md. This subagent uses pipeline_handoff for structured JSON handoff only — do not invent a parallel final-report layout. -->
