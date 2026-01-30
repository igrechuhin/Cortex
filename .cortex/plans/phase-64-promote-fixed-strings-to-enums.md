# Phase 64: Promote Fixed String Sets to Enums

**Status:** Planning  
**Created:** 2026-01-29

## Goal

Replace all identified fixed string sets (currently `Literal[...]` or raw strings) with `str`-subclassed enums across the codebase. This ensures only valid values are used at type-check time, avoids typos, and aligns with the existing pattern established by `PreCommitCheck` in pre-commit tools.

## Context

A codebase scan identified multiple places where a closed set of string values is used for parameters, branching, or model fields. These are currently expressed as:

- `Literal["a", "b", "c"]` type aliases (e.g. `CheckType`, `StubAdapterLanguage`)
- Raw string literals in `if x == "value"` branches
- Pydantic `Field(..., Literal["success", "error"])` etc.

The pre-commit tools already use `PreCommitCheck(str, Enum)` successfully. Extending this pattern everywhere improves type safety and consistency.

## Scope

**In scope:**

- Tool parameters: operation/action/type/target/check_type where the set is fixed.
- Internal branching and validation that compares against fixed string sets.
- Shared model fields (e.g. status, grade, health) where the same set appears in multiple modules.

**Out of scope:**

- Generic `Literal["success", "error"]` in every response model (optional follow-up; not required for this phase).
- File open modes (`AsyncTextFileMode`); keep as Literal.
- One-off parsing of tool output (e.g. "passed"/"failed" in test output); low value for enum.

## Approach

1. Introduce enums in the appropriate modules (helpers, models, or a shared `cortex.core.enums` if many are cross-cutting).
2. Use `class X(str, Enum)` so JSON/MCP boundaries remain string values (`.value`).
3. Keep MCP tool parameters as `str` at the boundary; parse/validate to enum inside the handler (same pattern as `PreCommitCheck` and `determine_checks_to_perform`).
4. Replace Literal type aliases and string branches with enum members; use `.value` when writing to Pydantic/dict/JSON.

## Implementation Steps

### Milestone 1: Tool-layer enums (high impact, small surface)

1. **RulesOperation**  
   - Add `RulesOperation(str, Enum)` with `INDEX`, `GET_RELEVANT` in `cortex.tools.rules_operations` or `rules_operation_helpers`.  
   - Update `dispatch_operation(operation: ...)` to accept `str`, validate to `RulesOperation`, and branch on enum.  
   - Update call sites and error messages to use enum.

2. **FileOperation**  
   - Add `FileOperation(str, Enum)` with `READ`, `WRITE`, `METADATA` in `cortex.tools.file_operations` or `file_operation_helpers`.  
   - Update `manage_file(operation: ...)` to accept `str`, validate to `FileOperation`, use enum internally; keep docstring examples as strings.  
   - Replace internal branches and validation with enum.

3. **RefactoringAction**  
   - Add `RefactoringAction(str, Enum)` with `APPROVE`, `APPLY`, `ROLLBACK` (e.g. in `phase5_execution` or refactoring helpers).  
   - Update `apply_refactoring(action: ...)` and all `if action == "approve"` etc. to use enum.

4. **RefactoringSuggestionType**  
   - Add `RefactoringSuggestionType(str, Enum)` with `CONSOLIDATION`, `SPLITS`, `REORGANIZATION`.  
   - Update `suggest_refactoring(type: ...)`, `refactoring_operations`, and `execution_validator` branching to use enum.

### Milestone 2: Validation and configuration

1. **ValidationCheckType**  
   - Replace `CheckType = Literal["schema", "duplications", "quality", "infrastructure", "timestamps", "roadmap_sync"]` with `ValidationCheckType(str, Enum)` in `validation_dispatch` or `validation_helpers`.  
   - Update `validate(check_type: ...)` and all dispatch/branching to use enum.

2. **ConfigAction**  
   - Add `ConfigAction(str, Enum)` with `VIEW`, `UPDATE`, `RESET` for configure/validation config.  
   - Update configuration_operations branching and error messages.

