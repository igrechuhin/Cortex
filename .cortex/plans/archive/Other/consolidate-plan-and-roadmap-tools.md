# Plan: Consolidate Plan and Roadmap Tools

**Status**: PENDING  
**Priority**: P2 (medium)  
**Estimated Effort**: 6–10 hours

## Goal

Reduce Cortex MCP tool count by consolidating two tool groups into operation-based dispatchers, following the Phase 50 pattern (`query_memory_bank`, `query_usage`). Target savings: 3 tool slots (40 → 37).

## Context

### Current State

- **Tool budget**: 40 registered (at MAX_REGISTERED_TOOLS), target 24 (long-term).
- **Group 1**: `create_plan` and `complete_plan` — plan lifecycle operations (create vs complete).
- **Group 2**: `add_roadmap_entry`, `remove_roadmap_entry`, `remove_roadmap_section` — roadmap mutations.
- Both groups share a domain and can use an `operation` parameter; parameters differ per operation but that is standard for dispatchers.

### Business Value

- **Slot savings**: 3 tools (1 from plan group, 2 from roadmap group).
- **Consistency**: Aligns with Phase 50 dispatcher pattern.
- **Discoverability**: Single entry point per domain with clear operation semantics.

### References

- [Tool optimization mapping](docs/architecture/tool-optimization-mapping.md)
- [Tool optimization baseline](docs/architecture/tool-optimization-baseline.md)
- [Tool description altitude rubric](docs/guides/tool-description-altitude-rubric.md) — target ≥ 4; aim for score 5 with examples.
- `tool_categories.py`: MAX_REGISTERED_TOOLS, TARGET_REGISTERED_TOOLS

## Implementation Steps

**Implementation sequence**: Execute in order (Step 1 → 2 → … → 7).

### Step 1: Consolidate plan tools (create_plan + complete_plan)

- Introduce `plan(operation="create"|"complete", ...)` dispatcher.
- **create**: Keep current create_plan params (title, content, slug, etc.).
- **complete**: Keep current complete_plan params (plan_title, summary, completion_date, progress_entry, plan_file_name).
- Internal: route by `operation` to existing handlers.
- Update `tool_categories.py`: replace create_plan and complete_plan entries with single `plan` entry.
- Remove `@mcp.tool()` from create_plan and complete_plan; keep handlers as internal helpers.
- Update `.cortex/config/optimization.json` tool_search lists if applicable.
- **Tool description**: Write `plan` docstring per [tool-description-altitude-rubric](docs/guides/tool-description-altitude-rubric.md) (Purpose, USE WHEN, input/output expectations; aim for examples).
- **Deliverables**: One `plan` tool; create_plan and complete_plan removed from MCP; governance test passes.

### Step 2: Update callers of create_plan and complete_plan

- Update Plan prompt (create-plan workflow) to call `plan(operation="create", ...)`.
- Update implement prompt, complete_plan callers (implement Step 5, plan-archiver agent) to call `plan(operation="complete", ...)`.
- Update AGENTS.md, CLAUDE.md, memory-bank-workflow.mdc, and any Synapse agent references.
- **Deliverables**: All callers use `plan`; no references to create_plan or complete_plan.

### Step 3: Consolidate roadmap tools (add_roadmap_entry, remove_roadmap_entry, remove_roadmap_section)

- Introduce `roadmap(operation="add_entry"|"remove_entry"|"remove_section", ...)` dispatcher.
- **add_entry**: entry_text, section, position (optional).
- **remove_entry**: entry_contains (unique substring).
- **remove_section**: section_heading_contains.
- Internal: route by `operation` to existing logic.
- Update `tool_categories.py`: replace three entries with single `roadmap` entry.
- Remove `@mcp.tool()` from add_roadmap_entry, remove_roadmap_entry, remove_roadmap_section; keep logic as helpers.
- **Tool description**: Write `roadmap` docstring per [tool-description-altitude-rubric](docs/guides/tool-description-altitude-rubric.md) (Purpose, USE WHEN, input/output expectations; aim for examples).
- **Deliverables**: One `roadmap` tool; three roadmap tools removed; governance test passes.

