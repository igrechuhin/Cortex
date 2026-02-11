# Test Fixture Maintenance Protocol

This guide describes when and how to update test fixtures so they stay in sync with implementation code and avoid failures from incomplete mocks.

## When to update fixtures

Update fixtures when any of the following change:

1. **New configuration getters or gating methods**  
   If you add a new method on `OptimizationConfig` (or another manager) that is used by tool handlers, add the corresponding mock attribute to the fixture and to the validator’s required list.

2. **New managers in ManagersDict**  
   If you add a new manager (e.g. `optimization_config`, `summarization_engine`) that is resolved via `get_manager()` in tool code, ensure the relevant test fixtures provide a mock for it with all methods that the code path calls.

3. **Async method changes**  
   If a handler method is changed to async, update tests to `await` the coroutine. Consider adding a test-maintenance checklist step when making methods async (see Session Optimization 2026-02-07).

4. **Usage context / decorators**  
   If a tool uses `ensure_usage_context` and the test invokes the handler, patch `set_current_managers` and `set_current_project_root` to no-op where appropriate so the test does not persist real managers.

## Checklist for fixture updates

- [ ] Identify all test files that use the affected fixture (e.g. `mock_managers`, `mock_rules_manager`).
- [ ] Add the new mock member (method or property) with a sensible `return_value` or callable.
- [ ] If the fixture is validated (e.g. `validate_optimization_config_mock`), add the new member name to the validator’s required list in `tests/helpers/fixture_validator.py`.
- [ ] Update `tests/FIXTURE_REQUIREMENTS.md` if the new member is part of a documented fixture.
- [ ] Run the affected test module and the fixture validator unit tests.

## Where fixtures are validated

- **optimization_config (Phase 4)**  
  Validated in `tests/tools/test_phase4_optimization.py` via `validate_optimization_config_mock()` in the `mock_managers` fixture. Required list: `OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4` in `tests/helpers/fixture_validator.py`.

## Adding validation to a new fixture

1. Define the set of required member names (e.g. methods used by the code under test).
2. In `tests/helpers/fixture_validator.py`, add a new constant (e.g. `SOME_MANAGER_REQUIRED`) and a function `validate_some_manager_mock(mock) -> FixtureValidationResult`.
3. In the fixture, after building the mock, call the validator and `pytest.fail(result.message)` if `not result.valid`.
4. Document the fixture and required members in `tests/FIXTURE_REQUIREMENTS.md`.

## References

- Session optimization reviews: `.cortex/reviews/session-optimization-2026-02-06T22-15.md`, `session-optimization-2026-02-07T11-17.md`, `session-optimization-2026-02-09T08-12.md`
- Plan: `.cortex/plans/test-fixture-validation-maintenance.md` (if present)
