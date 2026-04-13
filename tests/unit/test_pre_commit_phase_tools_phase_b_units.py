"""Unit tests for docs/memory bank helper functions used by phase B."""

from __future__ import annotations

from typing import cast

from cortex.core.models import JsonDict
from cortex.tools.execution.pre_commit_docs_memory_helpers import (
    build_docs_memory_bank_model as _build_docs_memory_bank_model,
)
from cortex.tools.execution.pre_commit_docs_memory_helpers import (
    build_docs_memory_bank_summaries as _build_docs_memory_bank_summaries,
)
from cortex.tools.execution.pre_commit_docs_memory_helpers import (
    build_roadmap_sync_summary as _build_roadmap_sync_summary,
)
from cortex.tools.execution.pre_commit_docs_memory_helpers import (
    build_timestamps_summary as _build_timestamps_summary,
)
from cortex.tools.execution.pre_commit_docs_memory_helpers import (
    compute_docs_memory_bank_passed as _compute_docs_memory_bank_passed,
)


class TestDocsMemoryHelperFunctions:
    """Unit tests for pure helper functions in pre_commit_docs_memory_helpers."""

    def test_compute_passed_both_none(self) -> None:
        """Both None results default to passed."""
        assert _compute_docs_memory_bank_passed(None, None, []) is True

    def test_compute_passed_timestamps_invalid(self) -> None:
        """Fails when timestamps are invalid."""
        ts = cast(JsonDict, {"valid": False})
        assert _compute_docs_memory_bank_passed(ts, None, []) is False

    def test_compute_passed_roadmap_invalid(self) -> None:
        """Fails when roadmap_sync is invalid."""
        rm = cast(JsonDict, {"valid": False})
        assert _compute_docs_memory_bank_passed(None, rm, []) is False

    def test_compute_passed_consistency_violation(self) -> None:
        """Consistency violations are errors — phase fails when violations present."""
        assert _compute_docs_memory_bank_passed(None, None, ["drift"]) is False

    def test_build_timestamps_summary_none(self) -> None:
        """Returns None when timestamps_result is None."""
        assert _build_timestamps_summary(None) is None

    def test_build_timestamps_summary_valid(self) -> None:
        """Builds success summary for valid timestamps."""
        ts = cast(
            JsonDict,
            {
                "valid": True,
                "total_invalid_format": 0,
                "total_invalid_with_time": 0,
            },
        )
        summary = _build_timestamps_summary(ts)
        assert summary is not None
        assert summary.status == "success"
        assert summary.errors is None

    def test_build_timestamps_summary_invalid(self) -> None:
        """Builds error summary with counts for invalid timestamps."""
        ts = cast(
            JsonDict,
            {
                "valid": False,
                "total_invalid_format": 3,
                "total_invalid_with_time": 2,
            },
        )
        summary = _build_timestamps_summary(ts)
        assert summary is not None
        assert summary.status == "error"
        assert summary.errors == 5

    def test_build_roadmap_sync_summary_none(self) -> None:
        """Returns None when roadmap_result is None."""
        assert _build_roadmap_sync_summary(None) is None

    def test_build_roadmap_sync_summary_valid(self) -> None:
        """Builds success summary for valid roadmap sync."""
        rm = cast(
            JsonDict,
            {
                "valid": True,
                "summary": {
                    "missing_entries_count": 0,
                    "invalid_references_count": 0,
                    "completed_entries_count": 0,
                    "warnings_count": 0,
                },
            },
        )
        summary = _build_roadmap_sync_summary(rm)
        assert summary is not None
        assert summary.status == "success"
        assert summary.errors is None

    def test_build_roadmap_sync_summary_with_errors(self) -> None:
        """Builds error summary with aggregated error count."""
        rm = cast(
            JsonDict,
            {
                "valid": False,
                "summary": {
                    "missing_entries_count": 1,
                    "invalid_references_count": 2,
                    "completed_entries_count": 0,
                    "warnings_count": 5,
                },
            },
        )
        summary = _build_roadmap_sync_summary(rm)
        assert summary is not None
        assert summary.status == "error"
        assert summary.errors == 3
        assert summary.warnings == 5

    def test_build_roadmap_sync_summary_non_dict_summary(self) -> None:
        """Handles non-dict summary field gracefully."""
        rm = cast(JsonDict, {"valid": False, "summary": "not a dict"})
        summary = _build_roadmap_sync_summary(rm)
        assert summary is not None
        assert summary.status == "error"
        assert summary.errors is None

    def test_build_docs_memory_bank_summaries_includes_consistency(self) -> None:
        """Always appends roadmap_progress_consistency summary."""
        summaries = _build_docs_memory_bank_summaries(None, None, [])
        assert len(summaries) == 1
        assert summaries[0].name == "roadmap_progress_consistency"
        assert summaries[0].status == "success"

    def test_build_docs_memory_bank_model_success(self) -> None:
        """Builds success model with correct shape."""
        ts = cast(
            JsonDict,
            {
                "status": "success",
                "valid": True,
                "total_invalid_format": 0,
                "total_invalid_with_time": 0,
            },
        )
        rm = cast(
            JsonDict,
            {
                "status": "success",
                "valid": True,
                "summary": {
                    "missing_entries_count": 0,
                    "invalid_references_count": 0,
                    "completed_entries_count": 0,
                    "warnings_count": 0,
                },
            },
        )
        model = _build_docs_memory_bank_model(ts, rm, [])
        assert model["status"] == "success"
        assert model["docs_phase_passed"] is True
        checks_raw = cast(JsonDict, model).get("checks")
        assert isinstance(checks_raw, list)
        assert len(checks_raw) == 3

    def test_build_docs_memory_bank_model_error(self) -> None:
        """Builds error model when tool error detected."""
        ts = cast(JsonDict, {"status": "error", "error": "crash"})
        model = _build_docs_memory_bank_model(ts, None, [])
        assert model["status"] == "error"
        assert model["error_type"] == "DocsMemoryBankToolError"

    def test_build_docs_memory_bank_model_both_none(self) -> None:
        """Builds success model when both inputs are None."""
        model = _build_docs_memory_bank_model(None, None, [])
        assert model["status"] == "success"
        assert model["docs_phase_passed"] is True
        checks_raw = cast(JsonDict, model).get("checks")
        assert isinstance(checks_raw, list)
        assert len(checks_raw) == 1
        row0 = checks_raw[0]
        assert isinstance(row0, dict)
        assert row0.get("name") == "roadmap_progress_consistency"

    def test_build_docs_memory_bank_model_consistency_failure(self) -> None:
        """Consistency violations are errors — phase fails even when other checks pass."""
        ts = cast(JsonDict, {"status": "success", "valid": True})
        rm = cast(
            JsonDict,
            {
                "status": "success",
                "valid": True,
                "summary": {
                    "missing_entries_count": 0,
                    "invalid_references_count": 0,
                    "completed_entries_count": 0,
                    "warnings_count": 0,
                },
            },
        )
        model = _build_docs_memory_bank_model(ts, rm, ["roadmap drift"])
        assert model["docs_phase_passed"] is False
        checks_raw = cast(JsonDict, model).get("checks")
        assert isinstance(checks_raw, list)
        cons_row = next(
            cast(JsonDict, c)
            for c in checks_raw
            if isinstance(c, dict) and c.get("name") == "roadmap_progress_consistency"
        )
        assert cons_row.get("status") == "error"
        assert cons_row.get("errors") == 1
