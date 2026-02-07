# Test Fixture Validation and Maintenance

**Status**: Planning

**Goal**: Implement test fixture validation and maintenance mechanisms to prevent test failures caused by incomplete mock configurations, ensuring fixtures stay in sync with implementation changes.

## Context

During commit pipeline execution (2026-02-06), 6 tests failed in `test_phase4_optimization.py` due to missing mock methods in the `mock_managers` fixture. The fixture was missing:

- `is_summarization_enabled.return_value`
- `is_optimization_enabled.return_value`
- `get_summarization_target_reduction.return_value`
- `get_summarization_strategy.return_value`

**Root Cause**: The optimization config wiring was implemented incrementally (Steps 1-8), and when Step 3 (summarization) added new gating logic (`is_summarization_enabled()`), the test fixtures weren't updated to reflect all required mock methods. This created a gap between implementation requirements and test fixture configuration.

**Impact**: Test failures block commit pipeline, requiring manual investigation and fixture updates. This pattern is likely to recur as new configuration getters or gating methods are added.

## Approach

Implement a three-pronged approach:

1. **Fixture Validation**: Add automated validation to detect incomplete fixtures before tests run
2. **Fixture Documentation**: Document all required mock return values in fixture docstrings/comments
3. **Fixture Maintenance Protocol**: Establish a protocol for updating fixtures immediately when implementation changes

## Implementation Steps

### Step 1: Create Fixture Validation Helper

**Goal**: Create a reusable helper function that validates fixture completeness against expected manager interfaces.

**Tasks**:

1. Create `tests/helpers/fixture_validator.py` with:
   - `validate_mock_manager_fixture(fixture, manager_protocol)` function
   - Validates that all required methods/properties from protocol are configured in mock
   - Returns validation result with missing methods list
   - Supports both `MagicMock` and `AsyncMock` validation
2. Create protocol definitions for manager interfaces:
   - `OptimizationConfigProtocol` (defines all getters and gating methods)
   - `FileSystemManagerProtocol` (if needed)
   - `MetadataIndexProtocol` (if needed)
   - Use `typing.Protocol` for structural subtyping
3. Add unit tests for `fixture_validator.py`:
   - Test validation passes when all methods configured
   - Test validation fails when methods missing
   - Test validation handles optional vs required methods
   - Test validation works with both sync and async mocks

**Success Criteria**:

- Helper function validates mock completeness
- Protocol definitions match actual manager interfaces
- Unit tests achieve 95%+ coverage
- Validation can be called from test fixtures or test setup

### Step 2: Integrate Fixture Validation into Test Suite

**Goal**: Add fixture validation checks to existing test fixtures to catch incomplete configurations early.

**Tasks**:

1. Update `mock_managers` fixture in `tests/tools/test_phase4_optimization.py`:
   - Add validation call using `validate_mock_manager_fixture()`
   - Validate `optimization_config` mock against `OptimizationConfigProtocol`
   - Raise `pytest.fail()` or `AssertionError` if validation fails
   - Include helpful error message listing missing methods
2. Identify other fixtures that use manager mocks:
   - Search for `MagicMock()` or `AsyncMock()` usage in `tests/conftest.py`
   - Search for fixtures in `tests/tools/` that mock managers
   - Add validation to high-risk fixtures (those that mock config objects)
3. Create pytest plugin or hook (optional):
   - `pytest_collection_modifyitems` hook to validate fixtures at collection time
   - Or `pytest_fixture_setup` hook to validate during fixture setup
   - Log validation failures as warnings or errors

**Success Criteria**:

- `mock_managers` fixture validates `optimization_config` completeness
- At least 3 other high-risk fixtures have validation
- Validation failures provide clear error messages
- Tests fail fast with helpful diagnostics

### Step 3: Document Fixture Requirements

**Goal**: Add comprehensive documentation to fixture docstrings and comments listing all required mock return values.

**Tasks**:

1. Update `mock_managers` fixture docstring:
   - List all required `optimization_config` mock methods
   - Document expected return value types
   - Include example configuration
   - Add note about keeping in sync with `OptimizationConfig` implementation
2. Create `tests/FIXTURE_REQUIREMENTS.md` documentation:
   - Document all shared fixtures in `conftest.py`
   - List required mock methods for each manager type
   - Include examples of complete fixture configurations
   - Add maintenance guidelines (when to update fixtures)
3. Add inline comments to complex fixtures:
   - Comment each mock method configuration
   - Explain why each return value is needed
   - Reference related implementation code

**Success Criteria**:

- All fixture docstrings list required mock methods
- `FIXTURE_REQUIREMENTS.md` documents at least 5 fixture types
- Inline comments explain mock configurations
- Documentation is discoverable and maintainable

### Step 4: Establish Fixture Maintenance Protocol

**Goal**: Create a protocol for updating fixtures immediately when implementation changes, preventing fixture drift.

**Tasks**:

1. Create `tests/FIXTURE_MAINTENANCE.md` guide:
   - Document when to update fixtures (new getters, new gating methods, new managers)
   - Provide checklist for fixture updates
   - Include examples of common fixture update scenarios
