# Session Optimization: Commit Pipeline Improvements

**Status**: PENDING

**Related**: See [Session Optimization: Commit Pipeline Orchestration Refactor](.cortex/plans/session-optimization-commit-pipeline-orchestration-refactor.md) for structural changes (phase-based pipeline, phase helpers, helper commands). This plan focuses on checks and content (async tests, markdown, spelling, integration test schema, memory-bank write quality).

**Goal**: Implement improvements to the commit pipeline based on end-of-session analysis findings to prevent recurring issues (async test validation, markdown formatting, git SSL handling).

## Context

During commit pipeline execution (2026-02-07), several issues were identified that, while resolved, indicate process gaps:

1. **Test Maintenance Gap**: 3 tests failed because `MCPToolFailureHandler.detect_failure()` was made async in Phase 3.2, but tests were not updated to await the coroutine. Type checker (pyright) doesn't catch unawaited coroutines in test code.

2. **Markdown Formatting Violations**: 5 markdown lint errors (MD036 - emphasis used instead of heading) across multiple files. Errors accumulate before commit because markdown lint only runs during pre-commit checks.

3. **Git SSL Certificate Configuration**: Git push failed with SSL certificate verification error. While non-blocking (commit was already created), this indicates missing documentation and no fallback strategy for non-critical git operations.

**Root Causes**:

- No automated detection when async methods are introduced (test maintenance gap)
- No early validation during file creation/editing (markdown formatting)
- Missing guidance and fallback strategy for git SSL issues

**Impact**: These issues block commit pipeline, requiring manual investigation and fixes. The patterns are likely to recur without preventive measures.

### New Input (2026-02-07 end-of-session, post-commit)

From session-optimization-2026-02-07T20-53:

1. **Integration test content vs schema**: Two tests (`test_full_workflow`, `test_initialize_read_write_workflow`) wrote projectBrief content missing required schema sections (Project Overview, Goals, Core Requirements, Success Criteria), causing schema validation failures. Test fixtures were not aligned with `schema_validator` required sections.

2. **Markdown lint scope**: One MD026 in `.cortex/history/progress_v11.md`. Commit prompt should explicitly state that markdown lint runs on all markdown files (including `.cortex/history/` and `.cortex/reviews/`) so agents don’t assume history is out of scope.

3. **Memory bank write quality**: After Step 5 (memory-bank-updater), typos appeared in activeContext/progress (e.g. "900.01%", "Phase 18Markdown"). Review memory-bank-updater agent to reduce numeric and phase-name typos; consider templating or validation of key fields before writing.

## Approach

Implement improvements in three categories:

1. **Automated Validation**: Add checks to detect issues before they block commits
2. **Early Detection**: Integrate validation earlier in development workflow
3. **Documentation and Process**: Add guidance and fallback strategies

## Implementation Steps

### Step 1: Add Async Test Validation ✅ COMPLETED (2026-02-11)

**Goal**: Add automated check to detect unawaited coroutines in test files.

**Tasks**:

1. Create `.cortex/synapse/scripts/python/check_async_tests.py`:
   - Parse test files to detect async function calls
   - Identify coroutine calls that are not awaited
   - Report unawaited coroutines with file and line number
   - Support both `pytest` and `unittest` test patterns
   - Return proper exit codes (0 = no issues, 1 = issues found)

2. Integrate into pre-commit checks:
   - Add `check_async_tests` to `execute_pre_commit_checks` tool
   - Add to `checks` enum in `pre_commit_tools.py`
   - Add Python adapter support in `python_adapter.py`
   - Run check before test execution in commit pipeline

3. Add unit tests for `check_async_tests.py`:
   - Test detection of unawaited coroutines
   - Test false positives (properly awaited coroutines)
   - Test edge cases (nested calls, decorators, fixtures)
   - Test exit codes and error reporting

4. Update commit prompt documentation:
   - Document new `check_async_tests` check
   - Add to Step 4 (Test Execution) in commit prompt

**Success Criteria**:

- Script detects unawaited coroutines in test files
- Script integrated into pre-commit checks
- All new functionality has 95%+ test coverage
- Commit pipeline includes async test validation

