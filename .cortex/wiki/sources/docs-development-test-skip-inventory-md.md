# Test skip / xfail inventory

Living document for `.cortex/plans/cleanup-skipped-legacy-tests.md` (Step 1). Update when skip patterns change.

## Classification legend

| Category | Meaning |
| --- | --- |
| A | Permanent skip / xfail without tracked ref (should be fixed or removed) |
| B | Skip with reason + plan/issue ref |
| C | Conditional `skipif` / `xfail` (platform or expected flake) |

## `@pytest.mark.skip` (unconditional)

Enforced at collection via `tests/conftest.py` + `tests/skip_reference_policy.py`: reason must include `ref:`, `issue:`, or `see` + token.

Current suite: no unconditional `@pytest.mark.skip` on tests (only policy copy in that module).

## `pytest.skip(...)` (runtime)

All known call sites include `(ref: cleanup-skipped-legacy-tests)` in the reason string. Files include integration prompt-alignment tests, `test_rules_operations.py`, `test_python_adapter.py`, `test_check_async_tests_script.py`, `test_implement_select_explicit_plan_prompt.py`, and related integration modules.

**Category:** B (optional resources / minimal tree / submodule absent).

## `@pytest.mark.skipif`

| Location | Condition | Reason | Category |
| --- | --- | --- | --- |
| `tests/unit/test_structure_manager.py` | non-Windows | Unix-only test | C |

## `@pytest.mark.xfail`

None found under `tests/` as of last audit (grep `xfail`).

## Related implementation

- Skip reference policy: `tests/skip_reference_policy.py`
- Quality summary `skipped_tests` + trend warning: `parse_pytest_output` in `python_adapter_parsing.py`, cache `.cortex/.cache/last_pytest_skipped_count.json` (gitignored via `.cache` rule)
