# Plan: Documentation Completeness & Accuracy

## Status: COMPLETE

Steps 1–5 complete (2026-02-23).

## Priority: P1 (High)

## Created: 2026-02-21

## Effort: 1 sprint

## Motivation

Comprehensive review (2026-02-21) found documentation gaps and inaccuracies:

- Tool count claims "52 MCP tools" — actual count is 101+ (142 `@mcp.tool` decorators)
- Phase 5 evaluation tools (phase5_evaluation.py, dashboard helpers) not documented
- Phase 57/58 not in API docs
- No end-to-end workflow examples
- Stale module references in `modules.md`
- No generated defaults reference for configuration

---

## Step 1: Fix Tool Count and Phase Coverage in API Docs ✅ COMPLETED

**Files to update:**

| File | Issue | Fix |
|------|-------|-----|
| `docs/index.md` | Claims "52 MCP tools" | Update to actual count |
| `docs/getting-started.md` | Claims "52 MCP tools" | Update to actual count |
| `docs/api/tools.md` | Missing Phase 5 eval, Phase 57, Phase 58 tools | Add tool documentation |
| `docs/api/modules.md` | Missing Phase 8+, recent modules | Add module docs |

**Action:**

1. Count actual tool registrations (`@mcp.tool()` decorators)
2. Update all references to correct count
3. Document all undocumented tools with: description, parameters, return type, example
4. Add Phase 57 (evaluation-driven improvement) and Phase 58 (multi-agent) sections

**Acceptance criteria:** Tool count accurate. All registered tools documented.

---

## Step 2: Add End-to-End Workflow Examples ✅ COMPLETED

**Create `docs/guides/workflows.md`** with:

1. **New Project Setup Workflow**: Initialize → configure → create memory bank → validate
2. **Session Lifecycle**: session_start → load_context → work → compact_session → handoff
3. **Code Quality Workflow**: pre-commit checks → fix quality issues → validate → commit
4. **Refactoring Workflow**: analyze patterns → detect consolidation → execute refactoring → validate
5. **Plan Management**: create plan → update progress → archive completed plans

Each workflow should include:

- Tool call sequence with example inputs/outputs
- Decision points and branching
- Error recovery steps

**Acceptance criteria:** 5+ documented workflows with concrete tool call examples.

---

## Step 3: Synchronize Architecture Documentation ✅ COMPLETED

**Issues:**

1. `docs/architecture.md` doesn't cover Phase 8+ additions
2. Bridge transport (HTTP/SSE) mentioned but not explained
3. Synapse integration architecture sparse
4. Health check module architecture not detailed
5. Manager lifecycle not fully diagrammed

**Action:**

1. Update architecture diagrams to include all current layers
2. Add Bridge transport section (stdio vs HTTP/SSE modes)
3. Document Synapse integration architecture (submodule pattern, directory layout, rule loading)
4. Add health check and monitoring architecture section
5. Update manager initialization diagram with lazy loading flow

**Acceptance criteria:** Architecture docs reflect current system. No undocumented subsystems.

**Done (2026-02-23):** Diagram updated (transport line); Layer 2 tool list updated to current phases and modules; Bridge Transport section added (stdio/SSE/streamable-http, Bridge proxy); Layer 3 expanded with ManagerRegistry and lazy-loading flow; Synapse Integration Architecture section added (layout, rule loading, submodule); Health Check and Monitoring Architecture section added (connection health, structure health, health_check module).

---

## Step 4: Generate Configuration Defaults Reference ✅ COMPLETED

**Current state:** `docs/guides/configuration.md` shows example configs but no generated reference of actual defaults.

**Action:**

1. Create `docs/api/configuration-reference.md`
2. Extract all default values from Pydantic config models
3. Document each setting: name, type, default, valid range, description
4. Auto-generate from source (script or MCP tool) to keep in sync

**Acceptance criteria:** Complete configuration reference with all defaults. Generation script/tool exists.

**Done (2026-02-23):** Created `docs/api/configuration-reference.md` with tables for validation, optimization, structure, and environment/transport; added `.cortex/synapse/scripts/python/generate_config_reference.py` that writes `docs/api/config-defaults.json` from `ValidationConfigModel()`, `DEFAULT_OPTIMIZATION_CONFIG` (+ tool_search), and `DEFAULT_STRUCTURE`.

---

## Step 5: Archive Completed Investigation Plans ✅ COMPLETED

**3 completed plans** moved from root of `.cortex/plans/` to archive (2026-02-23):

- `phase-investigate-execute_pre_commit_checks-failure-20260217-201854.md` → `archive/Investigations/2026-02-17/`
- `phase-investigate-fix_markdown_lint-failure-20260216-204350.md` → `archive/Investigations/2026-02-16/`
- `session-optimization-load-context-and-test-typing.md` → `archive/SessionOptimization/`

**Action:** Moved to `archive/` directory; roadmap entries for these plans removed.

**Acceptance criteria:** Only active/planned work in plans root. Archive organized.

---

## Verification

After all steps:

1. `grep -r "52 MCP tools" docs/` returns zero results
2. All `@mcp.tool()` registrations have corresponding documentation
3. 5+ workflow examples in docs
4. Architecture diagrams current
5. Configuration reference generated and complete
6. Plans directory clean (only active/planned in root)