**Dependencies**: None

**Estimated Effort**: 4-6 hours

### Step 2: Early Markdown Lint Validation

**Goal**: Run markdown lint on file save or during editing to catch errors before commit.

**Tasks**:

1. Create git pre-commit hook for markdown lint:
   - Create `.git/hooks/pre-commit` (or `.githooks/pre-commit`)
   - Run `fix_markdown_lint` on staged markdown files
   - Auto-fix fixable issues (MD036, etc.)
   - Block commit if unfixable errors remain
   - Document hook installation in `docs/getting-started.md`

2. Add Cursor IDE integration (optional):
   - Create `.cursor/rules/markdown-lint-on-save.md` rule
   - Document how to configure Cursor to run markdown lint on save
   - Reference markdown lint tool and configuration

3. Update commit prompt:
   - Note that markdown lint runs in pre-commit hook
   - Update Step 1.5 (Markdown Linting) to reference hook
   - Document manual override if needed

4. Test hook integration:
   - Verify hook runs on commit attempt
   - Verify auto-fix works correctly
   - Verify commit blocked for unfixable errors
   - Test hook with various markdown files

**Success Criteria**:

- Pre-commit hook runs markdown lint on staged files
- Hook auto-fixes fixable issues
- Hook blocks commit for unfixable errors
- Documentation updated

**Dependencies**: None

**Estimated Effort**: 2-3 hours

### Step 3: Markdown Formatting Guidelines

**Goal**: Document when to use headings vs emphasis to prevent MD036 violations.

**Tasks**:

1. Create `.cortex/synapse/rules/markdown-formatting.mdc`:
   - Document when to use headings (section titles, major divisions)
   - Document when to use emphasis (inline emphasis, minor highlights)
   - Provide examples of correct vs incorrect usage
   - Include MD036 rule explanation and examples
   - Add to rules indexing

2. Update rules indexing:
   - Ensure new rule is indexed by `rules(operation="index")`
   - Verify rule appears in relevant rule retrieval
   - Test rule retrieval for markdown-related tasks

3. Update agent documentation:
   - Reference markdown formatting rule in `AGENTS.md`
   - Add to implement prompt (Step 4.3) for markdown file creation
   - Include in commit prompt guidance

4. Add examples to documentation:
   - Show correct heading usage in `docs/guides/markdown-formatting.md`
   - Show incorrect emphasis usage (what to avoid)
   - Link from commit prompt and agent docs

**Success Criteria**:

- Markdown formatting rule created and indexed
- Rule retrievable for markdown-related tasks
- Documentation updated with examples
- Agents reference rule in workflows

**Dependencies**: None

**Estimated Effort**: 2-3 hours

### Step 4: Git SSL Certificate Documentation

**Goal**: Document SSL certificate troubleshooting for git operations.

**Tasks**:

1. Create `docs/troubleshooting.md` (or add section to existing docs):
   - Document SSL certificate verification errors
   - Provide solutions for common SSL issues:
     - Missing CA certificates
     - Incorrect certificate paths
     - Self-signed certificates
     - Certificate expiration
   - Include platform-specific guidance (macOS, Linux, Windows)
   - Add git configuration examples

2. Update commit prompt:
   - Reference troubleshooting guide in Step 14 (Push Branch)
   - Add note about SSL certificate issues
   - Document that push failures are non-blocking (commit already created)

3. Add to git operations guide:
   - Create or update `docs/guides/git-operations.md`
   - Include SSL certificate troubleshooting
   - Reference from commit prompt

4. Test documentation:
   - Verify links work correctly
   - Ensure examples are accurate
   - Check platform-specific guidance

**Success Criteria**:

- Troubleshooting documentation created
- SSL certificate issues documented
- Commit prompt references troubleshooting guide
- Documentation is accurate and helpful

**Dependencies**: None

**Estimated Effort**: 1-2 hours

### Step 5: Test Maintenance Checklist

**Goal**: Add checklist item for test updates when making methods async.

**Tasks**:

