---
title: "Context-Scoped Instruction Assembly"
component: context
work_type: feature
status: PENDING
priority: high
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

**Verification**: `infer_task_type` returns correct types for representative inputs; no `Any`.

### Step 2: Tag rules sections by task type

- In `cortex://rules` resource (`src/cortex/resources/rules.py`), add metadata to each rules section:
  - Tag each section header with one or more `TaskType` values in a comment or frontmatter.
  - Example: `<!-- task_types: PYTHON_CORE, SCHEMA -->` above a rules section.
- Add `filter_rules(rules_content: str, task_types: list[TaskType]) -> str` in `src/cortex/core/rules_filter.py`.
- Always include sections tagged `ALL` or untagged (universal rules).

**Verification**: `filter_rules` returns only relevant sections; universal rules always present.

### Step 3: Add dependency plan resolution

- Add `resolve_upstream_plans(plan_slug: str, plans_dir: Path) -> list[str]` in `src/cortex/core/artifact_graph.py` (extend from artifact graph plan).
- Recursively resolves the transitive closure of `depends_on`, returning plan slugs in topological order.
- Returns only DONE plans (completed dependencies provide stable context; in-progress ones are excluded to avoid partial-state confusion).

**Verification**: Transitive resolution works for chains and diamonds; in-progress plans excluded.

### Step 4: Add `scope: str` parameter to `cortex://context` resource

- In `src/cortex/resources/context.py`, accept `scope` from session config (set via `pipeline_handoff` before `implement-code` runs).
- `scope` format: `"plan:<slug>"` — load the specified plan + its resolved upstream plans + filtered rules.
- Default (no scope): existing broad behavior (backward compatible).
- Assemble the context packet:
  1. Session metadata (always included).
  2. Constitution (always included, if present).
  3. Upstream dependency plans (DONE only, in topo order).
  4. Current plan (full content).
  5. Filtered rules (by inferred task type).
  6. Explore log if referenced (summary only).

**Verification**: `cortex://context` with `scope="plan:my-plan"` returns scoped packet; without scope returns full context.

### Step 5: Update `implement-code` subagent to set scope

- In the `implement-code` subagent prompt (`.cortex/synapse/cursor-agents/implement-code.md`):
  1. Before loading context, call `pipeline_handoff(operation="write", key="context_scope", value="plan:<slug>")`.
  2. Read `cortex://context` (scope is now set).
  3. Proceed with implementation using scoped context.

**Verification**: `implement-code` agent reads a scoped context packet, not the full context.

### Step 6: Add token budget reporting

- In the context resource, include a `context_stats` section in the response:
  - `total_tokens_estimate: int`
  - `sections: dict[str, int]` — token estimate per section
  - `rules_sections_included: int` / `rules_sections_total: int`
- This allows agents to see what was included/excluded and users to audit context efficiency.

**Verification**: `context_stats` section present in scoped context response; counts are accurate.

### Step 7: Tests

- Unit: `infer_task_type` — representative inputs for each `TaskType`.
- Unit: `filter_rules` — sections included/excluded correctly; universal rules always present.
- Unit: `resolve_upstream_plans` — linear chain, diamond, DONE/IN_PROGRESS filtering.
- Unit: Context assembly — scoped vs. unscoped; all sections present in correct order.
- Unit: Token budget reporting.
- Integration: Full pipeline — set scope → read context → verify packet content.

**Verification**: All tests pass, ≥ 95% coverage on new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `TaskType`, `infer_task_type` | `src/cortex/core/` | `models.py`, `task_classifier.py` |
| 2 | `filter_rules`, task type tags | `src/cortex/resources/rules.py`, `src/cortex/core/rules_filter.py` | full files |
| 3 | `resolve_upstream_plans` | `src/cortex/core/artifact_graph.py` | full file |
| 4 | `scope` param in context | `src/cortex/resources/context.py` | full file |
| 5 | Scope setting in `implement-code` | `.cortex/synapse/cursor-agents/implement-code.md` | full file |
| 6 | `context_stats` in response | `src/cortex/resources/context.py` | context assembly |
| 7 | Test files | `tests/` | new test files |

## Dependencies

- Existing `cortex://context` resource
- Existing `pipeline_handoff` tool
- `implement-code` subagent
- `TaskType` enum (Step 1)
- `infer_task_type` (Step 1)
- `filter_rules` (Step 2)
- `resolve_upstream_plans` (Step 3) — depends on artifact graph plan (can be implemented independently with a simpler version)

## Success Criteria

- `implement-code` reads a scoped context packet containing only the relevant plan, its dependencies, and relevant rules sections.
- Scoped context reduces estimated token usage by at least 30% compared to full context for single-plan tasks.
- Full context (no scope) continues to work as before (backward compatible).
- No `Any` types; functions ≤ 30 lines; ≥ 95% coverage.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Task type inference; rules filtering; upstream resolution; context assembly order.
- **Integration**: End-to-end scoped context assembly with real plan files.
- **Edge cases**: Plan with no dependencies (only self + filtered rules); all rules sections match (full rules returned); no rules sections match (only universal rules returned); scope referencing non-existent plan (error with clear message).
