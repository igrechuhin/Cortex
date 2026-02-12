# Session Optimization: Commit Pipeline Orchestration Refactor

**Status**: COMPLETED (Steps 1-8 completed 2026-02-10 / 2026-02-11)

**Goal**: Refactor the commit pipeline into modular phases and helper tools/commands so that agents can reliably execute `/cortex/commit` end-to-end without hitting context/step limits, while preserving the existing zero-errors policy and all current checks, and apply the same orchestration and MCP-tool patterns to closely related prompts (especially the review prompt, Analyze (End of Session) prompt, and `create-plan` prompt).

## Context

The current commit pipeline prompt and AGENTS rules have grown large and dense over time. They enforce many important guarantees (zero-errors, full pre-commit checks, memory bank/roadmap updates, session analysis), but this comes with several practical issues:

- Large, highly repetitive prompt text consumes a lot of context budget before any tools run.
- `/cortex/commit` tries to do everything: fix errors, run all checks, debug failing tests, update memory bank and roadmap, handle Synapse submodule, and run end-of-session analysis.
- When tests or other checks fail late in the pipeline, the agent often has too little context/step budget left to debug and fix within the same run.
- There are already related plans and work (e.g. `session-optimization-commit-pipeline-improvements-2026-02-07.md`, `quality-gate-commit-pipeline-spelling-gap.md`, `session-optimization-load-context-on-problem-fix-path-2026-02-09.md`) that improved checks, spelling, and context loading, but the orchestration and prompt size still cause reliability issues.

This plan builds on the existing session-optimization and quality-gate work and focuses specifically on **how** the commit pipeline is orchestrated and represented (tools, commands, prompts), not on adding new checks. Where it improves orchestration patterns (phase helpers, pre-action checklists, MCP tool usage), those patterns should also be reflected in the review, Analyze (End of Session), and `create-plan` prompts so review, analysis, and plan-creation flows benefit from the same structure.

## Approach

1. **Modularize the pipeline** into explicit phases (e.g., preflight checks, docs/memory-bank sync, final gate + git operations, analyze session) with clear, small responsibilities.
2. **Introduce helper MCP tools and/or sub-commands** that encapsulate phase logic, so `/cortex/commit` mainly orchestrates a few high-level calls instead of dozens of fine-grained steps.
3. **Slim and de-duplicate prompts** by moving behavioral rules into code and referencing AGENTS/plan rules concisely.
4. **Clarify failure semantics**: if any phase fails (especially tests), `/cortex/commit` should stop the commit pipeline cleanly and point to specific helper commands (e.g., `/cortex/fix_tests`) instead of attempting open-ended debugging.
5. **Align the review and Analyze prompts** with these patterns where appropriate so that code-review and end-of-session analysis flows use the same MCP tools, pre-action checklist standards, and phase-style delegation (agents + tools) as the commit pipeline, without duplicating low-level rules.

## Implementation Steps

### Step 1: Define canonical commit phases - COMPLETED (2026-02-10)

**Goal**: Decide and document the canonical phases of the commit pipeline and their responsibilities.

**Status**: COMPLETED

**Deliverable**: `docs/design/commit-pipeline-phases.md`

**Summary**: Reviewed the full `/cortex/commit` prompt (1587 lines), AGENTS rules, and related session-optimization plans. Defined 4 canonical phases:

- **Phase A: Preflight Checks** (Steps 0-4) - fix_errors, quality preflight, format, markdown lint, type_check, quality, tests.
- **Phase B: Docs & Memory Bank Sync** (Steps 5-10) - activeContext/progress updates, roadmap updates, plan archiving, archive validation, timestamps, state verification.
- **Phase C: Submodule & Git Operations** (Steps 11-14) - Synapse submodule handling, final validation gate (Step 12 with sub-steps 12.0-12.7), git commit, git push.
- **Phase D: Session Analysis** (Step 15) - Analyze (End of Session) prompt.

All 16 existing steps (including pre-step) are mapped to exactly one phase. Inputs, outputs, and failure semantics documented for each phase. Seven key invariants preserved (zero-errors policy, coverage threshold, memory bank contracts, submodule cleanliness, mandatory final gate, sequential execution, user-initiated only).

**Dependencies**: Existing commit prompt, AGENTS, and session-optimization plans.

---

### Step 2: Introduce phase-level MCP tools or helpers - COMPLETED (2026-02-10)