1. Update `.cortex/synapse/agents/implement.md`:
   - Add Step 4.3.1: "When making methods async, update all test calls to await coroutines"
   - Add checklist item: "Verify all async method calls in tests are awaited"
   - Include reference to async test validation (Step 1)
   - Add to refactoring workflow section

2. Update commit prompt:
   - Add note in Step 0 (Fix Errors) about async test updates
   - Reference test maintenance checklist
   - Link to async test validation check

3. Create test maintenance guide:
   - Create `docs/guides/test-maintenance.md`
   - Document async test patterns
   - Include examples of correct async test usage
   - Reference from implement prompt

4. Update refactoring workflows:
   - Add async conversion checklist to refactoring prompts
   - Include test update requirement
   - Reference test maintenance guide

**Success Criteria**:

- Implement prompt includes async test update checklist
- Commit prompt references test maintenance
- Test maintenance guide created
- Refactoring workflows include async test updates

**Dependencies**: Step 1 (Async Test Validation) for validation tool reference

**Estimated Effort**: 1-2 hours

### Step 6: Commit Pipeline Push Strategy

**Goal**: Make push optional or add retry logic for SSL errors.

**Tasks**:

1. Update `.cortex/synapse/prompts/commit.md`:
   - Modify Step 14 (Push Branch) to make push optional
   - Add retry logic for SSL certificate errors (up to 2 retries)
   - Document that push failures are non-blocking
   - Add fallback: if push fails, provide instructions for manual push
   - Update error handling to distinguish SSL errors from other push failures

2. Add push retry logic:
   - Implement retry with exponential backoff for SSL errors
   - Log retry attempts
   - Provide clear error messages with troubleshooting links
   - Document retry behavior

3. Update commit pipeline documentation:
   - Document push as optional post-commit step
   - Explain when push might fail (SSL, network, permissions)
   - Provide manual push instructions
   - Reference troubleshooting guide (Step 4)

4. Test push strategy:
   - Test with SSL errors (if possible in test environment)
   - Test retry logic
   - Test error messages and troubleshooting links
   - Verify non-blocking behavior

**Success Criteria**:

- Push is optional in commit pipeline
- Retry logic implemented for SSL errors
- Error messages provide troubleshooting guidance
- Push failures don't block commit success
- Documentation updated

**Dependencies**: Step 4 (Git SSL Certificate Documentation) for troubleshooting reference

**Estimated Effort**: 2-3 hours

### Step 7: Integration Test Schema Alignment ✅ COMPLETED (2026-02-11)

**Goal**: Ensure integration tests that write projectBrief use content satisfying schema_validator required sections (Project Overview, Goals, Core Requirements, Success Criteria).

**Tasks**:

1. Add shared fixture or constant for minimal valid projectBrief content:
   - Define in test helpers or conftest (e.g. `tests/conftest.py` or `tests/helpers/schema_fixtures.py`)
   - Include all four required sections with minimal valid content
   - Document that schema_validator required sections must be kept in sync

2. Update integration tests that write projectBrief:
   - Use the shared fixture in `test_full_workflow` (tests/test_integration.py) and `test_initialize_read_write_workflow` (tests/integration/test_mcp_tools_integration.py)
   - Optionally add a schema validation check in test setup to fail fast if fixture drifts from schema

3. Add unit test for fixture:
   - Assert fixture content passes schema validation for projectBrief
   - Ensures fixture stays aligned when schema changes

**Success Criteria**:

- Single source of truth for minimal valid projectBrief content in tests
- Both affected integration tests use it; no schema validation failures from test content
- Fixture validated against schema in tests

**Dependencies**: None

**Estimated Effort**: 1-2 hours

### Step 8: Markdown Lint Scope in Commit Prompt ✅ COMPLETED (2026-02-11)

**Goal**: Clarify in the commit prompt that markdown lint runs on all markdown files, including `.cortex/history/` and `.cortex/reviews/`, so agents and tools don’t assume history/reviews are out of scope.

**Tasks**:

1. Update commit prompt (Step 1.5 and/or Step 12.5):
   - State explicitly that markdown lint uses `check_all_files=True` and includes all `.md`/`.mdc` under the project (including `.cortex/history/`, `.cortex/reviews/`)
   - Note that files modified by MCP tools (e.g. history, session reviews) are included and must pass lint

