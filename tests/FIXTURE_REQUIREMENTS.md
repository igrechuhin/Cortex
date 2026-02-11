# Test Fixture Requirements

This document lists required mock members for shared fixtures used by the test suite. Keeping these in sync with implementation code prevents test failures from incomplete mock configurations.

## optimization_config (Phase 4 tools)

Used by: `tests/tools/test_phase4_optimization.py` (`mock_managers` fixture), and by Phase 4 handlers (load_context, load_progressive_context, summarize_content, get_relevance_scores).

**Required members** (must be present as callable or with `return_value` on the mock):

| Member | Used by | Typical return |
|--------|--------|----------------|
| `get_token_budget` | phase4_context_operations, phase4_progressive_operations | `10000` |
| `get_max_token_budget` | phase4_context_operations, phase4_progressive_operations | `100000` |
| `get_reserve_for_response` | phase4_context_operations, phase4_progressive_operations | `10000` |
| `get_priority_order` | phase4_progressive_operations | `["file1.md", "file2.md"]` |
| `get_mandatory_files` | phase4_progressive_operations | `["file1.md"]` |
| `is_optimization_enabled` | phase4_optimization_handlers | `True` |
| `is_summarization_enabled` | phase4_summarization_operations | `True` |
| `get_summarization_target_reduction` | phase4_summarization_operations | `0.5` |
| `get_summarization_strategy` | phase4_summarization_operations | `"extract_key_sections"` |

Validation is performed by `tests/helpers/fixture_validator.validate_optimization_config_mock()`. The Phase 4 `mock_managers` fixture runs this validation at setup; if the mock is incomplete, the test fails with a clear message.

## mock_ctx (MCP Context logging)

Used by: Context logging tests (e.g. `test_context_logging_integration.py`), and any test that exercises code paths using `ctx.log()` or `ctx.report_progress()`.

**Required members**:

| Member | Type | Purpose |
|--------|------|--------|
| `log` | AsyncMock | Client-visible log messages |
| `report_progress` | AsyncMock | Progress updates |

Defined in `tests/conftest.py` as `mock_ctx` fixture.

## Usage context (ensure_usage_context)

When a tool uses `ensure_usage_context`, the handler may call `set_current_managers` / `set_current_project_root`. Tests that mock `get_managers` (or inject managers) and invoke such handlers should patch `set_current_managers` and `set_current_project_root` to no-op to avoid persisting real managers. See `tests/tools/test_consolidated.py` (`test_manage_file_metadata_success`) for the pattern.

## projectBrief schema (integration tests)

Integration tests that write to `projectBrief.md` must use content that includes the required schema sections: **Project Overview**, **Goals**, **Core Requirements**, **Success Criteria**. See session optimization review 2026-02-07 (schema vs tests) and `tests/integration/test_mcp_tools_integration.py` for valid examples.
