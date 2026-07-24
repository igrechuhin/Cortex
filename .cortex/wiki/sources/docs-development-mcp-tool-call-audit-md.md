# MCP tool call audit (argument wiring / bridging)

This document is the **Step 1 audit** for the plan [Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps](../../.cortex/plans/archive/Blocker/fix-mcp-plan-tool-argument-bridging.md). It inventories MCP tool call sites in orchestration layers and classifies each as **Safe** (full JSON payload instructed) or **Unsafe** (name-only or underspecified).

## Scope

- **Orchestration layers**: Claude Code subagents and Synapse prompts that instruct agents to call Cortex MCP tools.
- **Tools in scope**: `plan`, `manage_file`, `rules`, `run_quality_gate`, `run_docs_gate`, `pipeline_handoff`, `update_memory_bank`, `load_context`, `autofix`, `get_structure_info`, `validate`.

## Classification

| Classification | Meaning |
|----------------|--------|
| **Safe** | Instructions explicitly require full JSON arguments (e.g. `operation`, `file_name`, `plan_title`, `phase`, `checks`) and document required fields. |
| **Unsafe** | Tool is invoked by name only, or instructions do not require all required parameters, relying on tool-side defaults. |

## Implement pipeline

| Call site | Tool(s) | Argument style | Classification |
|-----------|---------|-----------------|----------------|
| `.claude/agents/implement-select.md` | `manage_file(file_name="roadmap.md", operation="read")` | Full payload | **Safe** |
| `.claude/agents/implement-select.md` | `rules(operation="get_relevant", task_description="...")` | Full payload | **Safe** |
| `.claude/agents/implement-code.md` | `pipeline_handoff(operation="read_task", pipeline="implement", phase="code")` | Full payload | **Safe** |
| `.claude/agents/implement-code.md` | `run_quality_gate()` | Zero-arg; config from pipeline task file when present | **Safe** |
| `.claude/agents/implement-code.md` | `autofix()` | No params required for this tool | **Safe** |
| `.claude/agents/implement-finalize.md` | `pipeline_handoff(operation="read_task", pipeline="implement", phase="finalize")` | Full payload | **Safe** |
| `.claude/agents/implement-finalize.md` | `plan(operation="complete", plan_title="...", summary="...", plan_file_name="...", progress_entry="...", completion_date="...")` | Full payload | **Safe** |
| `.claude/agents/implement-finalize.md` | `update_memory_bank(operation="progress_append", ...)` / `active_context_append` | Full payload | **Safe** |
| `.claude/agents/implement-verify.md` | `manage_file(file_name="roadmap.md", operation="read")`, `manage_file(file_name="progress.md", operation="read")` | Full payload | **Safe** |

Synapse claude-agents (`.cortex/synapse/claude-agents/`) mirror the same patterns with explicit arguments; classification is **Safe** for implement-select, implement-finalize, implement-verify.

## Commit pipeline

| Call site | Tool(s) | Argument style | Classification |
|-----------|---------|-----------------|----------------|
| `.claude/agents/commit-preflight.md` | `rules(operation="get_relevant", task_description="...")` | Full payload | **Safe** |
| `.claude/agents/commit-checks.md` | `pipeline_handoff(operation="read_task", pipeline="commit", phase="checks")` | Full payload | **Safe** |
| `.claude/agents/commit-checks.md` | `run_quality_gate()` | Zero-arg; config from pipeline task file when present | **Safe** |
| `.claude/agents/commit-checks.md` | `load_context(task_description="...", token_budget=15000)` | Full payload | **Safe** |
| `.claude/agents/commit-checks.md` | `autofix()` | No params required | **Safe** |
| `.claude/agents/commit-docs.md` | `manage_file(file_name="activeContext.md", operation="read")`, etc. | Full payload | **Safe** |
| `.claude/agents/commit-docs.md` | `manage_file(file_name="...", operation="write", content="...", change_description="...")` | Full payload | **Safe** |
| `.claude/agents/commit-docs.md` | `run_docs_gate()` | Zero-arg Phase B validation | **Safe** |
| `.claude/agents/commit-docs.md` | `get_structure_info()`, `manage_session_scripts(operation="capture")` | Full payload / no required params | **Safe** |

## Other agents and prompts

| Call site | Tool(s) | Argument style | Classification |
|-----------|---------|-----------------|----------------|
| `.cortex/synapse/agents/quality-checker.md` | `run_quality_gate()` | Zero-arg Phase A | **Safe** |
| `.cortex/synapse/agents/error-fixer.md` | `rules(operation="get_relevant", task_description="...")` | Full payload | **Safe** |
| `.cortex/synapse/agents/error-fixer.md` | `autofix()` then `run_quality_gate()` | Zero-arg tools | **Safe** |
| `.cortex/synapse/agents/error-fixer.md` | Documents anti-pattern: missing `file_name`/`operation` for `manage_file`, missing `operation` for `rules` | N/A (guardrails) | **Safe** |

## Plan / docs flows

- **`/user-cortex/plan`** (MCP client prompt): The plan file states that this flow should prefer `plan(operation="create", ...)` and `plan(operation="register", ...)` with full payloads; fallback to direct writes only when MCP is unavailable. The **bridge** (the client's `CallMcpTool`-equivalent) must forward the `arguments` object verbatim. If the IDE invokes `plan` without arguments, the tool now returns a clear error (Step 6). Remaining risk: **Unsafe** only if the orchestrator does not construct the payload; the prompts and this repo’s tool implementation are aligned with **Safe** usage.

## Summary

- **Implement and commit pipelines**: All documented call sites in `.claude/agents/` and `.cortex/synapse/claude-agents/` instruct **full JSON payloads** (operation, file_name, phase, plan_title, etc.). Classified **Safe**.
- **Plan tool**: Server-side no-arg and missing-field handling is fixed (Step 6). Orchestrators (implement-finalize, plan/docs) are instructed to pass full payloads. Any remaining failure is at the **bridge** (`CallMcpTool` not forwarding `arguments`).
- **Next steps (from plan)**: Step 4 (harden `/user-cortex/plan` to always use structured `plan` ops), Step 5 (audit/fix other tools’ argument-bridging), Step 7 (more tests and guardrails).

## References

- Plan: [fix-mcp-plan-tool-argument-bridging.md](../../.cortex/plans/archive/Blocker/fix-mcp-plan-tool-argument-bridging.md)
- MCP client `CallMcpTool` contract: see “Developer Notes” in the plan.
- Tool payload contracts: `docs/api/tools.md` and plan Step 2.
