"""Unit tests for early parameter validation in update_memory_bank.

Covers fix for the progress_append/active_context_append shape mismatch:
the dispatcher now catches wrong parameters before delegating to
append_entry_impl, returning a clear error instead of a silent no-op.
"""

from __future__ import annotations

import json

from cortex.tools.plans.update_memory_bank import (
    UpdateRequest,
    validate_append_op_params,
)


def _make_request(**kwargs: object) -> UpdateRequest:
    defaults: dict[str, object] = {
        "operation": "progress_append",
        "section": None,
        "entry_text": None,
        "position": "last",
        "change_description": None,
        "entry_contains": None,
        "section_heading_contains": None,
        "date_str": None,
        "title": None,
        "summary": None,
        "operation_type": None,
        "skip_classification": False,
    }
    defaults.update(kwargs)
    return UpdateRequest(**defaults)  # type: ignore[arg-type]


class TestProgressAppendValidation:
    def test_missing_both_returns_error(self) -> None:
        req = _make_request(operation="progress_append", date_str=None, entry_text=None)
        result = validate_append_op_params(req)
        assert result is not None
        data = json.loads(result)
        assert data["status"] == "error"
        assert "entry_text" in data["message"]

    def test_missing_entry_text_only_returns_error(self) -> None:
        req = _make_request(
            operation="progress_append", date_str="2026-04-16", entry_text=None
        )
        result = validate_append_op_params(req)
        assert result is not None
        data = json.loads(result)
        assert data["status"] == "error"

    def test_missing_date_str_only_returns_error(self) -> None:
        req = _make_request(
            operation="progress_append", date_str=None, entry_text="some work done"
        )
        result = validate_append_op_params(req)
        assert result is not None
        data = json.loads(result)
        assert data["status"] == "error"

    def test_wrong_params_title_summary_returns_helpful_error(self) -> None:
        """Passing title/summary to progress_append produces a clear hint."""
        req = _make_request(
            operation="progress_append",
            date_str=None,
            entry_text=None,
            title="My work",
            summary="Did things",
        )
        result = validate_append_op_params(req)
        assert result is not None
        data = json.loads(result)
        assert "active_context_append" in data["message"]

    def test_valid_params_returns_none(self) -> None:
        req = _make_request(
            operation="progress_append",
            date_str="2026-04-16",
            entry_text="Implemented X",
        )
        assert validate_append_op_params(req) is None


class TestActiveContextAppendValidation:
    def test_missing_all_returns_error(self) -> None:
        req = _make_request(
            operation="active_context_append",
            date_str=None,
            title=None,
            summary=None,
        )
        result = validate_append_op_params(req)
        assert result is not None
        data = json.loads(result)
        assert data["status"] == "error"
        assert "title" in data["message"]

    def test_missing_title_returns_error(self) -> None:
        req = _make_request(
            operation="active_context_append",
            date_str="2026-04-16",
            title=None,
            summary="summary text",
        )
        result = validate_append_op_params(req)
        assert result is not None

    def test_wrong_params_entry_text_returns_helpful_error(self) -> None:
        """Passing entry_text to active_context_append hints at progress_append."""
        req = _make_request(
            operation="active_context_append",
            date_str=None,
            title=None,
            summary=None,
            entry_text="I did some work",
        )
        result = validate_append_op_params(req)
        assert result is not None
        data = json.loads(result)
        assert "progress_append" in data["message"]

    def test_valid_params_returns_none(self) -> None:
        req = _make_request(
            operation="active_context_append",
            date_str="2026-04-16",
            title="Completed X",
            summary="Details about X",
        )
        assert validate_append_op_params(req) is None


class TestNonAppendOpsSkipped:
    def test_roadmap_op_not_validated(self) -> None:
        req = _make_request(operation="roadmap_add")
        assert validate_append_op_params(req) is None

    def test_log_op_not_validated(self) -> None:
        req = _make_request(operation="log_append")
        assert validate_append_op_params(req) is None