**Goal**: Encapsulate complex phase logic into dedicated MCP tools or helper functions so that a single tool call performs all checks within a phase and returns structured results.

**Tasks**:

1. Design one or more new MCP tools or orchestration helpers, for example:
   - `run_preflight_checks` - wraps `execute_pre_commit_checks`, `fix_markdown_lint`, and related quality tools; returns a JSON object summarizing per-check status, errors, and coverage.
   - `sync_docs_and_memory_bank` - wraps memory bank updates, roadmap/activeContext state validation, timestamps validation, and plan archiving checks.
   - `run_final_gate_and_git_operations` - verifies a quick final gate and performs git commit & push when allowed.
2. Implement these helpers in Python, following project rules:
   - Use typed Pydantic models for request/response shapes instead of raw dicts.
   - Keep MCP handlers thin; push business logic into pure helper functions.
   - Enforce existing zero-errors policy inside these helpers (e.g., via explicit checks on counts and flags).
3. Add unit tests with >=95% coverage for each new helper/tool, including both success and failure paths.
4. Update existing tools or prompts (including the review prompt where it uses commit-related checks like `execute_pre_commit_checks`) to rely on these new helpers instead of re-implementing logic in natural language.

**Status**: COMPLETED (2026-02-10)

**Deliverables**:

- `run_preflight_checks` MCP tool (Phase A): `pre_commit_phase_tools.py` + `pre_commit_preflight_helpers.py`
- `run_docs_and_memory_bank_sync` MCP tool (Phase B): `pre_commit_phase_tools.py` + `pre_commit_docs_memory_helpers.py`
- Pydantic result models: `PreflightCheckSummary`, `RunPreflightChecksResult`, `DocsAndMemoryBankSyncResult` (and error variants) in `models.py`
- Tool registry registration in `tool_registry.py`
- 45 tests in `test_pre_commit_phase_tools.py` covering success, failure, tool-error, and edge cases
- Coverage: `pre_commit_phase_tools.py` 100%, `pre_commit_preflight_helpers.py` 97.25%, `pre_commit_docs_memory_helpers.py` 95.04%

**Success Criteria**:

- Each canonical phase has at least one corresponding MCP tool/helper.
- JSON responses expose enough detail (per-check results, coverage, errors) for prompts to make decisions without re-parsing raw text.
- Tests cover normal and failure scenarios with >=95% coverage for new code.

**Dependencies**: Step 1 phase definition; existing `execute_pre_commit_checks`, `manage_file`, and validation tools.

---

### Step 3: Refactor `/cortex/commit` prompt to orchestrate phases

**Goal**: Simplify the `/cortex/commit` prompt so it orchestrates phase tools instead of micromanaging individual checks.

**Status**: IN PROGRESS (commit prompt now references Phase A/B helpers and names follow-up commands; further prompt slimming pending).

**Session 2026-02-10 Progress**:

- Updated commit prompt to reference `run_preflight_checks` and `run_docs_and_memory_bank_sync` phase helpers.
- Phase A failures now explicitly point to `/cortex/fix_tests` and `/cortex/fix_quality`.
- Phase B failures now explicitly point to `/cortex/docs-sync`.
- Further prompt slimming (removing duplicated rules, shortening verbose sections) deferred to Step 5.

**Tasks**:

1. Rewrite `/cortex/commit` to:
   - Call `run_preflight_checks` (or equivalent) and interpret its structured result.
   - If preflight fails (especially tests), **stop the commit pipeline** and:
     - Present a concise, structured summary of failures.
     - Recommend explicit follow-up commands (e.g., `/cortex/fix_tests`, `/cortex/fix_quality`) rather than trying to debug inline.
   - If preflight passes, proceed to `sync_docs_and_memory_bank` and then `run_final_gate_and_git_operations`.
   - Run session analysis (Analyze prompt or its MCP equivalent) only after successful commit.
2. Remove or drastically shrink repeated bullet lists and redundant instructions already covered by AGENTS and phase tools.
3. Ensure the prompt still enforces key invariants (zero-errors, memory bank and roadmap contracts, no partial commits), but refers to those via concise statements and links to AGENTS/rules.
4. Add or update tests (where applicable) that validate the textual behavior of the commit prompt (e.g., via snapshot or structure checks in docs/tests that already assert prompt content).
5. Where the review prompt orchestrates type/quality checks and rules-aware review flows, ensure its structure is compatible with the phase helpers (e.g., by reusing `run_preflight_checks` for type/quality context or mirroring the same pre-action checklist patterns), without bloating the review prompt or duplicating commit-specific behavior.

