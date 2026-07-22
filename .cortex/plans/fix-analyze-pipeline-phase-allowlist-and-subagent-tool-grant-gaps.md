## Context

The `/cortex/analyze` workflow (`.cortex/synapse/prompts/analyze.md`, `cursor-agents/analyze-context.md`, `analyze-session.md`, `analyze-tools.md`) instructs writing `pipeline_handoff()` results to `phase="context"`, `phase="session"`, and `phase="tools"`, but `src/cortex/tools/session/pipeline_handoff.py`'s phase allowlist only permits: `checks, code, coverage, docs, final-gate, finalize, fix, gate_feedback, gate_iterations, preflight, quality, review, select, tests, validate, verify`. Every analyze run hits "Unknown phase" for 3 of its 4 steps and falls back to overloading `phase="review"`, losing per-step handoff isolation for `analyze-compact`'s downstream report assembly.

Separately, the `analyze-context`, `analyze-session`, `analyze-tools`, and `analyze-compact` subagents are registered with `Tools: mcp__cortex__*` only, but their own prompts require `ReadMcpResourceTool` (to read `cortex://analysis`), `Bash` (for `git log`/`git diff`), and generic `Write` (for report files) to complete their prescribed steps. Every `/cortex/analyze` run this session had all four steps run inline by the orchestrator instead of via the dedicated subagent, defeating the purpose of the subagent split (context-window isolation).

Evidence: discovered via direct failure during a live `/cortex/analyze` run on 2026-07-22 — see `.cortex/reviews/session-optimization-2026-07-22T16-42.md`, "Mistake Patterns Identified" and "Optimization Recommendations" sections.

## Plan

1. Extend the `pipeline_handoff` phase allowlist (`src/cortex/tools/session/pipeline_handoff.py` and/or its validation module) to include `context`, `session`, `tools` — or generalize validation to accept any snake_case identifier instead of a fixed enum.
2. Grant `ReadMcpResourceTool`, `Bash`, and `Write` to the four `analyze-*` subagents' tool lists so they can self-sufficiently complete their own documented steps without orchestrator fallback.
3. Add/update tests covering the newly-accepted phase values.
4. Verify a full `/cortex/analyze` run no longer hits "Unknown phase" and the analyze-* subagents run standalone (not inline-fallback).

## Acceptance Criteria

- `pipeline_handoff(operation="write", phase="context"|"session"|"tools", pipeline="analyze", ...)` succeeds without error.
- `analyze-context`/`analyze-session`/`analyze-tools`/`analyze-compact` subagent definitions list the additional tools.
- Quality gate passes.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
