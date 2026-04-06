---
title: "Schema-Defined Workflow Variants"
component: planning
work_type: feature
status: PENDING
priority: medium
created: 2026-04-06
depends_on: []
---

## Goal

Allow project teams to define custom Cortex workflow variants in `.cortex/schemas/`. Built-in schemas ship with Cortex (e.g., `fast-path`, `compliance`, `data-science`). The `session()` tool picks the active schema from project config, and the pipeline orchestrator (`/cortex/do`) adapts its phase sequence accordingly.

## Context

Inspired by OpenSpec's forkable schemas. Currently Cortex has one fixed pipeline: plan → implement → review → commit. Some tasks are trivial (no review needed); some are high-risk (need a security gate); some are domain-specific (data science needs EDA and experiment tracking). A schema system enables these variants without forking the codebase.

## Implementation Steps

### Step 1: Define schema model

- Add `WorkflowSchema` Pydantic model in `src/cortex/core/models.py`:
  - `name: str`
  - `description: str`
  - `phases: list[WorkflowPhase]`
  - `inherits: str | None` (name of a base schema to extend)
- Add `WorkflowPhase` model:
  - `name: str`
  - `tool: str` (MCP tool or slash command to invoke)
  - `required: bool`
  - `condition: str | None` (Python expression evaluated against session state; phase skipped if False)
  - `config: dict[str, str]` (phase-specific config passed to tool)

**Verification**: Models defined, fully typed, no `Any`.

### Step 2: Define built-in schemas

Create `.cortex/schemas/` with three built-in YAML schema files:

**`default.yaml`** — current behavior:

```yaml
name: default
description: Standard plan → implement → review → commit pipeline
phases:
  - name: plan
    tool: /cortex/plan
    required: true
  - name: implement
    tool: /cortex/do
    required: true
  - name: review
    tool: /cortex/review
    required: true
  - name: commit
    tool: /cortex/commit
    required: true
```

**`fast-path.yaml`** — skip review for trivial tasks:

```yaml
name: fast-path
description: plan → implement → commit (no review gate)
phases:
  - name: plan
    tool: /cortex/plan
    required: true
  - name: implement
    tool: /cortex/do
    required: true
  - name: commit
    tool: /cortex/commit
    required: true
```

**`compliance.yaml`** — adds a mandatory security gate:

```yaml
name: compliance
description: plan → implement → security-review → review → commit
phases:
  - name: plan
    tool: /cortex/plan
    required: true
  - name: implement
    tool: /cortex/do
    required: true
  - name: security-review
    tool: /cortex/review
    required: true
    config:
      mode: security-only
  - name: review
    tool: /cortex/review
    required: true
  - name: commit
    tool: /cortex/commit
    required: true
```

**`data-science.yaml`** — adds EDA and experiment tracking phases:

```yaml
name: data-science
description: explore → plan → EDA → implement → experiment-log → review → commit
phases:
  - name: explore
    tool: /cortex/explore
    required: false
  - name: plan
    tool: /cortex/plan
    required: true
  - name: eda
    tool: /cortex/do
    required: false
    condition: "session_config.get('eda_required', False)"
  - name: implement
    tool: /cortex/do
    required: true
  - name: review
    tool: /cortex/review
    required: true
  - name: commit
    tool: /cortex/commit
    required: true
```

**Verification**: All four YAML files valid, parseable into `WorkflowSchema`.

### Step 3: Add schema loader

- Add `load_schema(name: str, project_root: Path) -> WorkflowSchema` in `src/cortex/core/schema_loader.py`.
- Search order: `.cortex/schemas/<name>.yaml` (project-local) → built-in schemas → raise `SchemaNotFoundError`.
- Support `inherits`: merge phases from parent schema, overriding with child definitions.

**Verification**: Loader finds project-local schemas first; falls back to built-ins; `inherits` merging works.

### Step 4: Add schema selection to session config

- Add `workflow_schema: str` field to `SessionConfig` in `src/cortex/core/session_config.py` (default: `"default"`).
- `session()` reads `workflow_schema` from `.cortex/session.yaml` and loads the schema.
- Include active schema name and phase list in `session()` output.

**Verification**: `session()` output includes schema name and phases; changing `session.yaml` changes the loaded schema.

### Step 5: Update pipeline orchestrator to read schema

- In the do-orchestrator (prompt or `pipeline_handoff.py`):
  1. Call `session()` to get active schema.
  2. Execute phases in schema order.
  3. Evaluate `condition` for optional phases; skip if condition is False.
  4. For required phases, block on completion before advancing.

**Verification**: Orchestrator skips optional phases when condition is False; required phases always run.

### Step 6: Add `manage_file(operation="list_schemas")` and `"fork_schema"`

- `list_schemas`: returns names + descriptions of all available schemas (built-in + project-local).
- `fork_schema(base: str, new_name: str)`: copies a built-in schema to `.cortex/schemas/<new_name>.yaml` for local customization.

**Verification**: List returns all schemas; fork creates a local copy; forked schema takes precedence over built-in.

### Step 7: Tests

- Unit: `WorkflowSchema` and `WorkflowPhase` model validation.
- Unit: Schema loader — project-local precedence, fallback, `inherits` merging, not-found error.
- Unit: Condition evaluation — True, False, invalid expression (graceful error).
- Unit: `list_schemas`, `fork_schema`.
- Integration: Full pipeline with `fast-path` schema (review phase skipped).

**Verification**: All tests pass, ≥ 95% coverage on new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `WorkflowSchema`, `WorkflowPhase` | `src/cortex/core/models.py` | full file |
| 2 | YAML schema files | `.cortex/schemas/` | all four files |
| 3 | `load_schema` | `src/cortex/core/schema_loader.py` | full file |
| 4 | `workflow_schema` field | `src/cortex/core/session_config.py` | full file |
| 5 | Schema-aware orchestrator | `pipeline_handoff.py` / do prompt | full file |
| 6 | `list_schemas`, `fork_schema` | `src/cortex/tools/manage_file.py` | full file |
| 7 | Test files | `tests/` | new test files |

## Dependencies

- Existing `session()` tool and `SessionConfig`
- Existing `pipeline_handoff` tool
- `WorkflowSchema` / `WorkflowPhase` models (Step 1)
- `schema_loader.py` (Step 3)
- Explore workflow plan (for `data-science` schema — optional integration)

## Success Criteria

- Four built-in schemas ship with Cortex.
- Project teams can fork and customize schemas locally.
- `session()` reports the active schema and its phases.
- The do-orchestrator respects schema phase order and conditions.
- No `Any` types; functions ≤ 30 lines; ≥ 95% coverage.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Model validation; loader search order; `inherits` merging; condition evaluation.
- **Integration**: `fast-path` schema run (review skipped); `compliance` schema run (two review phases).
- **Edge cases**: Schema not found; cyclic `inherits` (detect and error); condition expression with syntax error.