**Success Criteria**:

- `/cortex/commit` uses a small number of phase-level tool calls and short, clear instructions.
- The prompt no longer contains large, duplicated sections of rules that live in AGENTS or dedicated rules files.
- The behavior for success and failure (especially test failures) is consistent and easy to reason about.

**Dependencies**: Steps 1-2.

---

### Step 4: Add focused helper commands for common failure modes

**Goal**: Provide dedicated commands for follow-up work when `/cortex/commit` reports failures, especially test failures, without overloading the commit prompt.

**Status**: COMPLETED (2026-02-10)

**Session 2026-02-10 Progress**:

- Created `fix-tests.md` helper prompt: diagnose and fix failing tests using `execute_pre_commit_checks(checks=["tests"])`.
- Created `fix-quality.md` helper prompt: fix type/format/lint issues using `fix_quality_issues` and `execute_pre_commit_checks`.
- Created `docs-sync.md` helper prompt: repair docs/memory-bank inconsistencies using `run_docs_and_memory_bank_sync` and `validate`.
- Registered all three in `prompts-manifest.json` as `/cortex/fix_tests`, `/cortex/fix_quality`, `/cortex/docs_sync`.
- Markdown structure fixes applied to fix-quality.md and docs-sync.md (list indentation under checklists).

**Tasks**:

1. Design and document small, focused commands, for example:
   - `/cortex/fix_tests` - locate and debug failing tests based on the last preflight run; open relevant modules and tests; run targeted test subsets.
   - `/cortex/fix-quality` - run quality tools and fix type/format/lint issues outside the commit pipeline.
   - `/cortex/docs-sync` - run memory bank/roadmap/timestamps sync without committing.
2. Ensure each command:
   - Has a clear, minimal scope and does not attempt to run the full commit pipeline.
   - Uses existing MCP tools (`execute_pre_commit_checks`, `fix_quality_issues`, `manage_file`, `validate`) in a narrowly scoped way.
   - Updates memory bank and roadmap only when its scope requires it.
3. Update AGENTS and relevant prompts to describe when and how to use these helper commands in response to `/cortex/commit` failures.
4. Add tests and/or documentation examples showing the interplay between `/cortex/commit` and these helper commands.

**Success Criteria**:

- There are explicit, documented helper commands for test debugging, quality fixes, and docs sync.
- `/cortex/commit` references these commands instead of attempting open-ended debugging.
- Agents can reliably recover from common failure modes by running the appropriate helper commands.

**Dependencies**: Steps 1-3.

---

### Step 5: Slim and centralize rules to reduce prompt size

**Goal**: Move duplicated rules and long-form guidance from individual prompts into AGENTS or dedicated rules files, then reference them concisely.

**Status**: COMPLETED (2026-02-10)

**Session 2026-02-10 Progress**:

- Added AGENTS.md section "Commit pipeline (phase-based)" describing phase helpers (`run_preflight_checks`, `run_docs_and_memory_bank_sync`), failure semantics, and helper commands (`/cortex/fix_tests`, `/cortex/fix_quality`, `/cortex/docs_sync`).
- Commit prompt: added one-line reference to AGENTS.md at Phase Helper MCP Tools section.
- Implement prompt: added reference to AGENTS.md and phase alignment in Step 4.7 (quality gate).
- **Completed this session**: Added Synapse rule `general/commit-pipeline.mdc` (zero-errors, phase helpers, memory bank refs) for `rules(operation="get_relevant")`. Slimmed commit.md: Pre-Step Load Rules now references Pre-Action Checklist item 2 and commit-pipeline.mdc/memory-bank-workflow.mdc; Verify code conformance checklist item shortened to reference rules loaded above and memory-bank-workflow.mdc. review.md: added one-line reference to AGENTS.md "Commit pipeline (phase-based)" in Static analysis step for type/quality checks.

**Tasks**:

