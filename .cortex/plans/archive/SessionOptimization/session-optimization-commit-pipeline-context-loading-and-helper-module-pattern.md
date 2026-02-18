# Session Optimization: Commit Pipeline Context Loading and Helper Module Pattern

## Source

End-of-session analysis report: `session-optimization-2026-02-16T16-43.md` (reviews directory).

## Recommendations Summary

1. **Context loading optimization for commit pipeline** – Optimize `load_context` calls for commit pipeline tasks to reduce token usage by 40-60% while maintaining effectiveness. Focus on essential files (`activeContext.md`, `roadmap.md`, `progress.md`) and reduce token budget from 5000 to 3000-4000 tokens.

2. **Helper module extraction pattern documentation** – Document the helper module extraction pattern for code quality violations (file size > 400 lines, function length > 30 lines) as a standard refactoring approach in implement prompt and code quality guidelines.

## Plan Steps

### Step 1: Optimize Commit Pipeline Context Loading

1. **Update commit prompt Pre-Action Checklist**:
   - Specify targeted file selection for commit pipeline tasks
   - Essential files: `activeContext.md`, `roadmap.md`, `progress.md`
   - Optional files: `techContext.md`, `systemPatterns.md`, `productContext.md`, `projectBrief.md` (load only if task-specific relevance)
   - Token budget: Reduce from 5000 to 3000-4000 tokens for commit pipeline workflow tasks

2. **Update load_context guidance**:
   - Document commit pipeline task type in load_context tool or implement prompt
   - Specify recommended file set and token budget for commit pipeline tasks
   - Ensure guidance aligns with actual usage patterns (low utilization observed)

**Target File**: `.cortex/synapse/prompts/commit.md`

**Expected Impact**: Reduce token usage by 40-60% for commit pipeline tasks while maintaining effectiveness.

### Step 2: Document Helper Module Extraction Pattern

1. **Add helper module extraction guidance to implement prompt**:
   - Document pattern in Step 4 (Code Quality Checks)
   - When file size exceeds 400 lines: identify cohesive function groups, extract to `*_helpers.py` modules
   - When function length exceeds 30 lines: extract logic to helper functions in same file or helper module
   - Maintain test coverage and update imports

2. **Update code quality guidelines**:
   - Add helper module extraction as standard refactoring approach
   - Document naming conventions (`*_helpers.py` for extracted modules)
   - Provide examples from recent refactoring (e.g., `phase4_metadata_helpers.py`)

**Target File**: `.cortex/synapse/prompts/implement-next-roadmap-step.md`

**Expected Impact**: Standardize refactoring approach, reduce decision time, improve consistency.

## Status

PENDING

## Completion Criteria

- Commit prompt updated with optimized context loading guidance (targeted files, reduced token budget)
- Implement prompt updated with helper module extraction pattern documentation
- Code quality guidelines include helper module extraction pattern
- Token usage reduced for commit pipeline tasks (measured via context effectiveness analysis)

## Related Plans

- `session-optimization-path-resolver-context-loading-2026-02-11.md` – General context loading improvements
- `session-optimization-test-coverage-and-development-workflow-improvements.md` – Test coverage and workflow improvements

## Notes

- Analysis showed commit pipeline tasks had very low token utilization (0.56%) with 5000 token budget
- Helper module extraction successfully resolved quality violations in `phase4_context_operations.py`
- Pattern should be documented to reduce refactoring decision time in future sessions
