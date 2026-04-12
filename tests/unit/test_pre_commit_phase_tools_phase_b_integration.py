"""Integration tests for execute_pre_commit_checks(phase='B')."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.execution.pre_commit_tools import execute_pre_commit_checks
from tests.unit.pre_commit_phase_tools_support import (
    get_checks_list,
    phase_b_roadmap_payload,
    phase_b_timestamps_payload,
    run_phase_b_for_partial_without_pending,
    run_phase_b_with_validate_mocks,
)


@pytest.fixture(autouse=True)
def _disable_detached_mode():  # type: ignore[misc]  # noqa: ANN202
    """Phase tests exercise the inline runners; disable detached mode."""
    with patch(
        "cortex.tools.execution.pre_commit_detached.DETACHED_ENABLED",
        False,
    ):
        yield


class TestRunDocsAndMemoryBankSync:
    """Tests for execute_pre_commit_checks(phase='B') (Phase B docs/memory sync)."""

    @pytest.fixture(autouse=True)
    def _patch_roadmap_progress_consistency(self):  # type: ignore[misc]  # noqa: ANN202
        """Isolate tests from workspace progress/roadmap PARTIAL vs PENDING drift."""
        with patch(
            "cortex.tools.execution.pre_commit_docs_memory_helpers._roadmap_progress_consistency_violations",
            new_callable=AsyncMock,
            return_value=[],
        ):
            yield

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Docs/memory phase passes when both validations are valid."""
        result = await run_phase_b_with_validate_mocks(
            phase_b_timestamps_payload(valid=True),
            phase_b_roadmap_payload(valid=True),
        )
        assert result["status"] == "success"
        assert result["docs_phase_passed"] is True
        check_names = {str(e.get("name", "")) for e in get_checks_list(result)}
        assert "timestamps" in check_names
        assert "roadmap_sync" in check_names
        assert "roadmap_progress_consistency" in check_names

    @pytest.mark.asyncio
    async def test_sets_flag_when_timestamps_invalid(self) -> None:
        """docs_phase_passed is False when timestamps report errors."""
        result = await run_phase_b_with_validate_mocks(
            phase_b_timestamps_payload(
                valid=False, total_invalid_format=2, total_invalid_with_time=1
            ),
            phase_b_roadmap_payload(valid=True),
        )
        assert result["status"] == "success"
        assert result["docs_phase_passed"] is False
        ts_entry = next(
            (e for e in get_checks_list(result) if e.get("name") == "timestamps"),
            None,
        )
        assert ts_entry is not None
        assert ts_entry.get("status") == "error"
        assert ts_entry.get("errors") == 3

    @pytest.mark.asyncio
    async def test_reports_tool_error(self) -> None:
        """Tool-level validation error is surfaced with status=error."""
        timestamps_payload = {
            "status": "error",
            "error": "roadmap missing",
        }
        roadmap_payload = {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": True,
            "summary": {
                "missing_entries_count": 0,
                "invalid_references_count": 0,
                "completed_entries_count": 0,
                "warnings_count": 0,
            },
        }

        with patch(
            "cortex.tools.execution.pre_commit_docs_memory_helpers.validate_from_parsed",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = [
                json.dumps(timestamps_payload),
                json.dumps(roadmap_payload),
            ]
            result = await execute_pre_commit_checks(phase="B")

        assert result["status"] == "error"
        assert result["error_type"] == "DocsMemoryBankToolError"
        assert "underlying validation error" in str(result.get("error", ""))

    @pytest.mark.asyncio
    async def test_both_validations_fail(self) -> None:
        """Both timestamps and roadmap invalid sets docs_phase_passed=False."""
        result = await run_phase_b_with_validate_mocks(
            phase_b_timestamps_payload(valid=False, total_invalid_format=1),
            phase_b_roadmap_payload(
                valid=False,
                missing_entries_count=2,
                invalid_references_count=1,
                warnings_count=1,
            ),
        )
        assert result["status"] == "success"
        assert result["docs_phase_passed"] is False
        by_name = {str(e.get("name", "")): e for e in get_checks_list(result)}
        assert by_name["timestamps"].get("status") == "error"
        assert by_name["roadmap_sync"].get("status") == "error"
        assert by_name["roadmap_progress_consistency"].get("status") == "success"

    @pytest.mark.asyncio
    async def test_roadmap_sync_error_surfaces(self) -> None:
        """Roadmap sync tool error is surfaced correctly."""
        timestamps_payload = {
            "status": "success",
            "check_type": "timestamps",
            "valid": True,
            "total_invalid_format": 0,
            "total_invalid_with_time": 0,
        }
        roadmap_payload = {
            "status": "error",
            "error": "filesystem error",
        }

        with patch(
            "cortex.tools.execution.pre_commit_docs_memory_helpers.validate_from_parsed",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = [
                json.dumps(timestamps_payload),
                json.dumps(roadmap_payload),
            ]
            result = await execute_pre_commit_checks(phase="B")

        assert result["status"] == "error"
        assert result["error_type"] == "DocsMemoryBankToolError"

    @pytest.mark.asyncio
    async def test_invalid_json_from_validation_handled(self) -> None:
        """Invalid JSON from validate() is gracefully handled as None."""
        with patch(
            "cortex.tools.execution.pre_commit_docs_memory_helpers.validate_from_parsed",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = ["NOT-JSON", "ALSO-NOT-JSON"]
            result = await execute_pre_commit_checks(phase="B")

        assert result["status"] == "success"
        assert result["docs_phase_passed"] is True
        names = [e.get("name") for e in get_checks_list(result)]
        assert names == ["roadmap_progress_consistency"]

    @pytest.mark.asyncio
    async def test_validation_result_not_dict_handled(self) -> None:
        """Valid JSON that is not a dict (e.g. array) from validate() is treated as None."""
        roadmap_payload = {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": True,
            "summary": {
                "missing_entries_count": 0,
                "invalid_references_count": 0,
                "completed_entries_count": 0,
                "warnings_count": 0,
            },
        }
        with patch(
            "cortex.tools.execution.pre_commit_docs_memory_helpers.validate_from_parsed",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = ["[1, 2]", json.dumps(roadmap_payload)]
            result = await execute_pre_commit_checks(phase="B")

        assert result["status"] == "success"
        assert result["docs_phase_passed"] is True
        check_names = {str(e.get("name", "")) for e in get_checks_list(result)}
        assert "roadmap_sync" in check_names
        assert "roadmap_progress_consistency" in check_names
        assert "timestamps" not in check_names

    @pytest.mark.asyncio
    async def test_roadmap_sync_with_warnings_only(self) -> None:
        """Roadmap sync passes with warnings but no errors."""
        result = await run_phase_b_with_validate_mocks(
            phase_b_timestamps_payload(valid=True),
            phase_b_roadmap_payload(valid=True, warnings_count=3),
        )
        assert result["status"] == "success"
        assert result["docs_phase_passed"] is True
        roadmap_entry = next(
            (e for e in get_checks_list(result) if e.get("name") == "roadmap_sync"),
            None,
        )
        assert roadmap_entry is not None
        assert roadmap_entry.get("warnings") == 3
        assert roadmap_entry.get("status") == "success"


class TestRunDocsAndMemoryBankProgressConsistency:
    """Phase B progress/roadmap consistency uses real memory-bank files (no autouse patch)."""

    @pytest.mark.asyncio
    async def test_docs_phase_warns_when_partial_without_pending(
        self, tmp_path: Path
    ) -> None:
        """Synthetic memory bank: PARTIAL/no-PENDING yields warning-only consistency."""
        result = await run_phase_b_for_partial_without_pending(tmp_path)
        assert result["status"] == "success"
        assert result["docs_phase_passed"] is True
        cons = next(
            e
            for e in get_checks_list(result)
            if e.get("name") == "roadmap_progress_consistency"
        )
        assert cons.get("status") == "success"
        assert cons.get("warnings") == 1