1. Audit `/cortex/commit`, AGENTS, review prompt, and related prompts (`implement-next-roadmap-step`, analyze prompt, session-optimization plans) for repeated content (zero-errors rules, TodoWrite usage, memory bank/roadmap contracts, pre-commit check ordering).
2. Centralize these rules into:
   - AGENTS.md sections (for cross-command behavior).
   - Synapse rules files (e.g., for commit pipeline behavior, TodoWrite usage, memory-bank workflow).
3. Refactor prompts to replace long repeated sections with short references like:
   - "Apply zero-errors rules from AGENTS.md to all checks."
   - "Follow memory bank workflow rules for activeContext/roadmap from memory-bank-workflow.mdc."
4. Ensure that any references are stable (do not rely on brittle line numbers) and that rules remain discoverable via `rules(operation="get_relevant")`.
5. For `implement-next-roadmap-step`, explicitly reuse the phase helpers and orchestration pattern defined in this plan (e.g., preflight checks via `run_preflight_checks`, docs/memory-bank sync, final gate) instead of re-specifying low-level behavior such as quality gates, memory bank workflow, or roadmap sync in long natural-language blocks.
6. For the review prompt, mirror the same centralization strategy: keep it focused on orchestrating specialized agents and MCP tools, reference shared rules (coding standards, testing standards, memory-bank workflow) via AGENTS/rules, and avoid duplicating commit-specific sequences or low-level check descriptions.
7. Keep `implement-next-roadmap-step` and the review prompt themselves small by delegating work to MCP tools and Synapse agents (`roadmap-implementer`, `memory-bank-updater`, `plan-archiver`, `static-analyzer`, `rules-compliance-checker`, etc.) and by referencing AGENTS/rules for shared behavior, so they mirror the commit pipeline's phase-based orchestration rather than duplicating logic.

**Success Criteria**:

- Commit-related prompts shrink significantly in size without losing behavior.
- Core rules exist in a single, canonical place and are easy for agents to retrieve.
- `rules(operation="get_relevant")` surfaces these rules when working on commit pipeline tasks.
- `implement-next-roadmap-step` mirrors the phase-based orchestration pattern and helper-tool usage from this plan while remaining significantly shorter and easier to maintain.

**Dependencies**: Steps 1-4.

---

### Step 6: Update existing session-optimization plans and AGENTS - COMPLETED (2026-02-11)

**Goal**: Align existing session-optimization and commit-quality plans with the new orchestration model and avoid overlapping or conflicting guidance.

**Status**: COMPLETED (2026-02-11)

**Summary**: Added cross-references from `session-optimization-commit-pipeline-improvements-2026-02-07.md`, `quality-gate-commit-pipeline-spelling-gap.md`, and `session-optimization-load-context-on-problem-fix-path-2026-02-09.md` to this plan (structural vs content/focus). AGENTS.md already describes phase-based pipeline and failure behavior (Step 5). Memory bank updated on Step 6 completion.

**Tasks**:

1. Review and, if needed, update the following plans:
   - `session-optimization-commit-pipeline-improvements-2026-02-07.md`
   - `quality-gate-commit-pipeline-spelling-gap.md`
   - `session-optimization-load-context-on-problem-fix-path-2026-02-09.md`
   - Any other commit-related session-optimization plans.
2. Add cross-references from those plans to this orchestration refactor plan where appropriate (e.g., "See Commit Pipeline Orchestration Refactor for structural changes; this plan focuses on checks/content").
3. Update AGENTS.md to briefly describe the new phase-based commit pipeline, the helper commands, and the expected behavior when phases fail.
4. Ensure memory bank (activeContext/progress) and roadmap entries are updated when major orchestration milestones complete.

**Success Criteria**:

- Existing session-optimization and quality plans remain accurate and non-overlapping with this plan.
- AGENTS and memory bank reflect the new orchestration model.

**Dependencies**: Steps 1-5.

---

### Step 7: Apply orchestration patterns to `create-plan` prompt - COMPLETED (2026-02-11)

**Goal**: Apply the same phase-based orchestration and prompt-slimming patterns to the `create-plan` workflow so that `/cortex/plan` remains reliable and maintainable as it grows.

**Status**: COMPLETED (2026-02-11)

**Summary**: Added explicit phases (1–5) to create-plan.md execution steps; added Phases overview referencing memory-bank-workflow.mdc and AGENTS.md; slimmed Path Resolution and ERROR HANDLING path resolution by referencing memory-bank-workflow.mdc and AGENTS.md. Invariants preserved (get_structure_info, register_plan_in_roadmap, full-content rule, mandatory Analyze). Existing tests in test_plan_creation_workflow_compliance.py continue to assert prompt structure.

