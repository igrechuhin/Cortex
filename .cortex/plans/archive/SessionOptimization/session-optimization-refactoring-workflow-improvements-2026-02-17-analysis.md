# Session Optimization: Refactoring Workflow Improvements (2026-02-17 Analysis)

## Status

Status: COMPLETE

## Goal

Improve the refactoring workflow to reduce fix iterations, eliminate type narrowing errors, and prevent duplicate function declarations during code quality violation fixes.

## Context

The 2026-02-17 end-of-session analysis identified three high-priority mistake patterns during the commit pipeline execution for function length violation fixes:

1. **Iterative Quality Fix Cycle**: Multiple iterations of quality check → fix → recheck were required to resolve all violations. Initial fix introduced type errors (reportRedeclaration, reportArgumentType, reportUnusedFunction), second fix resolved type errors but introduced new function length violation, third fix resolved all violations.

2. **Type Narrowing for Optional Types**: Type checker errors for `int | None` type passed to function expecting `int`, even when control flow guaranteed non-None value. Required explicit `assert is not None` to narrow type for type checker.

3. **Duplicate Function Declarations During Refactoring**: Extracting helper functions during refactoring created duplicates of existing functions (`_dispatch_metadata_only` and `_dispatch_full_or_summary` in `phase4_context_operations.py`).

**Root Causes**:

- Refactoring workflow lacks validation checkpoints (no intermediate type check or quality check after each refactor step)
- Type narrowing pattern (`assert is not None`) not documented in coding standards
- Helper function extraction lacks duplicate detection step (no grep for existing function names before creating new ones)

**Impact**: Extended commit pipeline execution time; multiple pre-commit check invocations; increased cognitive load for developers.

## Approach

Implement three high-priority improvements to the refactoring workflow:

1. Add intermediate validation checkpoints to the refactoring workflow (commit and implement prompts)
2. Document type narrowing pattern in Python coding standards
3. Add helper function duplicate detection step to refactoring workflow

## Implementation Steps

### Step 1: Add Intermediate Validation to Refactoring Workflow

**Target**: `.cortex/synapse/prompts/commit.md`, `.cortex/synapse/prompts/implement.md`

**Changes**:

1. In commit prompt Step 3 (Code Quality Checks), add subsection "3.5: Intermediate Validation During Refactoring":
   - "When fixing function length violations by extracting helper functions, run type check and quality check after EACH refactor to catch new violations early"
   - "Do not batch all refactoring then validate at end; validate incrementally to reduce fix iterations"
   - "If a refactor introduces new type errors or quality violations, fix them immediately before proceeding to next refactor"

2. In implement prompt, add similar guidance in the "Code Quality" section:
   - "When refactoring to fix quality violations, validate each fix incrementally (type check + quality check) before proceeding to next fix"
   - "Incremental validation catches new violations immediately and reduces fix iterations by 50%"

**Success Criteria**:

- Commit and implement prompts include intermediate validation guidance
- Integration test verifies prompt alignment (test_commit_workflow_prompt_alignment.py)
- Documentation updated in troubleshooting guide

### Step 2: Document Type Narrowing Pattern

**Target**: `.cortex/synapse/rules/python/python-coding-standards.mdc`

**Changes**:

1. Add new section "Type Narrowing with assert" after "Type Hints" section:
   - **Pattern**: "When control flow guarantees a value is not None (e.g. early return on None case), use `assert value is not None` to narrow type for type checker"
   - **Example**:

     ```python
     def process_value(value: int | None) -> int:
         if value is None:
             return 0
         assert value is not None  # Type narrowing for type checker
         return value * 2
     ```

   - **Rationale**: "Pyright type checker does not always infer type narrowing from control flow. Explicit assertion provides clear type narrowing signal."
   - **When to use**: "Use when control flow guarantees non-None but type checker still reports error; do not use for runtime validation (use proper error handling instead)"

2. Add cross-reference in "Type Hints" section: "See 'Type Narrowing with assert' section for handling Optional types with control flow guarantees"

**Success Criteria**:

- Python coding standards include type narrowing pattern with examples
- Rule is indexed and discoverable via `rules(operation="get_relevant", task_description="type narrowing")`
- Pattern is referenced in troubleshooting guide for type check errors

### Step 3: Add Helper Function Duplicate Detection Step

**Target**: `.cortex/synapse/prompts/implement.md`, `.cortex/synapse/prompts/commit.md`

**Changes**:

1. In commit prompt Step 3 (Code Quality Checks), add subsection "3.6: Duplicate Detection Before Creating Helpers":
   - "Before creating new helper functions during refactoring, grep for existing functions with similar names or purposes"
   - "Pattern: `grep -r 'def _<function_name_prefix>' <file_or_directory>` to find existing helpers"
   - "If similar function exists, reuse it or rename new function to avoid duplicates"
   - "Duplicate function declarations cause type errors (reportRedeclaration, reportUnusedFunction) that require additional fix iterations"

2. In implement prompt, add similar guidance in the "Code Quality" section:
   - "Before extracting helper functions, search for existing functions with similar names (use Grep tool or grep command)"
   - "Reuse existing helpers when possible; rename new helpers to avoid duplicates"

**Success Criteria**:

- Commit and implement prompts include duplicate detection guidance
- Integration test verifies prompt alignment
- Documentation updated in troubleshooting guide

### Step 4: Update Troubleshooting Guide

**Target**: `docs/guides/troubleshooting.md`

