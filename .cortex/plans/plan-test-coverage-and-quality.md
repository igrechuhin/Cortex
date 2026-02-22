# Plan: Test Coverage Expansion & Quality Improvement

## Status: PLANNED

## Priority: P0 (Critical)

## Created: 2026-02-21

## Effort: 2–3 sprints

## Motivation

Comprehensive review (2026-02-21) found critical test gaps:

- **4 modules completely untested**: `services/` (15 files), `discovery/` (5 files), `guides/` (5 files), `script_promotion/` (6 files)
- **Zero `@pytest.mark.parametrize`** usage across entire 230-file test suite
- **46 `await asyncio.sleep()` calls** creating flakiness risk
- **`tool_helpers.py` at 11,796 lines** — needs splitting
- **No E2E workflow tests** — integration tests are narrowly scoped
- **58 TODO/FIXME comments** in test code
- **Low module-level coverage**: `tools/` at 10%, `core/` at 5.9%, `refactoring/` at 12.9%

---

## Step 1: Add Tests for Untested Modules (P0)

### 1a: `src/cortex/services/` (15 files) — COMPLETED 2026-02-22

- Create `tests/services/` directory — done
- Write unit tests for each service file (framework adapters) — done: test_models, test_language_detector, framework_adapters/test_base, test_detection, test_stub_adapter (32 tests)
- Target: 90%+ coverage for each file — in progress (existing unit tests + new tests/services/ cover services package)
- Focus on: input validation, error paths, async behavior

### 1b: `src/cortex/discovery/` (5 files) — COMPLETED 2026-02-22

- Create `tests/discovery/` directory — done
- Test discovery logic, file scanning, pattern matching — done: test_tool_registry, test_search_interface, test_use_case_mapper, test_recommendation_engine (30 tests)
- Test edge cases: empty directories (missing/empty scripts dir, private modules, sorted stems)

### 1c: `src/cortex/guides/` (5 files, 0 tests) — COMPLETED 2026-02-22

- Create `tests/guides/` directory — done
- Test guide generation, template rendering, content formatting — done: test_guide_content.py (GUIDE constants, content/formatting per guide), test_resources_guides.py (GUIDES dict integration)

### 1d: `src/cortex/script_promotion/` (6 files) — COMPLETED 2026-02-22

- Create `tests/script_promotion/` directory — done
- Test promotion workflow, validation, rollback — done: test_models, test_script_validator, test_documentation_generator, test_script_integrator, test_tool_converter (25 tests)

**Acceptance criteria:** All 31 previously-untested files have tests. Coverage ≥ 90% for each.

---

## Step 2: Add Parametrized Tests (P1) — COMPLETED 2026-02-22

### 2a: Language Adapter Tests — COMPLETED

Consolidated detection and adapter init into parametrized tests. Detection: `tests/services/framework_adapters/test_detection.py` (parametrized over 7 languages). Adapter init: `tests/unit/test_framework_adapters_parametrized.py` (8 adapters × 2 init tests). Original pattern:

```python
@pytest.mark.parametrize("language", ["python", "java", "kotlin", "typescript", "go", "rust", "swift"])
async def test_adapter_detects_language(language: str, ...) -> None:
    adapter = get_adapter(language)
    result = await adapter.detect()
    assert result.language == language
```

### 2b: Tool Operation Parametrization — COMPLETED

Added `test_manage_file_invalid_file_name_returns_error_for_operation` parametrized over `["read", "write", "metadata"]` in `tests/tools/test_file_operations.py`. Original pattern:

```python
@pytest.mark.parametrize("operation,expected_status", [
    ("create", "created"),
    ("update", "updated"),
    ("delete", "deleted"),
])
```

### 2c: Edge Case Parametrization — COMPLETED

Added edge-case parametrized tests: `test_manage_file_edge_case_file_name_returns_error` (empty, very_long_path, unicode, whitespace_only, dot_only) and guide tests `test_guide_has_reasonable_length`, `test_guide_contains_no_null_bytes`. Original scope:

- Unicode filenames, empty strings, very long paths
- Boundary values for token counts, file sizes
- Invalid/malformed JSON, YAML, TOML inputs
- Concurrent access patterns

**Acceptance criteria:** ≥ 50 parametrized test cases. 7 language adapter tests consolidated into 1 parametrized file.