3. **AnalysisTarget**  
   - Add `AnalysisTarget(str, Enum)` with `USAGE_PATTERNS`, `STRUCTURE`, `INSIGHTS`.  
   - Update analysis_operations dispatch and error messages.

### Milestone 3: Adapters and shared models

1. **StubAdapterLanguage**  
   - Replace `StubAdapterLanguage = Literal["typescript", "javascript", "rust", "go", "java"]` with `StubAdapterLanguage(str, Enum)` in `stub_adapter` or `base`.  
   - Update `StubAdapter.__init__` and registry usage to use enum where appropriate; keep MCP/CLI input as string.

2. **Shared quality/health enums (optional)**  
   - If desired: add `QualityGrade(str, Enum)` (A–F) and `HealthStatus(str, Enum)` (e.g. healthy, warning, critical) in a shared module used by validation, quality_metrics, and structure.  
   - Replace repeated `Literal["A","B",...]` and `Literal["healthy","warning","critical"]` in Pydantic models.  
   - Defer to a follow-up if scope is large.

### Milestone 4: Documentation and consistency

1date `docs/api/types.md` or equivalent to document new enums and the pattern (str Enum, `.value` at JSON boundary).  
2d a short guideline in `.cortex/synapse/rules` or python-coding-standards: “Use `class X(str, Enum)` for fixed sets of string values; reserve Literal for one-off or external API constraints.”

## Dependencies

- Existing pattern: `PreCommitCheck` in `pre_commit_helpers` and its use in `pre_commit_tools`.
- No new runtime dependencies; Python `enum` and Pydantic (serializes str Enum as value).

## Success Criteria

- All candidates from the codebase scan are either converted to enums or explicitly deferred with a short rationale.
- No regression: existing MCP tool JSON shapes unchanged (still string values).
- Type checker: 0 new errors; branches use enum members instead of raw strings where applicable.
- Tests: existing tests pass; new or updated tests cover enum validation and invalid-value handling where relevant.

## Testing Strategy

- **Coverage target:** Minimum 95% for new/changed code (enum definitions, validation paths, dispatch branches).
- **Unit tests:** For each new enum: construction from valid string, rejection of invalid string (where we validate), and `.value` serialization. Reuse existing tool tests; extend with enum-based parameter tests where needed.
- **Integration tests:** Ensure MCP tools still accept string parameters and return same JSON; add one test per tool that uses enum (e.g. pass valid string, assert success and response shape).
- **Edge cases:** Invalid operation/action/type strings return clear error (existing or improved message); Pydantic models that use enum still serialize to same string in JSON.
- **Pattern:** Arrange–Act–Assert; no blanket skips. When asserting on MCP JSON, use Pydantic v2 models and `model_validate_json()` where applicable (see `tests/tools/test_file_operations.py`).

## Risks and Mitigation

- **Risk:** Large refactor in validation/models could introduce regressions.  
  **Mitigation:** Milestone 1 first (tools only); then validation/config; then shared models optional.

- **Risk:** Pydantic or OpenAPI schema might expose enum names instead of values.  
  **Mitigation:** `str` Enum serializes as `.value` by default; verify schema in one tool after first enum rollout.

- **Risk:** File/function size limits (400/30 lines).  
  **Mitigation:** Put enums in small, dedicated modules or alongside existing helpers; no single file over limit.

## Timeline

- Milestone 1: 1–2 sessions (RulesOperation, FileOperation, RefactoringAction, RefactoringSuggestionType).  
- Milestone 2: 1 session (ValidationCheckType, ConfigAction, AnalysisTarget).  
- Milestone 3: 0.5–1 session (StubAdapterLanguage; optional shared quality/health enums deferred if needed).  
- Milestone 4: 0.5 session (docs and rules).

Total estimate: 3–5 sessions depending on optional shared-model enums and test depth.

## Notes

- Precedent: `PreCommitCheck` and `determine_checks_to_perform()` in `pre_commit_helpers` / `pre_commit_tools`.  
- Validation already uses `CheckType` Literal in `validation_dispatch` and `validation_helpers`; converting to enum is a direct replacement.  
- Phase 60 (manage_file discoverability) mentioned “operation enum values”; this plan fulfils that and extends the pattern everywhere identified.
