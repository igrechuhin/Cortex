---
title: "Context-Scoped Instruction Assembly"
component: context
work_type: feature
status: DONE
priority: High
created: 2026-04-06
depends_on: []
---

## Goal

When `implement-code` starts, assemble a scoped context packet instead of loading `cortex://context` broadly. The packet contains: the relevant plan + all its upstream dependency plans + only the `cortex://rules` sections relevant to the task type (Python vs. MCP vs. test-writing). This reduces context noise and prevents agents from hallucinating constraints from unrelated rules.

## Context

Inspired by OpenSpec's per-artifact context injection, which dynamically assembles only the content an agent needs. Currently, `cortex://context` loads the full memory bank, all active plans, and all rules — regardless of what is being implemented. For a task that only touches Python models, loading MCP development rules and data-science experiment conventions wastes tokens and dilutes focus. Scoped assembly solves this by computing the minimal relevant context for each task.

## Implementation Steps

### Step 1: Define task type taxonomy

- Add `TaskType` enum in `src/cortex/core/models.py`:
  - `PYTHON_CORE` — pure Python logic, models, utilities
  - `MCP_TOOL` — FastMCP tool implementation
  - `MCP_RESOURCE` — FastMCP resource implementation
  - `TEST` — test writing (any type)
  - `PROMPT` — synapse prompt authoring
  - `SCHEMA` — Pydantic model or schema work
  - `INFRA` — CI/CD, build, configuration
  - `DOCUMENTATION` — markdown, docstrings
- Add `infer_task_type(plan_content: str, files_touched: list[str]) -> list[TaskType]` in `src/cortex/core/task_classifier.py` — keyword + path-based heuristic; returns a list (tasks can be multi-type).

### Step 2: Tag rules sections by task type

- In `cortex://rules` resource (`src/cortex/resources/rules.py`), add metadata to each rules section.
- Add `filter_rules(rules_content: str, task_types: list[TaskType]) -> str` in `src/cortex/core/rules_filter.py`.
- Always include sections tagged `ALL` or untagged (universal rules).

### Step 3: Add dependency plan resolution

- Add `resolve_upstream_plans(plan_slug: str, plans_dir: Path) -> list[str]` in `src/cortex/core/artifact_graph.py`.
- Resolve transitive `depends_on` in topological order.
- Include only `DONE` upstream plans.

### Step 4: Add `scope: str` parameter to `cortex://context` resource

- Accept `scope` from session config.
- Scope format: `"plan:<slug>"`.
- Keep default broad behavior when scope missing.

### Step 5: Update `implement-code` subagent to set scope

- Set scope before loading context.
- Read scoped `cortex://context`.
- Continue implementation with scoped packet.

### Step 6: Add token budget reporting

- Include `context_stats` section in scoped context output.

### Step 7: Tests

- Unit tests for classifier/filter/dependency resolver/context assembly.
- Integration coverage for scope propagation and scoped context retrieval.

## Partial Progress Log

- 2026-04-10: Implemented TaskType/task classifier, rules filtering, upstream plan resolution, and scoped context packet with context_stats plus focused tests — files: src/cortex/core/models/_enums.py, src/cortex/core/models/__init__.py, src/cortex/core/task_classifier.py, src/cortex/core/rules_filter.py, src/cortex/core/artifact_graph.py, src/cortex/tools/context/scoped_context.py, src/cortex/tools/optimization/handlers.py, tests/unit/test_task_classifier.py, tests/unit/test_rules_filter.py, tests/unit/test_artifact_graph.py, tests/tools/test_phase4_optimization.py
- 2026-04-10: Completed scope propagation and scoped-context integration in implement flow with cache-key separation and expanded scoped behavior tests — files: src/cortex/tools/context/scoped_context.py, src/cortex/tools/optimization/handlers.py, .cortex/synapse/cursor-agents/implement-code.md, .cortex/synapse/prompts/do.md, .cursor/agents/implement-code.md, .claude/agents/implement-code.md, tests/tools/test_phase4_optimization.py