2. Verify tool behavior:
   - Confirm `fix_markdown_lint(check_all_files=True)` already covers history and reviews; document in prompt if needed

**Success Criteria**:

- Commit prompt clearly states scope of markdown lint (all files, including history and reviews)
- No code change required if tool already covers scope; documentation only

**Dependencies**: None

**Estimated Effort**: ~0.5 hours

### Step 9: Memory Bank Write Quality

**Goal**: Reduce typos in memory-bank-updater (or equivalent) outputs when writing activeContext/progress (e.g. coverage percentage, phase names).

**Tasks**:

1. Review memory-bank-updater agent and related prompts:
   - Identify where numeric values (e.g. coverage %, year) and phase/label names are inserted
   - Add templating or validation for key fields (e.g. coverage as "90.01%" not "900.01%", phase labels without concatenation artifacts)

2. Add validation or sanitization before write:
   - Validate numeric ranges (e.g. coverage 0–100) and date format (e.g. YYYY-MM-DD)
   - Sanitize phase/label strings to avoid concatenation typos ("Phase 18" + "Markdown" → "Phase 18 Markdown" not "Phase 18Markdown")

3. Test with commit pipeline:
   - Run Step 5 (memory bank update) and verify no typos in written content; add regression check if feasible

**Success Criteria**:

- Fewer or no typos in automated activeContext/progress entries for coverage, dates, phase names
- Process documented; validation/sanitization in place where practical

**Dependencies**: None

**Estimated Effort**: 2-3 hours

## Dependencies

- **Step 1** (Async Test Validation): No dependencies
- **Step 2** (Early Markdown Lint Validation): No dependencies
- **Step 3** (Markdown Formatting Guidelines): No dependencies
- **Step 4** (Git SSL Certificate Documentation): No dependencies
- **Step 5** (Test Maintenance Checklist): Depends on Step 1 for validation tool reference
- **Step 6** (Commit Pipeline Push Strategy): Depends on Step 4 for troubleshooting reference
- **Step 7** (Integration Test Schema Alignment): No dependencies
- **Step 8** (Markdown Lint Scope in Commit Prompt): No dependencies
- **Step 9** (Memory Bank Write Quality): No dependencies

**Execution Order**: Steps 1-4 and 7-9 can be executed in parallel. Step 5 should follow Step 1. Step 6 should follow Step 4.

## Success Criteria

- All 9 steps implemented and tested
- Async test validation prevents unawaited coroutine issues
- Early markdown lint validation catches errors before commit
- Markdown formatting guidelines prevent MD036 violations
- Git SSL certificate issues documented and handled gracefully
- Test maintenance checklist prevents async test gaps
- Commit pipeline push strategy handles SSL errors gracefully
- Integration tests use schema-aligned projectBrief fixture (Step 7)
- Markdown lint scope (history, reviews) documented in commit prompt (Step 8)
- Memory bank write quality improved; typos reduced (Step 9)
- All new functionality has 95%+ test coverage
- Documentation updated and accurate

## Testing Strategy

### Coverage Target

#### Minimum 95% code coverage for ALL new functionality (MANDATORY)

### Unit Tests

1. **Async Test Validation (Step 1)**:
   - Test detection of unawaited coroutines in various patterns
   - Test false positives (properly awaited coroutines)
   - Test edge cases (nested calls, decorators, fixtures)
   - Test exit codes and error reporting
   - Test integration with pre-commit checks

2. **Markdown Lint Hook (Step 2)**:
   - Test hook execution on commit attempt
   - Test auto-fix functionality
   - Test commit blocking for unfixable errors
   - Test hook with various markdown files
   - Test hook error handling

3. **Markdown Formatting Rule (Step 3)**:
   - Test rule indexing and retrieval
   - Test rule content accuracy
   - Test rule integration with agent workflows

4. **Git SSL Documentation (Step 4)**:
   - Test documentation accuracy
   - Test link validity
   - Test platform-specific guidance accuracy