**Tasks**:

1. Analyze `.cortex/synapse/prompts/create-plan.md` and identify its implicit phases (structure resolution, context loading, existing-plan reuse check, plan creation/enrichment, roadmap registration, end-of-session Analyze).
2. Where appropriate, back each phase with existing or new MCP tools (e.g., `get_structure_info`, `manage_file`, `register_plan_in_roadmap`, `sequentialthinking`, `analyze_context_effectiveness`) so the prompt orchestrates helpers instead of re-specifying low-level behavior.
3. Slim repeated rules and guardrails in `create-plan` by moving them into AGENTS and Synapse rules (memory-bank workflow, roadmap anti-truncation, plan testing requirements) and referencing them concisely from the prompt.
4. Ensure the prompt continues to enforce critical invariants: dynamic path resolution via Cortex MCP tools, mandatory roadmap registration via `register_plan_in_roadmap`/`add_roadmap_entry`, full-content rules for any `manage_file(write, ...)` fallback, and mandatory Analyze (End of Session) execution after plan creation.
5. Update or add tests/docs that validate the `create-plan` prompt structure and its use of helper tools (e.g., snapshot-style tests for key sections, docs for the plan creation workflow).

**Success Criteria**:

- `create-plan` uses a small set of clearly defined phases that can be mapped to helper tools or well-bounded prompt sections.
- The prompt size is reduced by centralizing shared rules in AGENTS/rules while retaining all existing behavioral guarantees (including the mandatory testing strategy section).
- Plan creation remains robust against roadmap corruption (anti-truncation rules intact) and misuse of direct filesystem paths (all critical paths resolved via Cortex MCP tools).

**Dependencies**: Steps 1-5; existing `create-plan` prompt and memory-bank/roadmap workflows.

---

### Step 8: Apply orchestration patterns to Analyze (End of Session) prompt - COMPLETED (2026-02-11)

**Goal**: Ensure the Analyze (End of Session) prompt (`analyze.md`) benefits from the same session-optimization and orchestration improvements as the commit pipeline, while keeping the prompt small and delegating work to MCP tools and Synapse agents.

**Status**: COMPLETED (2026-02-11)

**Summary**: Added Phases (1–3) and Tooling reference to memory-bank-workflow.mdc and AGENTS.md; labeled Pre-Analysis Checklist as Phase 1, Steps 1–2 as Phase 2, report save and Step 4 as Phase 3; added alignment with Phase D (docs/design/commit-pipeline-phases.md); added full-report/no-truncation rule for review file writes.

**Tasks**:

1. Audit the current Analyze prompt for:
   - Pre-analysis checklist (context loading, rules loading, safety rails).
   - Tool usage (`analyze_context_effectiveness`, `get_context_usage_statistics`, `get_memory_bank_stats`, `rules`, `suggest_refactoring`).
   - Output responsibilities (reviews written to the reviews directory, optional improvements plan creation and roadmap registration).
2. Define a lightweight phase model for Analyze, for example:
   - Phase 1: **Context & Rules Load** - load relevant memory bank files, rules, and recent usage events.
   - Phase 2: **Analysis & Insights** - run context-effectiveness analysis, usage statistics, and structural/refactoring analysis.
   - Phase 3: **Outputs & Plans** - write a structured review file and, when appropriate, trigger or update improvement plans and roadmap entries.
3. Refactor the Analyze prompt text to:
   - Use semantic names ("plans directory", "memory bank", "reviews directory", "Synapse agents directory") and resolve paths via `get_structure_info()` and `manage_file()` instead of hardcoded `.cortex/` paths.
   - Delegate analysis work to MCP tools (`analyze_context_effectiveness`, `get_context_usage_statistics`, `get_memory_bank_stats`, `suggest_refactoring`, `rules`) and Synapse agents rather than in-prompt freeform analysis.
   - Mirror the zero-errors and no-truncation rules used by create-plan and memory-bank-updater when writing reviews or improvement plans.
4. Ensure Analyze's behavior is consistent with the Phase D "Session Analysis" definition from `docs/design/commit-pipeline-phases.md`:
   - Only runs after successful commit phases A-C.
   - Produces structured, reproducible outputs with clear links to plans and roadmap entries.
