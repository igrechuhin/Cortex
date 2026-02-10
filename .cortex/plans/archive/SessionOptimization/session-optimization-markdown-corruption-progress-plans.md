# Session Optimization (2026-02-01): Markdown Corruption in Progress and Plans

**Status**: Pending  
**Source**: `.cortex/reviews/session-optimization-2026-02-01T11-55.md`  
**Created**: 2026-02-01

## Goal

Implement the four recommendations from the session optimization review (2026-02-01 11-55) to reduce markdown text corruption in `progress.md` and `.cortex/plans/*.md`: typos, broken identifiers (e.g. `helpert_manager_helper`, `_ntcore_managers`, `*create**`), and MD037 (no-space-in-emphasis) from unescaped underscores/asterisks. Existing guards apply only to `roadmap.md`; progress and plan files are not covered.

## Context

The review analyzed a commit session where:

- **Pattern 1**: Typos and broken identifiers appeared in `progress.md` and plan files (e.g. `helpert_manager_helper` → should be `_get_manager_helper`; `(add_*, *create**)` → should be `` (`add_*` and `_create_*`) ``; `_ntcore_managers` → should be `_init_core_managers`). MD037 (spaces inside emphasis) occurred when code identifiers with `_` or `*` were not wrapped in backticks.
- **Pattern 2**: Corruption guards (Phase 24 `fix_roadmap_content_if_needed`) run only for `roadmap.md` on `manage_file` write. Progress and plan files are not passed through any content-corruption guard. Markdown lint runs after write and catches MD037 but not typos or symbol corruption.
- **Pattern 3**: Synapse rule `markdown-formatting.mdc` lists MD009, MD012, MD022, MD031, MD032, MD036, MD029, MD024, MD040, MD059 but not **MD037**. Agents are not instructed to wrap code identifiers in backticks.

Root causes: (1) No preventive rule for code identifiers in markdown (MD037 + backticks). (2) Corruption guards are roadmap-only. (3) Typos (e.g. helpert, ntcore) are valid tokens and not caught by regex-based guards; prevention relies on prompt/rule guidance to verify symbols against the codebase.

## Approach

1. **Synapse rule**: Add MD037 and "code identifiers in backticks" to markdown-formatting rule so agents produce correct markdown for memory-bank and plan content.
2. **Code**: Extend corruption guard to `progress.md` in `manage_file` write path (reuse or share Phase 24 patterns).
3. **Prompts/agents**: Add "verify code symbols and use backticks" when writing progress/plans (memory-bank-updater, memory-bank-workflow, create-plan/implement/commit as appropriate).
4. **Optional**: Evaluate applying the same corruption fix to plan file content when written through a central path; implement or defer.

## Implementation Steps

### Step 1: Add MD037 and "Code Identifiers in Backticks" to Markdown-Formatting Rule (High)

- **Target**: `.cortex/synapse/rules/markdown/markdown-formatting.mdc` (or equivalent path under Synapse).
- **Change**: Add a section for **MD037 (no-space-in-emphasis)** and require that any code identifier (function, variable, or symbol name containing `_` or `*`) be written in inline code (backticks) in progress, plans, and memory-bank markdown. Include examples: `` `add_*` ``, `` `_create_*` ``, `` `_init_core_managers` ``, `` `_get_manager_helper` ``.
- **Placement**: Insert subsection "Code identifiers (MD037)" after "No Emphasis as Heading (MD036)"; list MD037 in the validation checklist and in "MANDATORY VALIDATION STEPS."
- **Expected impact**: Reduces MD037 lint failures and repeated fix cycles when documenting code in plans/progress.

### Step 2: Extend Corruption Guard to progress.md (High)

- **Target**: `src/cortex/tools/file_operations.py` (and optionally `roadmap_corruption.py` if patterns are shared).
- **Change**: When `manage_file` writes `progress.md`, run the same (or a subset of) corruption detection/fix used for `roadmap.md` (e.g. percent_to, number_actual, percent_coverage, files_unchanged, malformed_date). Reuse `fix_roadmap_content_if_needed` for progress if patterns are generic, or introduce `fix_memory_bank_content_if_needed(content, file_name)` that applies roadmap-like patterns for both `roadmap.md` and `progress.md`.
- **Implementation**: In file_operations write path, add `elif file_name == "progress.md": content = fix_roadmap_content_if_needed(content)` (or call shared helper). Add tests for progress.md corruption fix.
- **Expected impact**: Prevents the same phrase corruptions (e.g. "90.32coverage" → "90.32% coverage") from persisting in progress.md.

### Step 3: Prompt/Rule — Verify Code Symbols When Writing Progress/Plans (Medium)