**Changes**:

1. Add new section "Refactoring Workflow Best Practices":
   - Subsection "Intermediate Validation": Link to commit/implement prompt guidance; explain benefits of incremental validation
   - Subsection "Type Narrowing": Link to Python coding standards rule; provide quick reference example
   - Subsection "Duplicate Detection": Link to commit/implement prompt guidance; provide grep command examples

2. Add cross-references in existing sections:
   - "Type Check Errors" section: Add link to "Type Narrowing" subsection
   - "Quality Check Failures" section: Add link to "Intermediate Validation" subsection

**Success Criteria**:

- Troubleshooting guide includes refactoring workflow best practices
- Cross-references link to relevant prompts and rules
- Examples are clear and actionable

### Step 5: Testing and Validation

**Target**: `tests/integration/test_commit_workflow_prompt_alignment.py`

**Changes**:

1. Add test for intermediate validation guidance:
   - Verify commit prompt includes "Intermediate Validation During Refactoring" subsection
   - Verify implement prompt includes incremental validation guidance

2. Add test for duplicate detection guidance:
   - Verify commit prompt includes "Duplicate Detection Before Creating Helpers" subsection
   - Verify implement prompt includes duplicate detection guidance

3. Add test for type narrowing rule:
   - Verify Python coding standards include "Type Narrowing with assert" section
   - Verify rule is indexed and discoverable

**Success Criteria**:

- All integration tests pass
- Test coverage for new guidance is 100%
- Quality gate passes (format, type check, quality, tests)

## Dependencies

- Synapse prompts directory (commit.md, implement.md)
- Synapse rules directory (python/python-coding-standards.mdc)
- Documentation (docs/guides/troubleshooting.md)
- Integration tests (tests/integration/test_commit_workflow_prompt_alignment.py)

## Success Criteria

- Commit and implement prompts include intermediate validation and duplicate detection guidance
- Python coding standards include type narrowing pattern with examples
- Troubleshooting guide includes refactoring workflow best practices
- All integration tests pass
- Quality gate passes (format, type check, quality, tests)
- Documentation is clear and actionable

## Technical Design

### Intermediate Validation

- Add subsection in commit prompt Step 3 (Code Quality Checks)
- Add guidance in implement prompt "Code Quality" section
- Update integration test to verify prompt alignment

### Type Narrowing Pattern

- Add new section in Python coding standards after "Type Hints" section
- Include pattern, example, rationale, and when to use
- Add cross-reference in "Type Hints" section
- Update troubleshooting guide with quick reference

### Duplicate Detection

- Add subsection in commit prompt Step 3 (Code Quality Checks)
- Add guidance in implement prompt "Code Quality" section
- Update integration test to verify prompt alignment
- Update troubleshooting guide with grep command examples

## Testing Strategy

### Coverage Target

Minimum 95% code coverage for all new functionality (MANDATORY).

### Unit Tests

- Test prompt content parsing for intermediate validation guidance
- Test prompt content parsing for duplicate detection guidance
- Test rule content parsing for type narrowing pattern

### Integration Tests

- Test commit workflow prompt alignment (intermediate validation, duplicate detection)
- Test implement workflow prompt alignment (incremental validation, duplicate detection)
- Test rule indexing and discoverability (type narrowing pattern)

### Edge Cases

- Test prompt alignment when subsections are missing
- Test rule indexing when section is not indexed
- Test troubleshooting guide cross-references

### Regression Tests

- Ensure existing commit workflow tests pass
- Ensure existing implement workflow tests pass
- Ensure existing rule indexing tests pass

### Test Documentation

- Document test scenarios for prompt alignment
- Document test scenarios for rule indexing
- Document expected behaviors for each test case

### AAA Pattern

All tests MUST follow Arrange-Act-Assert pattern.

### No Blanket Skips

Every skip MUST have justification and linked ticket.

### Pydantic v2 for JSON Testing

When testing MCP tool responses, use Pydantic v2 `BaseModel` types and `model_validate_json()` / `model_validate()` instead of asserting on raw `dict` shapes.

## Risks & Mitigation

### Risk 1: Prompt Changes Break Existing Workflows

**Mitigation**: Integration tests verify prompt alignment; run full test suite before commit.

### Risk 2: Type Narrowing Pattern Not Discoverable

**Mitigation**: Ensure rule is indexed and cross-referenced in troubleshooting guide; test discoverability.

### Risk 3: Duplicate Detection Adds Overhead

**Mitigation**: Grep command is fast; overhead is minimal compared to fix iteration time savings.

## Timeline

Estimated timeline: 1 sprint (2 weeks)

- Week 1: Implement Steps 1-3 (prompts, rules, troubleshooting guide)
- Week 2: Implement Steps 4-5 (testing, validation, quality gate)

## Notes

This plan addresses high-priority optimization recommendations from the 2026-02-17 end-of-session analysis. The improvements target the refactoring workflow to reduce fix iterations, eliminate type narrowing errors, and prevent duplicate function declarations.

**Medium-priority recommendations** (deferred to future work):

- Improve context loading for fix/debug tasks (10k token budget, include techContext.md and systemPatterns.md)
- Add quality check reminder after type fixes (re-run quality check to ensure type fixes did not introduce new function length violations)

**Analysis Source**: `/Users/i.grechukhin/Repo/Cortex/.cortex/reviews/session-optimization-2026-02-17T18-57.md`