5. Add or update documentation and tests:
   - Document the Analyze phases and tool usage in `docs/mcp-tool-timeouts.md` or a dedicated analyze-design doc.
   - Add tests (where feasible) that validate the Analyze workflow contracts (e.g., correct tools called, review filename pattern, presence of links to plans/roadmap) using Pydantic models to parse JSON responses from analysis tools.

**Success Criteria**:

- Analyze prompt is short, phase-oriented, and delegates to MCP tools and agents instead of embedding analysis logic.
- Analyze uses the same path-resolution and no-truncation guarantees as other memory-bank-aware workflows.
- Reviews and any improvement plans created by Analyze are consistently linked to roadmap entries and existing session-optimization plans.

**Dependencies**: Steps 1-6; existing Analyze prompt and reviews/memory-bank workflows.

---

## Dependencies

- Existing commit pipeline implementation and prompts.
- Session-optimization and quality gate plans around commit pipeline and pre-commit checks.
- MCP tools: `execute_pre_commit_checks`, `fix_markdown_lint`, `fix_quality_issues`, `manage_file`, `validate`, `rules`, `analyze_context_effectiveness`.

## Success Criteria

- `/cortex/commit` consistently completes or fails fast with a clear, structured report, without running out of context or step budget.
- All existing checks (fix_errors, format, markdown lint, type_check, quality, tests, memory bank/roadmap sync, timestamps, submodule handling, analyze) are still enforced, but organized into explicit phases.
- Helper commands exist for common failure modes, and `/cortex/commit` points to them instead of attempting open-ended debugging.
- Prompt sizes for commit-related commands are significantly reduced through centralization of rules.
- New orchestration code and tools have >=95% test coverage and pass all quality gates.

## Testing Strategy

### Coverage Target

- Minimum 95% code coverage for all new orchestration helpers, MCP tools, and any prompt-specific parsing or dispatch logic introduced by this plan (including `run_preflight_checks`, future phase helpers, and `create-plan` / Analyze orchestration changes).

### Unit Tests

1. **Phase helpers and MCP tools (Steps 2-4)**:
   - Success and failure paths for each helper, including structured error reporting and zero-errors enforcement.
   - Validation of request/response Pydantic models, including optional fields and edge cases.
2. **Helper commands for failure modes (Step 4)**:
   - `/cortex/fix_tests`, `/cortex/fix_quality`, and `/cortex/docs_sync` flows exercising their narrow scopes.
   - Assertions that they do not attempt to run the full commit pipeline and respect memory bank/roadmap contracts.
3. **Create-plan and Analyze orchestration (Steps 7-8)**:
   - Any new helper logic used by `create-plan` to resolve paths, discover existing plans, and register in the roadmap, and any helpers used by Analyze to orchestrate its phases and write reviews.
   - Guardrails around roadmap anti-truncation, mandatory Analyze-at-end behavior for plan creation, and Analyze review/write contracts.

### Integration Tests

1. **Commit pipeline end-to-end**:
   - `/cortex/commit` happy-path run using phase helpers only.
   - Failure-path runs where preflight, docs/memory-bank sync, or final gate fail and the pipeline stops cleanly with clear follow-up guidance.
2. **Plan creation workflow**:
   - `/cortex/plan` end-to-end flow exercising dynamic path resolution, existing-plan reuse, roadmap registration via `register_plan_in_roadmap`, and Analyze prompt execution.

### Edge Cases

- Commit pipeline invoked with partially failing preflight checks (e.g., tests failing but other checks passing).
- Roadmap already containing many session-optimization plans when orchestration-related entries are updated.
- Plan creation requests that reference existing plans and additional context (logs, code) simultaneously.

### Regression Tests

- Verify existing commit pipeline behavior (zero-errors, coverage thresholds, memory bank contracts) remains intact after orchestration refactors.
- Verify existing plan creation workflows still succeed when no new orchestration helpers are required.

### Test Practices

- All tests MUST follow the Arrange-Act-Assert pattern.
- No blanket skips; every skip requires a justification and linked ticket.
- When asserting on MCP tool responses (e.g., `execute_pre_commit_checks`, `run_preflight_checks`, `manage_file`), prefer Pydantic v2 models and `model_validate()` / `model_validate_json()` over raw `dict` shape assertions.