---

## Step 3: Eliminate `asyncio.sleep()` Flakiness (P1) — COMPLETED 2026-02-22

**46 instances** of `await asyncio.sleep()` create time-dependent tests.

**Approach:**

1. Audit all 46 uses — categorize as:
   - **Removable**: Sleep is unnecessary (just waiting for sync operations)
   - **Mockable**: Replace with `AsyncMock` or `freezegun`
   - **Justified**: True timing tests (mark with `@pytest.mark.slow`)
2. For timing-dependent tests, use `asyncio.Event` or `asyncio.Condition` instead of `sleep`
3. Mark remaining slow tests with `@pytest.mark.slow`

**Done:** Removed or mocked sleeps in test_core_utilities, test_security_enhancements, test_lazy_manager, test_mcp_stability_connection_closure, and test_mcp_stability_timeouts (Event.wait() or AsyncMock). Replaced timeout-style sleeps with `asyncio.Event().wait()`. Marked timing-dependent tests in test_file_watcher, test_security, test_task_locking, test_metadata_index with `@pytest.mark.slow`. All tests pass; slow marker registered in pytest.ini/conftest.

**Acceptance criteria:** ≤ 5 `asyncio.sleep()` calls remaining (all justified). All slow tests marked.

---

## Step 4: Split `tool_helpers.py` (P1)

**11,796 lines** — largest file in the project (test utility monster).

**Split into:**

| New File | Purpose |
|----------|---------|
| `helpers/manager_mocks.py` | Mock manager factories and fixtures |
| `helpers/file_fixtures.py` | File/path/directory test fixtures |
| `helpers/assertion_helpers.py` | Custom assertion functions |
| `helpers/tool_call_helpers.py` | Tool invocation and response helpers |
| `helpers/data_generators.py` | Test data generation factories |

**Acceptance criteria:** `tool_helpers.py` removed. Each helper module ≤ 400 lines. All existing tests pass unchanged.

---

## Step 5: Add E2E Workflow Tests (P2)

Currently missing: tests that exercise complete user workflows end-to-end.

**Create `tests/e2e/` with:**

1. **`test_session_lifecycle.py`** — session_start → load_context → work → compact_session
2. **`test_memory_bank_workflow.py`** — create project → manage_file → validate → query
3. **`test_commit_pipeline.py`** — code change → pre-commit checks → fix issues → commit
4. **`test_plan_workflow.py`** — create plan → update steps → archive
5. **`test_refactoring_workflow.py`** — detect pattern → propose refactoring → execute → validate

**Acceptance criteria:** 5+ E2E tests covering primary user workflows. Each exercises ≥ 3 MCP tools in sequence.

---

## Step 6: Address TODO/FIXME Comments (P2)

**58 TODO/FIXME comments** in test code.

**Approach:**

1. Categorize each TODO: implement, remove (obsolete), or convert to GitHub issue
2. Implement trivial TODOs inline
3. Create issues for non-trivial TODOs with clear descriptions
4. Remove obsolete TODOs

**Acceptance criteria:** ≤ 10 TODOs remaining (all with linked issues).

---

## Step 7: Increase Module-Level Test Coverage (P2)

Modules with low test-to-source ratio:

| Module | Source Files | Test Files | Ratio | Target |
|--------|-------------|------------|-------|--------|
| `tools/` | 98 | 10 | 10% | ≥ 50% |
| `core/` | 51 | 3 | 5.9% | ≥ 40% |
| `refactoring/` | 31 | 4 | 12.9% | ≥ 40% |

**Approach:**

1. Identify highest-risk untested tool files (most complex, most used)
2. Write focused unit tests for critical paths
3. Prioritize error handling and edge cases over happy paths (happy paths likely covered by integration tests)

**Acceptance criteria:** Overall test coverage ≥ 93%. Each module ratio ≥ 30%.

---

## Verification

After all steps:

1. `pytest --tb=short` — all tests pass
2. `pytest --cov=src/cortex --cov-report=term-missing` — coverage ≥ 93%
3. `pytest -m slow` runs separately (slow tests identified)
4. No `asyncio.sleep()` in non-slow tests
5. `tool_helpers.py` no longer exists
6. All previously-untested modules have tests
