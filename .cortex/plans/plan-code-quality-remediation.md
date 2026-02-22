# Plan: Code Quality Remediation — File/Function Size & Type Safety

## Status: PLANNED

## Priority: P0 (Critical)

## Created: 2026-02-21

## Effort: 2–3 sprints

## Motivation

Comprehensive review (2026-02-21) found **systematic violations** of the project's own rules:

- **10+ files exceed the 400-line limit** (worst: `tools/models.py` at 3,091 lines)
- **24+ functions exceed the 30-line limit** (worst: `manage_file()` at 223 lines)
- **8 instances of `Any` type** (project rule: "NEVER use Any type")
- **20+ instances of `dict[str, object]`** instead of Pydantic models or `JsonDict`
- **10+ bare `# type: ignore` comments** masking real type issues

These violations create technical debt, hurt readability, and make onboarding harder.

---

## Step 1: Split Oversized Model Files

**Target files:**

| File | Current Lines | Action |
|------|--------------|--------|
| `tools/models.py` | 3,091 | Split into domain-specific model modules (context_models, validation_models, refactoring_models, session_models, evaluation_models) |
| `refactoring/models.py` | 1,855 | Split into operation-specific modules (consolidation_models, split_models, reorganization_models) |
| `core/models.py` | 1,279 | Split into enums, base_models, type_aliases |
| `optimization/models.py` | 904 | Split into config_models, result_models |

**Approach:**

1. Create new module files in same package
2. Move related model classes to appropriate files
3. Re-export from `__init__.py` to preserve public API
4. Update all imports across codebase
5. Verify no circular imports
6. Run full test suite

**Acceptance criteria:** All model files ≤ 400 lines. No import changes needed by consumers (re-exports maintain backward compatibility).

**Step 1 progress (2026-02-22):** Split `tools/models.py` into domain modules. Created `validation_result_models.py` (Validate*, link graph), `refactoring_result_models.py` (suggest_refactoring, apply_refactoring), `context_models.py` (load_context, configure, get_memory_bank_stats, version history, dependency graph, transclusions, progressive, relevance, summarize), and `analysis_models.py` (analyze usage/structure/insights). `models.py` now imports from `models_base`, `session_models`, and the new modules and re-exports for backward compatibility; file reduced from ~2900 to ~1600 lines. Remaining: further split or move remaining blocks (rollback, structure health, rules, roadmap ops, etc.) so `models.py` ≤ 400 lines; evaluation_models deferred (no evaluation-specific types in tools/models).

---

## Step 2: Refactor Oversized Functions

**Critical functions (>60 lines):**

| Function | File | Lines | Action |
|----------|------|-------|--------|
| `manage_file()` | `tools/file_operations.py` | 223 | Extract operation handlers: `_handle_create`, `_handle_update`, `_handle_delete`, `_handle_read`, `_handle_metadata` |
| `session_start()` | `tools/session_start_tools.py` | 72 | Extract: `_build_health_summary`, `_build_session_brief`, `_build_suggestions` |
| `_empty_error_counter()` | `tools/phase5_evaluation.py` | 65 | Extract counter initialization into declarative dict literal |

**Medium functions (31–60 lines) — 20+ instances:**

- `_handle_metadata_operation()`, `_close_section_and_add()`, `extract_sections()` in `file_operations.py`
- `_calculate_health_summary()`, `_create_session_brief()`, `_create_brief_with_suggestions()` in `session_start_tools.py`
- `analyze_results()`, `analyze_error_patterns()`, `run_tool_optimization_workflow()` in `phase5_evaluation.py`

**Approach:** For each function:

1. Identify logical blocks (each block becomes a helper)
2. Extract to private helpers with typed parameters/return
3. Keep original function as a thin dispatcher
4. Ensure each helper ≤ 30 logical lines
5. Add unit tests for extracted helpers

**Acceptance criteria:** All functions ≤ 30 logical lines. Test coverage maintained or improved.

---

## Step 3: Eliminate `Any` Type Usage

**Instances to fix:**

| File | Line(s) | Current | Fix |
|------|---------|---------|-----|
| `tools/file_operation_helpers.py` | 101, 127 | `schema_validator: Any` | Create `SchemaValidatorProtocol` with required methods |
| `tools/file_operation_helpers.py` | 134–137 | `fs_manager: Any`, etc. | Use existing typed protocols or `ManagersDict` |
| `tools/session_start_tools.py` | 668 | `**kwargs: Any` | Define explicit `TypedDict` for kwargs |
| `tools/phase5_evaluation.py` | 323–346 | `list[dict[str, Any]]` (8x) | Define Pydantic model for evaluation records |

**Approach:**

1. For manager types: use existing `Protocol` definitions or create new ones
2. For data structures: create Pydantic `BaseModel` subclasses
3. For kwargs: replace with explicit typed parameters or `TypedDict`
4. Run pyright in strict mode to verify

**Acceptance criteria:** Zero `Any` type usage. Pyright passes with no type-ignore comments needed.

---

## Step 4: Replace `dict[str, object]` with Typed Models

**20+ instances across:**

- `tools/session_start_tools.py` — manager dict access
- `tools/phase4_context_operations.py` — file maps
- `tools/refactoring_operations.py` — operation payloads
- `tools/health_check_operations.py` — health payloads

**Approach:**

1. For each `dict[str, object]` usage, identify the actual schema
2. Create a Pydantic model or use existing `JsonDict` alias
3. Replace dict construction with model instantiation
4. Update consumers to use typed attribute access

**Acceptance criteria:** Zero `dict[str, object]` patterns. All structured data uses Pydantic models.

---

## Step 5: Resolve Type-Ignore Comments

**10+ instances to address:**

- `tools/models.py:2980` — `type: ignore[reportUnknownVariableType]`
- `tools/phase1_foundation_stats.py:162,164` — `type: ignore[assignment]`
- `tools/phase4_metadata_helpers.py:140,187` — unknown types
- `tools/phase5_evaluation.py:19` — file-level pyright disable

**Approach:**

1. For each ignore comment, investigate the root type issue
2. Fix the underlying type problem (add concrete types, fix generics)
3. Remove the ignore comment
4. Verify pyright passes cleanly

**Acceptance criteria:** Zero `type: ignore` comments except where truly unavoidable (with documented justification).

---

## Step 6: Split Oversized Tool Files

**Target files (non-model):**

| File | Lines | Action |
|------|-------|--------|
| `tools/file_operations.py` | 1,110 | Split into `file_crud_operations.py`, `file_metadata_operations.py`, `file_section_operations.py` |
| `tools/session_start_tools.py` | 1,000 | Split into `session_start_tools.py` (main), `session_health.py`, `session_brief.py` |
| `tools/markdown_operations.py` | 933 | Split into `markdown_lint.py`, `markdown_format.py`, `markdown_section.py` |
| `tools/plan_operations.py` | 930 | Split into `plan_crud.py`, `plan_roadmap.py`, `plan_archive.py` |
| `core/metadata_index.py` | 993 | Split into `metadata_index.py`, `metadata_queries.py`, `metadata_cache.py` |

**Acceptance criteria:** All production files ≤ 400 lines.

---

## Verification

After all steps:

1. `pyright --strict` passes with zero errors
2. `black --check` passes
3. `ruff check` passes
4. Full test suite passes (4,357+ tests)
5. Coverage ≥ 91.85% (no regression)
6. No file > 400 lines, no function > 30 lines, no `Any` usage