- **Target**: `.cortex/synapse/agents/memory-bank-updater.md` and/or `.cortex/synapse/prompts/` (create-plan, implement, commit) and `.cortex/synapse/rules/general/memory-bank-workflow.mdc`.
- **Change**: Add an explicit step or rule: when writing progress.md or plan files that reference code (function names, helpers, module names), verify identifiers against the codebase (e.g. grep or read the relevant module) so names like `_get_manager_helper`, `_init_core_managers` are spelled correctly. Prefer backticks for all code identifiers.
- **Implementation**: One short paragraph in memory-bank-updater and memory-bank-workflow: "When documenting refactors or implementation steps, use correct code symbols; verify function/module names (e.g. `_get_manager_helper`, `_init_core_managers`) against the codebase and wrap them in backticks."
- **Expected impact**: Reduces typos such as "helpert_manager_helper" and "_ntcore_managers" that current guards cannot detect.

### Step 4: Consider Applying Corruption Fix to Plan Files (Low / Optional)

- **Target**: `src/cortex/tools/file_operations.py` (if plans are written via a single write path) or plan-creation/update flow.
- **Change**: If plan content is written through a path that can call a shared corruption fix, apply the same phrase patterns (percent_to, percent_coverage, etc.) to plan file content before save. Alternatively, document that plans are out of scope and rely on Step 1 and Step 3 only.
- **Expected impact**: Prevents phrase-level corruption in plans; may require care if plan format differs from roadmap/progress.
- **Implementation**: Only if plan writes go through a central helper; otherwise leave as future work.

## Dependencies

- **Phase 24 (Fix roadmap text corruption)**: COMPLETE. Reuse or share `fix_roadmap_content_if_needed` / `roadmap_corruption.py` patterns for progress.md (and optionally plans).
- **Synapse**: Rules and prompts live under `.cortex/synapse/` (or resolved Synapse directory); may be a submodule.

## Success Criteria

- MD037 and "code identifiers in backticks" are present in the markdown-formatting rule; agents can discover and follow them.
- `manage_file` write for `progress.md` runs the same (or shared) corruption fix as for `roadmap.md`; tests confirm progress.md phrase corruptions are fixed.
- Memory-bank-updater and memory-bank-workflow (and relevant prompts) contain explicit guidance to verify code symbols against the codebase and use backticks when writing progress/plans.
- Optional: Plan file writes use shared corruption fix where feasible, or scope is documented as out of scope.

## Testing Strategy

- **Coverage target**: Minimum 95% code coverage for all new or modified production code (e.g. progress.md branch in file_operations, any new helper in roadmap_corruption or shared module).
- **Unit tests**: (1) New or updated tests in `tests/tools/test_file_operations.py` (or equivalent) that assert when `manage_file(..., file_name="progress.md", operation="write", content=...)` is used, content is passed through the corruption fix and known patterns (e.g. "90.32coverage" → "90.32% coverage") are corrected. (2) If a shared `fix_memory_bank_content_if_needed(content, file_name)` is introduced, unit tests for it with inputs covering roadmap.md and progress.md.
- **Integration / rule verification**: (1) Grep/read Synapse markdown-formatting rule to confirm MD037 subsection and backtick requirement exist. (2) Grep/read memory-bank-updater and memory-bank-workflow to confirm "verify code symbols" and backticks guidance exist.
- **Regression**: Existing tests and pre-commit checks (format, type_check, quality, tests) must pass; no unintended change to roadmap.md-only behavior.
- **AAA pattern**: All tests MUST follow Arrange-Act-Assert. No blanket skips; any skip must have justification and linked ticket.
- **Pydantic v2 for JSON**: When testing MCP tool responses (e.g. `manage_file` write result), use Pydantic v2 `BaseModel` types and `model_validate_json()` / `model_validate()` where applicable per project standards.

## Risks & Mitigation

- **Rule overlap**: Markdown rule may already reference other MD* rules. Mitigation: add MD037 in the same style as existing entries and keep examples concise.
- **Progress vs roadmap format**: Progress.md structure may differ from roadmap; some Phase 24 patterns might be roadmap-specific. Mitigation: apply only generic phrase patterns to progress.md or parameterize by file_name and skip progress-inappropriate patterns.
- **Plan writes**: Plan files may be written outside `manage_file` (e.g. direct Write in create-plan flow). Mitigation: Document scope in plan; implement Step 4 only if a single write path exists and is safe to hook.

## Timeline

- Step 1: Single session (rule edit).
- Step 2: Single session (file_operations + roadmap_corruption reuse + tests).
- Step 3: Single session (prompt/agent/rule text).
- Step 4: Evaluate in same or follow-up session; implement or defer.

## Notes

- Review file: `.cortex/reviews/session-optimization-2026-02-01T11-55.md`. Agent transcript from the commit session that produced the review: referenced in plan request; mistakes (helpert_manager_helper, _ntcore_managers, MD037 in phase-20 plan) are documented in the review.
- Phase 24 plan: `.cortex/plans/archive/Phase24/phase-24-fix-roadmap-text-corruption.md`. Implementation is in `src/cortex/tools/roadmap_corruption.py` and `file_operations.py` (roadmap.md branch only).
- Path resolution: Use Cortex MCP `get_structure_info()` for Synapse/plans paths; do not hardcode `.cortex/` paths.