2. Add pre-commit hook or CI check (optional):
   - Script that validates fixtures against implementation
   - Fails commit if fixtures are incomplete
   - Or add to existing pre-commit checks
3. Update development workflow documentation:
   - Add fixture update step to "Adding New Configuration" workflow
   - Add fixture update step to "Adding New Manager" workflow
   - Reference in `CONTRIBUTING.md` or similar

**Success Criteria**:

- Maintenance guide documents update protocol
- Developers know when and how to update fixtures
- Protocol is integrated into development workflow
- Fixture updates happen proactively, not reactively

### Step 5: Add Integration Test for Fixture Completeness

**Goal**: Create integration test that verifies all test fixtures are complete and up-to-date.

**Tasks**:

1. Create `tests/integration/test_fixture_completeness.py`:
   - Test that discovers all fixtures using manager mocks
   - Validates each fixture against expected protocols
   - Reports missing methods across all fixtures
   - Can be run standalone or as part of test suite
2. Add test to CI pipeline:
   - Run `test_fixture_completeness` as part of quality checks
   - Fail CI if fixtures are incomplete
   - Provide clear error output for fixing fixtures
3. Add test to pre-commit checks (optional):
   - Run fixture completeness check before commit
   - Block commit if fixtures incomplete
   - Or run as warning-only check

**Success Criteria**:

- Integration test validates all fixtures
- Test runs in CI and catches fixture drift
- Test output is actionable (lists missing methods)
- Test execution time is acceptable (<5 seconds)

## Dependencies

- **Phase 51 (Wire optimization config to runtime)**: Completed - provides context for the fixture gap
- **Test infrastructure**: Existing pytest fixtures and conftest.py
- **Protocol definitions**: Need to create protocol interfaces for managers

## Success Criteria

1. **Fixture Validation**: Automated validation detects incomplete fixtures before tests run
2. **Fixture Documentation**: All fixtures have documented requirements
3. **Fixture Maintenance**: Protocol ensures fixtures stay in sync with implementation
4. **Test Coverage**: All new code achieves 95%+ coverage
5. **Zero Fixture Drift**: No test failures due to missing mock methods for 3+ months

## Testing Strategy

### Coverage Target

#### Minimum 95% code coverage for ALL new functionality (MANDATORY)

### Unit Tests

- **fixture_validator.py**: Test all validation logic, protocol matching, error handling
- **Protocol definitions**: Test that protocols match actual manager interfaces
- **Validation helpers**: Test edge cases (optional methods, async mocks, nested mocks)

### Integration Tests

- **Fixture completeness test**: Test that discovers and validates all fixtures
- **Fixture validation integration**: Test validation works in real test scenarios
- **Protocol validation**: Test protocols match implementation at runtime

### Edge Cases

- **Optional vs required methods**: Test validation handles optional methods correctly
- **Async mocks**: Test validation works with `AsyncMock` and `MagicMock`
- **Nested mocks**: Test validation handles nested mock structures
- **Dynamic methods**: Test validation handles dynamically added mock methods

### Regression Tests

- **Existing tests**: Ensure all existing tests still pass after adding validation
- **Fixture updates**: Test that fixture updates don't break existing tests
- **Protocol changes**: Test that protocol changes are caught by validation

### Test Documentation

- **Test scenarios**: Document all test scenarios and expected behaviors
- **AAA Pattern**: All tests follow Arrange-Act-Assert pattern
- **No Blanket Skips**: Every skip MUST have justification and linked ticket

### Pydantic v2 for JSON Testing

When testing MCP tool responses or JSON structures, use Pydantic v2 `BaseModel` types and `model_validate_json()` / `model_validate()` instead of asserting on raw `dict` shapes. See `tests/tools/test_file_operations.py` for examples (e.g., `ManageFileErrorResponse` pattern).

## Risks & Mitigation

1. **Risk**: Validation adds overhead to test execution
   - **Mitigation**: Make validation optional (can be disabled), run only in CI, or cache validation results

2. **Risk**: Protocol definitions drift from implementation
   - **Mitigation**: Use structural subtyping (`typing.Protocol`), validate protocols match implementation in tests

3. **Risk**: False positives (validation fails but fixtures are correct)
   - **Mitigation**: Support optional methods, allow fixture-specific overrides, provide clear error messages

4. **Risk**: Maintenance burden (updating protocols when implementation changes)
   - **Mitigation**: Auto-generate protocols from implementation where possible, document maintenance protocol

## Timeline

- **Step 1**: 2-3 days (fixture validation helper)
- **Step 2**: 2-3 days (integrate validation)
- **Step 3**: 1-2 days (documentation)
- **Step 4**: 1-2 days (maintenance protocol)
- **Step 5**: 2-3 days (integration test)

**Total**: 8-13 days

## Notes

- This plan addresses the immediate issue (incomplete fixtures) and establishes long-term maintenance
- Fixture validation can be extended to other manager types beyond `OptimizationConfig`
- Consider adding fixture validation to other test suites (unit, integration) if beneficial
- Protocol definitions can be reused for type checking and IDE support
- This work complements existing test infrastructure and doesn't require major refactoring
