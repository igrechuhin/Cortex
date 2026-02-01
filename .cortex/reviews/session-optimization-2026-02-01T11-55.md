# Session Optimization Analysis

## Summary

This session focused on commit pipeline execution and user-reported corrections. **Markdown text corruption** appeared multiple times in memory-bank and plan files (typos, broken identifiers, MD037 emphasis). Existing guards (markdown lint, Phase 24 roadmap corruption fix) did not prevent these issues: corruption affected **progress.md** and **plans/** while guards apply only to **roadmap.md** and markdown lint runs after the fact. Recommendations target Synapse rules and prompts so agents produce correct markdown and so guards cover progress/plans or catch more patterns.

## Mistake Patterns Identified

### Pattern 1: Markdown text corruption in progress and plans

- **Description**: Typos and broken identifiers in `progress.md` and `.cortex/plans/*.md` (e.g. `helpert_manager_helper`, `_ntcore_managers`, `*create**`, unescaped underscores causing MD037).
- **Examples**:
  - progress.md: "helpert_manager_helper" → should be "_get_manager_helper"
  - progress.md: "(add_*, *create**)" → should be "(`add_*` and `_create_*`)"
  - phase-20-code-review-fixes.md: "_ntcore_managers" → should be "_init_core_managers"
  - phase-20-code-review-fixes.md: MD037 (spaces inside emphasis) from identifiers like `add_*`, `_init_core_managers` written without backticks
- **Frequency**: Multiple instances in one session; user stated "text has got broken several times."
- **Impact**: High – wrong or misleading documentation, CI/IDE markdown lint failures (MD037), and confusion when reading plans/progress.

### Pattern 2: Guards do not cover all markdown that gets corrupted

- **Description**: Roadmap corruption fix runs only for `roadmap.md` on `manage_file` write. Progress and plan files are not passed through any content-corruption guard. Markdown lint runs after write (commit/IDE) and catches MD037 but not typos or symbol corruption.
- **Examples**:
  - Phase 24 `fix_roadmap_content_if_needed` is applied only when `file_name == "roadmap.md"` (file_operations.py).
  - progress.md and .cortex/plans/*.md are written without analogous corruption detection/fix.
  - Typos like "helpert_manager_helper" and "_ntcore_managers" are valid words/tokens and are not caught by regex-based corruption patterns.
- **Frequency**: Structural (guards are scoped to roadmap only).
- **Impact**: High – same classes of corruption (missing spaces, symbol runs, emphasis) can persist in progress and plans.

### Pattern 3: MD037 not covered by markdown-formatting rule

- **Description**: Synapse rule `markdown-formatting.mdc` lists MD009, MD012, MD022, MD031, MD032, MD036, MD029, MD024, MD040, MD059 but not **MD037** (no-space-in-emphasis). Agents are not instructed to avoid emphasis-style parsing for code identifiers (e.g. wrap `add_*`, `_create_*` in backticks).
- **Examples**: Phase-20 plan line 178 had multiple identifiers with underscores/asterisks; markdownlint reported MD037 until identifiers were wrapped in backticks.
- **Frequency**: Occurs whenever markdown content mentions code symbols containing `_` or `*`.
- **Impact**: Medium–high – causes lint failures and repeated fix cycles.

## Root Cause Analysis

### Cause 1: No preventive rule for code identifiers in markdown

- **Description**: Prompts and rules do not explicitly require wrapping code identifiers (function/variable names with `_` or `*`) in backticks when writing progress, plans, or memory-bank content.
- **Contributing factors**: Markdown-formatting rule focuses on structure (blank lines, headings, lists) and does not mention MD037 or inline code formatting for symbols.
- **Prevention opportunity**: Add MD037 to the markdown rule and a clear "wrap code identifiers in backticks" requirement for memory-bank and plan content.

### Cause 2: Corruption guards are roadmap-only

- **Description**: Phase 24 corruption patterns (percent_to, number_actual, ceeds, percent_coverage, files_unchanged, malformed_date, etc.) are applied only to `roadmap.md` in `manage_file`. Progress and plans can exhibit similar or other corruption (e.g. symbol runs like "*create**") but are not processed.
- **Contributing factors**: Implementation was scoped to roadmap.md; progress and plans were not in scope for the initial corruption fix.
- **Prevention opportunity**: Either extend corruption fix to progress.md (and optionally plans) or add prompt/rule guidance so agents avoid known corruption patterns when writing those files.

### Cause 3: Typos are not detectable by current guards

- **Description**: Typos that produce valid-looking tokens (e.g. "helpert", "ntcore") cannot be caught by regex-based corruption patterns. They rely on human or agent review.
- **Contributing factors**: No spell-check or identifier-consistency check (e.g. against codebase) for memory-bank/plan content.
- **Prevention opportunity**: Add prompt/rule guidance to "verify code symbols and helper names against the codebase when documenting refactors or steps" (e.g. `_get_manager_helper`, `_init_core_managers`) so agents self-check before writing.

## Optimization Recommendations

### Recommendation 1: Add MD037 and "code identifiers in backticks" to markdown-formatting rule

- **Priority**: High
- **Target**: `.cortex/synapse/rules/markdown/markdown-formatting.mdc`
- **Change**: Add a section for **MD037 (no-space-in-emphasis)** and require that any code identifier (function, variable, or symbol name containing `_` or `*`) be written in inline code (backticks) in progress, plans, and memory-bank markdown. Include examples: `add_*`, `_create_*`, `_init_core_managers`, `_get_manager_helper`.
- **Expected impact**: Reduces MD037 lint failures and repeated fix cycles when documenting code in plans/progress.
- **Implementation**: Insert new subsection "Code identifiers (MD037)" after "No Emphasis as Heading (MD036)"; list MD037 in the validation checklist and in "MANDATORY VALIDATION STEPS."

### Recommendation 2: Extend corruption guard to progress.md

- **Priority**: High
- **Target**: `src/cortex/tools/file_operations.py` (and optionally `roadmap_corruption.py` if patterns are shared)
- **Change**: When `manage_file` writes `progress.md`, run the same (or a subset of) corruption detection/fix used for roadmap.md (e.g. percent_to, number_actual, percent_coverage, files_unchanged, malformed_date). Reuse `fix_roadmap_content_if_needed` for progress if patterns are generic, or introduce `fix_memory_bank_content_if_needed(content, file_name)` that applies roadmap-like patterns for both roadmap.md and progress.md.
- **Expected impact**: Prevents the same phrase corruptions (e.g. "90.32coverage" → "90.32% coverage") from persisting in progress.md.
- **Implementation**: In file_operations write path, add `elif file_name == "progress.md": content = fix_roadmap_content_if_needed(content)` (or call a shared helper). Add tests for progress.md corruption fix.

### Recommendation 3: Prompt/rule: verify code symbols when writing progress/plans

- **Priority**: Medium
- **Target**: `.cortex/synapse/agents/memory-bank-updater.md` and/or `.cortex/synapse/prompts/` (create-plan, implement, commit) and `.cortex/synapse/rules/general/memory-bank-workflow.mdc`
- **Change**: Add an explicit step or rule: when writing progress.md or plan files that reference code (function names, helpers, module names), verify identifiers against the codebase (e.g. grep or read the relevant module) so names like `_get_manager_helper`, `_init_core_managers` are spelled correctly. Prefer backticks for all code identifiers.
- **Expected impact**: Reduces typos such as "helpert_manager_helper" and "_ntcore_managers" that current guards cannot detect.
- **Implementation**: One short paragraph in memory-bank-updater and memory-bank-workflow: "When documenting refactors or implementation steps, use correct code symbols; verify function/module names (e.g. `_get_manager_helper`, `_init_core_managers`) against the codebase and wrap them in backticks."

### Recommendation 4: Consider applying corruption fix to plan files (optional)

- **Priority**: Low
- **Target**: `src/cortex/tools/file_operations.py` (if plans are written via a single write path) or plan-creation/update flow
- **Change**: If plan content is written through a path that can call a shared corruption fix, apply the same phrase patterns (percent_to, percent_coverage, etc.) to plan file content before save. Alternatively, document that plans are out of scope and rely on Recommendation 1 and 3 only.
- **Expected impact**: Prevents phrase-level corruption in plans; may require care if plan format differs from roadmap/progress.
- **Implementation**: Only if plan writes go through a central helper; otherwise leave as future work.

## Implementation Plan

1. **Recommendation 1** – Update `.cortex/synapse/rules/markdown/markdown-formatting.mdc`: add MD037 and "code identifiers in backticks" for memory-bank and plan content. Quick, high impact.
2. **Recommendation 2** – Extend corruption fix to progress.md in file_operations and add tests. Medium effort, closes gap for progress.
3. **Recommendation 3** – Add "verify code symbols and use backticks" to memory-bank-updater and memory-bank-workflow. Low effort, reduces typos.
4. **Recommendation 4** – Evaluate whether plan writes can use the same corruption helper; implement or defer.

## Expected Impact

- **MD037 + backticks rule**: Fewer markdown lint failures and fewer rounds of "fix MD037" in plans/progress.
- **Progress.md corruption fix**: Same phrase corruptions that are fixed in roadmap will not persist in progress.
- **Verify code symbols**: Fewer identifier typos (helpert_manager_helper, _ntcore_managers) in documentation.

## Session Context (Fallback Signals)

- **analyze_context_effectiveness**: Returned `status: "no_data"` (no load_context in session); expected for commit/workflow-only sessions.
- **Primary signals used**: User report ("text has got broken several times"; "we have guards for that, but errors still passed"), conversation corrections (progress.md and phase-20 plan typos/MD037), memory-bank content (progress.md, activeContext.md), and codebase review (roadmap_corruption.py, file_operations.py, markdown-formatting.mdc).