5. **Test Maintenance Checklist (Step 5)**:
   - Test checklist completeness
   - Test workflow integration
   - Test guide accuracy

6. **Push Strategy (Step 6)**:
   - Test retry logic with various error types
   - Test error message accuracy
   - Test non-blocking behavior
   - Test troubleshooting link validity

7. **Integration Test Schema Alignment (Step 7)**:
   - Test shared projectBrief fixture passes schema validation
   - Test integration tests using fixture pass
   - Test fixture drift detection if implemented

8. **Memory Bank Write Quality (Step 9)**:
   - Test validation/sanitization of numeric and label fields
   - Regression test for commit pipeline Step 5 output quality

### Integration Tests

1. **Pre-commit Check Integration**:
   - Test async test validation in full pre-commit pipeline
   - Test markdown lint hook in git workflow
   - Test error reporting and blocking behavior

2. **Commit Pipeline Integration**:
   - Test full commit pipeline with all improvements
   - Test push retry logic in commit workflow
   - Test error handling and non-blocking behavior

3. **Agent Workflow Integration**:
   - Test markdown formatting rule retrieval in agent workflows
   - Test test maintenance checklist in implement prompt
   - Test troubleshooting guide references

### Edge Cases

1. **Async Test Validation**:
   - Nested async calls
   - Decorators that modify async behavior
   - Fixtures with async setup/teardown
   - Test classes with async methods

2. **Markdown Lint Hook**:
   - Large markdown files
   - Files with mixed content
   - Files with existing errors
   - Hook execution failures

3. **Push Strategy**:
   - Network timeouts
   - Permission errors
   - Repository not found errors
   - Multiple retry scenarios

### Regression Tests

- Verify existing commit pipeline functionality unchanged
- Verify existing pre-commit checks still work
- Verify existing test suite still passes
- Verify existing documentation links still work

### Test Documentation

- Document test scenarios and expected behaviors
- Document edge cases and handling
- Document integration test scenarios
- Document regression test coverage

### AAA Pattern

All tests MUST follow Arrange-Act-Assert pattern:

- **Arrange**: Set up test fixtures, mocks, and test data
- **Act**: Execute the code under test
- **Assert**: Verify expected outcomes and behaviors

### No Blanket Skips

Every skip MUST have justification and linked ticket. No blanket test skips allowed.

### Pydantic v2 for JSON Testing

When testing MCP tool responses (e.g., `execute_pre_commit_checks`, `manage_file`), use Pydantic v2 `BaseModel` types and `model_validate_json()` / `model_validate()` instead of asserting on raw `dict` shapes. See `tests/tools/test_file_operations.py` for examples (e.g., `ManageFileErrorResponse` pattern).

## Risks & Mitigation

### Risk 1: Async Test Validation False Positives

**Risk**: Validation script incorrectly flags properly awaited coroutines as unawaited.
**Mitigation**: Comprehensive test suite covering various async patterns. Careful AST parsing to detect await statements.

### Risk 2: Markdown Lint Hook Performance

**Risk**: Hook adds significant delay to commit process for large markdown files.
**Mitigation**: Only lint staged files. Use caching for repeated files. Optimize lint execution.

### Risk 3: Push Retry Logic Complexity

**Risk**: Retry logic adds complexity and may mask other issues.
**Mitigation**: Clear error messages distinguishing SSL errors from other failures. Limit retries (max 2). Document behavior.

### Risk 4: Documentation Maintenance

**Risk**: Documentation becomes stale as project evolves.
**Mitigation**: Link documentation from relevant prompts and workflows. Include in review process.

## Timeline

**Estimated Total Effort**: 12-17 hours

**Sprint Breakdown**:

- **Sprint 1** (Steps 1-3): 8-12 hours - Automated validation and early detection
- **Sprint 2** (Steps 4-6): 4-5 hours - Documentation and process improvements

**Priority**: Medium (addresses recurring issues but not blocking)

## Notes

- This plan addresses recommendations from end-of-session analysis (2026-02-07)
- All improvements are preventive measures to avoid recurring issues
- Steps can be implemented incrementally
- Documentation updates should be reviewed for accuracy
- Consider user feedback on improvements after implementation