### Step 4: Update callers of roadmap tools

- Update memory-bank-updater agent, plan-creator agent, commit pipeline, implement prompt, and any other callers.
- Replace `add_roadmap_entry(...)`, `remove_roadmap_entry(...)`, `remove_roadmap_section(...)` with `roadmap(operation="add_entry"|"remove_entry"|"remove_section", ...)`.
- Update AGENTS.md, CLAUDE.md, memory-bank-workflow.mdc.
- **Deliverables**: All callers use `roadmap`; no references to legacy roadmap tools.

### Step 5: Update documentation and mapping

- Update `docs/api/tools.md` with `plan` and `roadmap` tool descriptions and operations.
- **Tool description altitude** (per [tool-description-altitude-rubric](docs/guides/tool-description-altitude-rubric.md)): Each new tool must score ≥ 4. Include:
  - **Purpose** — One-sentence statement of what the tool does.
  - **When to use** — USE WHEN guidance (e.g. when to call `plan` vs `roadmap`; when to use each operation).
  - **Input expectations** — Parameters, required vs optional, valid values for `operation` and operation-specific params.
  - **Output format** — RETURNS shape (success/error), key fields.
  - **Examples** (for score 5) — Embedded USE WHEN / EXAMPLES / input_examples where applicable.
- Update `docs/architecture/tool-optimization-mapping.md` with consolidation outcome.
- Update `docs/architecture/tool-optimization-baseline.md` baseline section with new tool count (37).
- **Deliverables**: Docs reflect consolidated tools; `plan` and `roadmap` descriptions meet altitude rubric.

### Step 6: Run regression suite

- Execute `execute_pre_commit_checks(phase="A")` (format, lint, type, quality, tests).
- Run `validate(check_type="roadmap_sync")`.
- Verify create-plan, implement, commit, and analyze workflows function with consolidated tools.
- **Deliverables**: All checks pass; no workflow breakage.

### Step 7: Record outcome

- Update activeContext.md with consolidation summary.
- Update roadmap; mark plan complete.
- **Deliverables**: Memory bank and roadmap reflect completion.

## Testing Strategy

- **Coverage target**: Minimum 95% for new dispatch logic and parameter validation.
- **Unit tests**: Test `plan` and `roadmap` handlers for each operation; verify parameter validation and routing.
- **Integration tests**: Call `plan(operation="create", ...)` and `plan(operation="complete", ...)`; call `roadmap(operation="add_entry"|"remove_entry"|"remove_section", ...)`; assert structure and side effects.
- **Regression**: Full pre-commit suite; governance test `TestToolCategoriesGovernance`; workflow smoke tests (create-plan, implement, commit, analyze).
- **AAA pattern**: All tests follow Arrange–Act–Assert.
- **Pydantic v2**: Use BaseModel for params and `model_validate_json()` for MCP JSON where applicable.

## Success Criteria

- **Tool count**: 37 registered (down from 40).
- **No breakage**: create-plan, implement, commit, analyze flows work with consolidated tools.
- **Documentation**: tools.md, mapping, and baseline updated.
- **Tool descriptions**: `plan` and `roadmap` descriptions score ≥ 4 on the [tool-description-altitude-rubric](docs/guides/tool-description-altitude-rubric.md).

## Risks & Mitigation

- **Risk**: Callers missed during migration.
- **Mitigation**: Grep for create_plan, complete_plan, add_roadmap_entry, remove_roadmap_entry, remove_roadmap_section before removing old tools; update all references.
- **Risk**: Parameter schema confusion for dispatcher.
- **Mitigation**: Tool descriptions per [tool-description-altitude-rubric](docs/guides/tool-description-altitude-rubric.md) (Purpose, USE WHEN, input/output); operation-specific param docs in tools.md.
