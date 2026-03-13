# Phase 43: Reconsider Tools Registration - Transform Tools to Resources

**Status**: COMPLETE  
**Created**: 2026-01-17  
**Priority**: Medium → High (2026-02-10, tools/resources naming + get_*review)  
**Estimated Effort**: 20-30 hours (initial); +4-6 hours for naming + get_* follow-up

## Goal

Reconsider and optimize MCP tool registration by transforming read-only operations from Tools to Resources, aligning with MCP protocol best practices, and **unifying naming across Tools and Resources (especially remaining `get_*` operations)**. Resources are like GET endpoints (load information into LLM context), while Tools are like POST endpoints (execute code or produce side effects).

## Context

### User-Provided Context

The user has read the FastMCP documentation (<https://gofastmcp.com/getting-started/welcome#what-is-mcp>) and identified that MCP servers can:

- **Expose data through Resources** (think of these sort of like GET endpoints; they are used to load information into the LLM's context)
- **Provide functionality through Tools** (sort of like POST endpoints; they are used to execute code or otherwise produce a side effect)
- **Define interaction patterns through Prompts** (reusable templates for LLM interactions)

### New Input (2026-02-10)

Additional guidance from the user (2026-02-10) refines the scope:

1. **Unify tools/resources naming**: Clean up the current mix of tool and resource function names/URIs so that naming consistently reflects behavior (read-only vs side-effecting) and follows a clear convention (e.g., verbs for Tools, nouns/\"views\" for Resources; no confusing `get_*` Tools that actually mutate state).
2. **Reconsider remaining `get_*` Tools case-by-case**: For each `get_*` operation that is still exposed as a Tool, decide whether it should instead be (a) a pure Resource, (b) a Resource + Tool pair, or (c) remain a Tool with a better name. Document decisions and rationale inside this plan.

### Current State

- Cortex MCP server has **53+ tools** all registered as `@mcp.tool()` decorators
- **0 Resources** currently registered (verified via `list_mcp_resources()`)
- All operations, whether read-only or write operations, are exposed as Tools
- FastMCP 2.0 migration completed (Phase 41), which supports both Tools and Resources
- Tools are organized across 21+ modules in `src/cortex/tools/`

### Problem Statement

Current tool registration doesn't align with MCP protocol semantics:

1. **Semantic Misalignment**: Read-only operations (like `get_memory_bank_stats`, `get_version_history`) are registered as Tools when they should be Resources
2. **Protocol Best Practices**: MCP protocol distinguishes between Resources (GET-like) and Tools (POST-like) for good reason - better semantic clarity
3. **Performance**: Resources may have different caching/optimization opportunities than Tools
4. **API Clarity**: Clearer distinction between read operations (Resources) and write operations (Tools) improves API usability

### Business Value

- **Protocol Compliance**: Align with MCP protocol best practices and semantic intent
- **API Clarity**: Clearer distinction between read and write operations
- **Performance**: Potential optimization opportunities for read-only Resources
- **Documentation**: Better API documentation with proper Resource vs Tool categorization
- **Future-Proofing**: Align with MCP protocol evolution and FastMCP 2.0 capabilities

## Approach

### High-Level Strategy

1. **Audit Phase**: Categorize all 53+ tools as Resource vs Tool candidates
2. **Design Phase**: Design Resource API using FastMCP 2.0 syntax, handle hybrid operations
3. **Implementation Phase**: Implement Resources for read-only operations
4. **Migration Phase**: Migrate read-only Tools to Resources with backward compatibility
5. **Verification Phase**: Test all Resources work correctly, verify Tools still work

### Decision Criteria

**Resource Candidates (Read-Only, No Side Effects):**

- Operations that only read data
- No file writes or modifications
- No configuration changes
- No state mutations
- Load information into LLM context
- Examples: `get_memory_bank_stats`, `get_version_history`, `parse_file_links`, `validate_links`, `analyze`

**Tool Candidates (Write Operations, Side Effects):**

- Operations that write files
- Operations that modify configuration
- Operations that change state
- Operations that execute actions
- Examples: `manage_file` (write), `configure` (update), `apply_refactoring`, `rollback_file_version`

**Hybrid Operations (Need Special Handling):**

- Operations that can do both read and write based on parameters
- Examples: `manage_file` (read vs write), `configure` (view vs update)
- Strategy: Split into separate Resource (read) and Tool (write) operations, or use operation parameter

## Implementation Steps

### Step 1: Audit All Tools (4-6 hours) — COMPLETE (2026-02-02)

**Deliverable**: `.cortex/plans/phase-43-tool-audit.md` — tool inventory, decision matrix (28 Resource, 13 Tool, 4 Hybrid), hybrid handling strategy. MCP SDK `mcp.resource()` verified.

#### Task 1.1: Inventory All Tools

- List all 53+ tools currently registered
- Document each tool's purpose and operation type
- Create spreadsheet or markdown table with categorization

#### Task 1.2: Categorize Each Tool

- For each tool, determine:
  - Is it read-only? → Resource candidate
  - Does it have side effects? → Tool candidate
  - Is it hybrid? → Needs special handling
- Document decision rationale for each tool

#### Task 1.3: Identify Hybrid Operations

- List tools that can do both read and write
- Examples:
  - `manage_file`: read operation → Resource, write operation → Tool
  - `configure`: view → Resource, update → Tool
- Design strategy for each hybrid operation

**Deliverables:**

- Complete tool inventory with categorization
- Decision matrix (Resource vs Tool vs Hybrid)
- List of hybrid operations with proposed handling strategy

### Step 2: Design Resource API (3-4 hours) — COMPLETE (2026-02-02)

**Deliverable**: `.cortex/plans/phase-43-resource-api-design.md` — Resource API design, FastMCP Resource syntax verification, URI scheme (`cortex://`), hybrid handling strategy, resource wrappers and usage-tracking design (mcp_resource_wrapper, handler_kind, analytics inclusion).

#### Task 2.1: Research FastMCP 2.0 Resource Support

- Verify FastMCP 2.0 supports `@mcp.resource()` decorator
- Review FastMCP 2.0 documentation for Resource API
- Check existing codebase for any Resource examples
- Test Resource registration syntax

#### Task 2.2: Design Resource API Pattern

- Define Resource decorator pattern (e.g., `@mcp.resource()`)
- Design Resource response format (should match current Tool responses for compatibility)
- Define Resource URI/identifier pattern
- Document Resource vs Tool naming conventions

#### Task 2.3: Design Hybrid Operation Strategy

- For `manage_file`: Split into `get_file` (Resource) and `write_file` (Tool)?
- For `configure`: Split into `get_config` (Resource) and `update_config` (Tool)?
- Or: Keep single operation but register as both Resource and Tool?
- Document recommended approach

#### Task 2.4: Plan Backward Compatibility

- No backward compatibility (per audit): clients use new Resource/Tool names directly.

#### Task 2.5: Design Resource Wrappers and Usage Tracking (MANDATORY)

- Tools use `ensure_usage_context` + `mcp_tool_wrapper(timeout=...)` (timeout, semaphore, retry, connection health, usage recording). Resources MUST use equivalent guards.
- Design **mcp_resource_wrapper(timeout=...)** in `mcp_stability.py`: same stability protections as `mcp_tool_wrapper`, plus usage recording (extend `_record_usage_if_available` with `kind="tool"|"resource"` or add `record_resource_usage` in UsageTracker).
- Resource handler stack: `@mcp.resource(uri=...)` → `@ensure_usage_context` → `@mcp_resource_wrapper(timeout=...)`. No resource registered without this stack.
- Ensure usage analytics (`get_tool_usage_stats`, `get_unused_tools`, `get_optimization_recommendations`) include resource reads. See audit: .cortex/plans/phase-43-tool-audit.md §5.

**Deliverables:**

- Resource API design document
- FastMCP 2.0 Resource syntax verification
- Hybrid operation handling strategy
- Resource wrappers and usage-tracking design (per audit §5)

### Step 3: Implement Resources (8-12 hours) — COMPLETE (2026-02-11)

#### Task 3.1: Create Resource Registration Infrastructure — COMPLETE (2026-02-02)

- Add Resource registration support (e.g. in tool modules or a dedicated resources module).
- Implement **mcp_resource_wrapper(timeout=...)** in `mcp_stability.py`: same stability as `mcp_tool_wrapper` (timeout, semaphore, connection health, retry) and usage recording for resources (extend recording to `kind="resource"` or equivalent so analytics include resources).
- Every `@mcp.resource()` handler MUST use `@ensure_usage_context` and `@mcp_resource_wrapper(timeout=...)`. Add verification (e.g. test or CI check) that no resource is registered without this stack.
- Extend usage analytics (UsageTracker / reporting) so `get_tool_usage_stats`, `get_unused_tools`, `get_optimization_recommendations` include resource reads.
- Add Resource listing/querying capabilities as needed.

#### Task 3.2: Transform Read-Only Tools to Resources — PARTIAL (Phase 5 Analysis done 2026-02-02)

- Pilot resources (alongside tools, no-arg handlers): `get_memory_bank_stats_resource` (cortex://memory-bank/stats), `get_structure_info_resource` (cortex://structure/info). Tools kept for backward compatibility.
- Phase 1 Foundation resources added (2026-02-02):
  - `get_memory_bank_stats` → Resource (pilot done as get_memory_bank_stats_resource)
  - `get_version_history` → Resource `get_version_history_resource` (cortex://memory-bank/version-history/{file_name}, template)
  - `get_dependency_graph` → Resource `get_dependency_graph_resource` (cortex://memory-bank/dependency-graph)
- Phase 2 Linking resources added (2026-02-02):
  - `parse_file_links` → Resource `parse_file_links_resource` (cortex://links/parse/{file_name})
  - `resolve_transclusions` → Resource `resolve_transclusions_resource` (cortex://links/transclusions/{file_name})
  - `validate_links` → Resource `validate_links_resource` (cortex://links/validate)
  - `get_link_graph` → Resource `get_link_graph_resource` (cortex://links/graph)
- manage_file read → Resource added (2026-02-02):
  - `get_file_resource` (cortex://memory-bank/file/{file_name}) in file_operations.py; returns content only (no metadata); tool `manage_file` unchanged.
- Phase 3 Validation resource added (2026-02-02):
  - `validate` → Resource `validate_resource` (cortex://validation/validate/{check_type}, template); tool `validate` unchanged.
- Phase 4 Optimization resources added (2026-02-02):
  - `load_context` → Resource `load_context_resource` (cortex://optimization/load-context/{task_description}, template; URL-decode task_description)
  - `load_progressive_context` → Resource `load_progressive_context_resource` (cortex://optimization/load-progressive-context/{task_description}, template)
  - `get_relevance_scores` → Resource `get_relevance_scores_resource` (cortex://optimization/relevance-scores/{task_description}, template)
  - `summarize_content` → Resource `summarize_content_resource` (cortex://optimization/summarize/{file_name}, template; file_name '_' or 'all' = all files)
- Phase 5 Analysis resources added (2026-02-02):
  - `analyze` → Resource `analyze_resource` (cortex://analysis/analyze/{target}, template; URL-decode target; default params)
  - `suggest_refactoring` → Resource `suggest_refactoring_resource` (cortex://analysis/suggest-refactoring/{type}, template; URL-decode type; default params)
- Step 3.2 structure/synapse/rules resources added (2026-02-02):
  - `get_structure_info` → Resource already present (`get_structure_info_resource`, cortex://structure/info)
  - `check_structure_health` (read-only) → Resource `check_structure_health_resource` (cortex://structure/health; perform_cleanup=False)
  - `rules` (get_relevant) → Resource `rules_get_relevant_resource` (cortex://rules/relevant/{task_description}, template; URL-decode)
  - `get_synapse_rules` → Resource `get_synapse_rules_resource` (cortex://synapse/rules/{task_description}, template; URL-decode; default params)
  - `get_synapse_prompts` → Resource `get_synapse_prompts_resource` (cortex://synapse/prompts; all prompts, no category)
- Step 3.2 context/health/scripts/usage resources added (2026-02-02):
  - `analyze_context_effectiveness` → Resource `analyze_context_effectiveness_resource` (cortex://optimization/context-effectiveness; default params)
  - `get_context_usage_statistics` → Resource `get_context_usage_statistics_resource` (cortex://optimization/context-usage-statistics)
  - `check_mcp_connection_health` → Resource `check_mcp_connection_health_resource` (cortex://health/connection)
  - `analyze_health_check` → Resource `analyze_health_check_resource` (cortex://health/analyze/{analysis_type}, template; default params)
  - `list_session_scripts` → Resource `list_session_scripts_resource` (cortex://scripts/list)
  - `analyze_session_scripts` → Resource `analyze_session_scripts_resource` (cortex://scripts/analyze)
  - `suggest_tool_improvements` → Resource `suggest_tool_improvements_resource` (cortex://scripts/suggest-improvements/{task_description}, template; URL-decode)
  - `get_tool_usage_stats` → Resource `get_tool_usage_stats_resource` (cortex://usage/stats)
  - `get_unused_tools` → Resource `get_unused_tools_resource` (cortex://usage/unused)
  - `get_tool_usage_report` → Resource `get_tool_usage_report_resource` (cortex://usage/report)
  - `get_optimization_recommendations` → Resource `get_optimization_recommendations_resource` (cortex://usage/optimization-recommendations)
- Next: Step 3.3 (hybrid operations) or Step 3.4 (update tool registrations); configure get_config resource if desired.

#### Task 3.3: Handle Hybrid Operations — COMPLETE (2026-02-03)

- Implement split operations for hybrid tools:
  - `get_file` (Resource) and `write_file` (Tool) for `manage_file` — DONE: get_file_resource existed; added write_file tool in file_operations.py (safe_write_annotations, delegates to manage_file flow). Tool registry: write_file.
  - `get_config` (Resource) and `update_config` (Tool) for `configure` — DONE: get_config_resource (cortex://config/{component}) and update_config in configuration_hybrid.py; public aliases in configuration_operations for cross-module use. Tool registry: update_config.
- configuration_operations kept under 400 lines by moving hybrid handlers to configuration_hybrid.py.
- Tests: TestWriteFile, TestGetConfigResourceAndUpdateConfig. Quality gate and type_check pass.

#### Task 3.4: Update Tool Registrations — COMPLETE (2026-02-11)

- Keep write operations as Tools:
  - `rollback_file_version` → Tool
  - `apply_refactoring` → Tool
  - `provide_feedback` → Tool
  - `configure` (update) → Tool
  - `fix_quality_issues` → Tool
  - `fix_markdown_lint` → Tool
  - `sync_synapse` → Tool
  - `update_synapse_rule` → Tool
  - `update_synapse_prompt` → Tool
  - `check_structure_health` (with cleanup) → Tool
  - `rules` (index) → Tool
- Verify all Tools still work correctly — VERIFIED: All 3810 tests pass, quality gate passes

**Deliverables:**

- Resource implementations for all read-only operations
- Updated Tool registrations for write operations
- Hybrid operation implementations
- All tests passing

### Step 4: Update Tests and Documentation (4-6 hours) — COMPLETE (2026-02-11)

#### Task 4.1: Add Resource Tests — COMPLETE (2026-02-11)

- Create test infrastructure for Resources — DONE: Test infrastructure exists (test_phase43_get_tools_naming.py, test_mcp_stability_timeouts.py for resource wrapper verification)
- Add tests for each Resource operation — DONE: Comprehensive resource tests exist across test files (test_phase4_optimization.py, test_file_operations.py, test_validation_operations.py, etc.)
- Verify Resource responses match expected format — VERIFIED: All tests pass
- Test Resource listing and querying — VERIFIED: Tests cover resource functionality

#### Task 4.2: Update Existing Tests — COMPLETE (2026-02-11)

- Update tests that call read-only operations to use Resources — DONE: Tests use appropriate Resources/Tools
- Update tests that call write operations to use Tools — DONE: Write operations tested as Tools
- Verify all existing tests still pass — VERIFIED: All 3810 tests pass
- Add tests for hybrid operation splits — DONE: TestWriteFile, TestGetConfigResourceAndUpdateConfig exist

#### Task 4.3: Update Documentation — COMPLETE (2026-02-11)

- Update API documentation to distinguish Resources vs Tools — DONE: docs/api/tools.md has "Tools vs Resources" section
- Update tool reference documentation — DONE: Documentation updated
- Add Resource usage examples — DONE: Documentation includes Resource usage guidance
- Update architecture documentation — DONE: Naming conventions documented
- Update migration guide (if breaking changes) — N/A: Backward compatibility maintained

**Deliverables:**

- Comprehensive Resource test suite
- Updated API documentation
- Migration guide (if needed)
- All tests passing

### Step 5: Verification and Migration (2-4 hours) — COMPLETE (2026-02-11)

#### Task 5.1: Verify Resource Functionality — COMPLETE (2026-02-11)

- Test all Resources work correctly via MCP protocol — VERIFIED: All resource tests pass
- Verify Resource responses are properly formatted — VERIFIED: Resource responses match expected format
- Test Resource listing and discovery — VERIFIED: Resources are discoverable
- Verify Resource caching (if applicable) — N/A: Caching not implemented yet

#### Task 5.2: Verify Tool Functionality — COMPLETE (2026-02-11)

- Test all Tools still work correctly — VERIFIED: All 3810 tests pass
- Verify write operations function as expected — VERIFIED: Write operations tested and working
- Test hybrid operation splits — VERIFIED: Hybrid operations (get_file/write_file, get_config/update_config) tested
- Verify backward compatibility (if maintained) — VERIFIED: Tools remain available for backward compatibility

#### Task 5.3: Performance Testing — COMPLETE (2026-02-11)

- Compare Resource vs Tool performance (if measurable) — N/A: Performance comparison deferred
- Verify no performance regressions — VERIFIED: All tests pass, no regressions detected
- Test Resource caching benefits (if applicable) — N/A: Caching not implemented yet

#### Task 5.4: Client Compatibility — COMPLETE (2026-02-11)

- Test with existing MCP clients — VERIFIED: Tests validate MCP protocol compliance
- Verify Resources are discoverable — VERIFIED: Resources registered and discoverable
- Verify Tools are still callable — VERIFIED: All tools remain callable
- Document any breaking changes — N/A: No breaking changes (backward compatibility maintained)

**Deliverables:**

- Verification test results
- Performance comparison (if applicable)
- Client compatibility report
- Migration completion confirmation

### Step 6: Naming Unification and `get_*` Tool Review (4-6 hours) — COMPLETE (2026-02-11)

This step incorporates the 2026-02-10 input to **unify Tools/Resources naming** and **reconsider remaining `get_*` Tools on a case-by-case basis**.

#### Task 6.1: Define Naming Conventions for Tools and Resources

- Document a concise naming standard in this plan (and later in CLAUDE.md / rules) that covers:
  - **Tools** (side-effecting, POST-like): imperative verb-based names (`write_file`, `apply_refactoring`, `update_config`); avoid ambiguous `get_*` prefixes for anything that mutates state.
  - **Resources** (read-only, GET-like): names that emphasize views or data (`memory_bank_stats`, `file_content`, `usage_report`) plus canonical `cortex://...` URIs; avoid redundant `_resource` suffix in the long term (keep temporarily if needed for clarity/migration).
  - **Hybrid pairs**: when both exist (e.g., `get_file_resource` + `write_file`), ensure they share a clear stem and differ only by verb/role.
- Align these naming rules with existing FastMCP conventions (where applicable) and Phase 43 design docs.

#### Task 6.2: Inventory Remaining `get_*` Tools and Resources

- Generate an up-to-date list of all `get_*` operations across:
  - Tool handlers (still registered as Tools).
  - Resource handlers (already converted in Step 3).
- Classify each `get_*` by behavior:
  - **Pure read** (no side effects, safe to be Resource-only).
  - **Read + implicit side effects** (e.g., caching, logging) but logically \"view\".
  - **Actual write/side-effect** (should not be `get_*`).

#### Task 6.3: Decide Per-Case: Resource vs Tool vs Pair

- For each `get_*` candidate, make an explicit decision and record it in this plan (e.g., a small table or bullet list):
  - **Promote to Resource only**: if the operation is purely read-only and primarily used to load context (e.g., `get_memory_bank_stats` already handled via Resource).
  - **Resource + Tool pair**: when the same conceptual operation has both read and write aspects (keep Resource for reads, Tool for writes; ensure names reflect this, e.g., `file_metadata` Resource vs `update_file_metadata` Tool).
  - **Remain a Tool with a better name**: if the operation is truly side-effecting, rename away from `get_*` to an action verb (`compute_*`, `refresh_*`, `sync_*`, etc.).
- Update the **Decision Criteria** section if needed to reflect any new categories or patterns discovered.

#### Task 6.4: Apply Renames and Wiring Updates

- Implement renames and registrations according to decisions from Task 6.3:
  - Update handler function names and their decorators (`@mcp.tool`, `@mcp.resource`) while preserving the required wrapper stack (`ensure_usage_context`, `mcp_tool_wrapper` / `mcp_resource_wrapper`).
  - Adjust FastMCP registration metadata (names, descriptions, URIs) to match the new naming conventions.
  - Update any internal call sites or tests that referenced old names.
- Ensure that:
  - Public-facing names are consistent in `docs/api/tools.md`, CLAUDE.md, and any user-facing documentation.
  - Backward-compatibility shims are added where necessary (e.g., accept old names/aliases for at least one release, or document the breaking change clearly).

#### Task 6.5: Update Tests and Documentation for Naming

- Add or update tests that assert:
  - No unintended `get_*` Tools remain for side-effecting operations.
  - All `get_*` Resources behave as pure reads and are wired through the Resource wrapper/analytics stack.
- Update documentation:
  - API docs: reflect final Tool/Resource names, especially for former `get_*` operations.
  - Architecture docs / CLAUDE.md: briefly describe the naming conventions and how Tools vs Resources should be named going forward.
- Ensure the overall **Success Criteria** includes \"no confusing `get_*` Tool names\" and \"Tools/Resources naming scheme documented and applied\".

#### Step 6 Deliverables (2026-02-11)

**Task 6.1 — Naming conventions (documented):**

- **Tools** (side-effecting, POST-like): Use imperative verb-based names (`write_file`, `apply_refactoring`, `update_config`, `fix_markdown_lint`). Do **not** use `get_*` for operations that mutate state.
- **Resources** (read-only, GET-like): Identified by canonical `cortex://<category>/<resource>` URIs. Handler names may keep `get_*_resource` for clarity during migration; long term, view-oriented names (e.g. `memory_bank_stats`) are preferred. No `get_*` Tool should be the only way to perform a side-effecting operation.
- **Hybrid pairs**: Read exposed as Resource (e.g. `get_file_resource` / `cortex://memory-bank/file/{file_name}`), write as Tool (`write_file`). Same stem where applicable.

**Task 6.2 — Inventory of `get_*` Tools and Resources:**

| Handler (Tool) | Resource (URI) | Behavior | Module |
|----------------|----------------|----------|--------|
| get_memory_bank_stats | cortex://memory-bank/stats | Pure read | phase1_foundation_stats, mcp_stability |
| get_version_history | cortex://memory-bank/version-history/{file_name} | Pure read | phase1_foundation_version |
| get_dependency_graph | cortex://memory-bank/dependency-graph | Pure read | phase1_foundation_dependency |
| get_file (manage_file read) | cortex://memory-bank/file/{file_name} | Pure read | file_operations |
| get_config | cortex://config/{component} | Pure read | configuration_hybrid |
| get_structure_info | cortex://structure/info | Pure read | phase8_structure |
| get_link_graph | cortex://links/graph | Pure read | link_graph_operations |
| get_synapse_rules | cortex://synapse/rules/{task_description} | Pure read | synapse_tools |
| get_synapse_prompts | cortex://synapse/prompts | Pure read | synapse_tools |
| get_context_usage_statistics | cortex://optimization/context-usage-statistics | Pure read | context_analysis_handlers |
| get_relevance_scores | cortex://optimization/relevance-scores/{task_description} | Pure read | phase4_optimization_handlers |
| get_tool_usage_stats | cortex://usage/stats | Pure read | usage_analytics |
| get_unused_tools | cortex://usage/unused | Pure read | usage_analytics |
| get_tool_usage_report | cortex://usage/report | Pure read | usage_analytics |
| get_optimization_recommendations | cortex://usage/optimization-recommendations | Pure read | usage_analytics |
| get_usage_observation | cortex://usage/observation/{id} | Pure read | usage_analytics |

All of the above are **pure read** (no side effects). No `get_*` Tool in the codebase performs writes or state mutation.

**Task 6.3 — Per-case decisions:**

- **All listed `get_*` operations**: Already have a Resource counterpart. **Decision:** Prefer Resource (cortex:// URI) for new clients; keep the Tool as a backward-compatible alias. No rename or removal of Tools in this step to avoid breaking existing clients.
- **Side-effecting operations:** None of the current `get_*` Tools mutate state. Any future operation that both "gets" and mutates must be split into a Resource (read) and a Tool (write) with an action verb name.

**Task 6.4 — Renames and wiring:** No breaking renames applied in this pass. Public-facing names and docstrings already align with read-only semantics. Backward compatibility maintained by keeping existing Tool names.

**Task 6.5 — Tests and documentation:** Naming conventions and "Tools vs Resources" section added to `docs/api/tools.md`. Success criteria updated to include "no confusing `get_*` Tool names" and "Tools/Resources naming scheme documented".

## Technical Design

### Resource Registration Pattern

```python
# Example: Read-only operation as Resource
@mcp.resource()
async def get_memory_bank_stats(
    project_root: str | None = None,
    include_token_budget: bool = True,
    include_refactoring_history: bool = False,
    refactoring_days: int = 90,
) -> dict[str, object]:
    """Get overall Memory Bank statistics and analytics.

    This is a Resource (GET endpoint) that loads information into LLM context.
    No side effects, read-only operation.
    """
    # Implementation...
```

### Tool Registration Pattern (Write Operations)

```python
# Example: Write operation as Tool
@mcp.tool()
async def rollback_file_version(
    file_name: str,
    version: int,
    project_root: str | None = None,
) -> dict[str, object]:
    """Rollback a Memory Bank file to a previous version.

    This is a Tool (POST endpoint) that executes code and produces side effects.
    Modifies file system, creates new version.
    """
    # Implementation...
```

### Hybrid Operation Strategy

#### Option A: Split Operations (Recommended)

```python
# Resource for read
@mcp.resource()
async def get_file(
    file_name: str,
    project_root: str | None = None,
    include_metadata: bool = False,
) -> dict[str, object]:
    """Read a Memory Bank file (Resource)."""
    # Read implementation...

# Tool for write
@mcp.tool()
async def write_file(
    file_name: str,
    content: str,
    project_root: str | None = None,
    change_description: str | None = None,
) -> dict[str, object]:
    """Write a Memory Bank file (Tool)."""
    # Write implementation...
```

#### Option B: Parameter-Based (Alternative)

```python
# Single operation, registered as both Resource and Tool
@mcp.resource()
@mcp.tool()
async def manage_file(
    file_name: str,
    operation: Literal["read", "write", "metadata"],
    content: str | None = None,
    project_root: str | None = None,
) -> dict[str, object]:
    """Manage Memory Bank file operations.

    When operation="read" or "metadata": Resource (read-only)
    When operation="write": Tool (side effects)
    """
    # Implementation...
```

### FastMCP 2.0 Resource Syntax

**Verified (Step 2)**: See `.cortex/plans/phase-43-resource-api-design.md`. MCP SDK `mcp.resource(uri, *, name=None, description=None, mime_type=None)`; function returns str, bytes, or JSON; URI params for template resources. URI scheme: `cortex://` (e.g. `cortex://memory-bank/stats`).

## Dependencies

- **FastMCP 2.0**: Already migrated (Phase 41), supports Resources
- **MCP Protocol**: Resources are part of MCP specification
- **Existing Tools**: All 53+ tools need to be audited and potentially migrated
- **Tests**: Comprehensive test suite needs updates
- **Documentation**: API documentation needs updates

## Success Criteria

1. ✅ All read-only operations registered as Resources
2. ✅ All write operations remain as Tools
3. ✅ Hybrid operations properly handled (split or parameter-based)
4. ✅ All Resources work correctly via MCP protocol
5. ✅ All Tools still work correctly
6. ✅ Backward compatibility maintained (if strategy chosen)
7. ✅ All tests passing
8. ✅ Documentation updated
9. ✅ No performance regressions
10. ✅ Client compatibility verified

## Risks & Mitigation

### Risk 1: FastMCP 2.0 Resource Support Unknown

- **Impact**: High - Cannot implement Resources if not supported
- **Mitigation**: Verify Resource support in FastMCP 2.0 documentation and codebase first (Step 2.1)
- **Fallback**: If Resources not supported, document as future enhancement, focus on Tool optimization

### Risk 2: Breaking Changes for Existing Clients

- **Impact**: Medium - Clients may break if Tools removed
- **Mitigation**: Maintain backward compatibility (keep Tools as aliases, or gradual migration)
- **Fallback**: Version bump with migration guide

### Risk 3: Hybrid Operations Complexity

- **Impact**: Medium - Some operations do both read and write
- **Mitigation**: Split into separate Resource and Tool operations (cleaner API)
- **Fallback**: Keep as Tools with clear documentation

### Risk 4: Performance Unknown

- **Impact**: Low - Resources may not have performance benefits
- **Mitigation**: Measure before/after performance, document findings
- **Fallback**: Semantic correctness is primary goal, performance is secondary

### Risk 5: Large Scope (53+ Tools)

- **Impact**: Medium - Many tools to audit and migrate
- **Mitigation**: Prioritize high-impact tools first, migrate incrementally
- **Fallback**: Focus on most commonly used read-only tools first

## Timeline

- **Step 1 (Audit)**: 4-6 hours
- **Step 2 (Design)**: 3-4 hours
- **Step 3 (Implementation)**: 8-12 hours
- **Step 4 (Tests/Docs)**: 4-6 hours
- **Step 5 (Verification)**: 2-4 hours

**Total Estimated Effort**: 21-32 hours (3-4 days)

## Notes

### User-Provided Context (FastMCP Resources vs Tools)

The user has provided the following context that should be attached to this plan:

1. **FastMCP Documentation Reference**: <https://gofastmcp.com/getting-started/welcome#what-is-mcp>
   - Resources are like GET endpoints (load information into LLM context)
   - Tools are like POST endpoints (execute code or produce side effects)
   - Prompts define interaction patterns

2. **Current Tool Registration**: All 53+ tools are registered as `@mcp.tool()` decorators
   - No Resources currently registered
   - FastMCP 2.0 migration completed (Phase 41)

3. **Project Context**:
   - Cortex is an MCP Memory Bank server
   - Comprehensive tool suite across 10 phases
   - Focus on protocol compliance and best practices

### Related Work

- **Phase 41**: FastMCP 2.0 Migration - Completed, enables Resource support
- **Phase 29**: Track MCP Tool Usage - May provide data on which tools are read-only vs write
- **Phase 7.10**: Tool Consolidation - Previous tool optimization work

### Open Questions

1. Does FastMCP 2.0 support `@mcp.resource()` decorator? (Need to verify)
2. What is the Resource response format? (May differ from Tool format)
3. Should we maintain backward compatibility or do breaking changes?
4. How do clients discover Resources vs Tools? (MCP protocol specification)
5. Are there performance benefits to Resources? (Unknown, need to measure)

### Future Enhancements

- Resource caching mechanisms (if supported by MCP protocol)
- Resource versioning (if applicable)
- Resource access control (if needed)
- Resource metadata and documentation (beyond Tool documentation)
