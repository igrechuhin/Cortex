from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.phase1_foundation_cleanup import cleanup_metadata_index
from tests.helpers.managers import make_test_managers


@pytest.mark.asyncio
class TestCleanupMetadataIndex:
    async def test_cleanup_metadata_index_when_no_stale_files_returns_success(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        mock_index = AsyncMock()
        mock_index.validate_index_consistency = AsyncMock(return_value=[])

        with (
            patch(
                "cortex.tools.phase1_foundation_cleanup.get_project_root",
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.phase1_foundation_cleanup.get_managers",
                return_value=make_test_managers(index=mock_index),
            ),
        ):
            # Act
            result = await cleanup_metadata_index(project_root=None, dry_run=False)

        # Assert
        assert result.status == "success"
        assert result.stale_files_found == 0
        assert result.entries_cleaned == 0
        assert "No stale entries found" in result.message

    async def test_cleanup_metadata_index_when_stale_files_and_dry_run_reports_no_changes(  # noqa: E501
        self, tmp_path: Path
    ) -> None:
        # Arrange
        stale_files = ["missing.md", "old.md"]
        mock_index = AsyncMock()
        mock_index.validate_index_consistency = AsyncMock(return_value=stale_files)
        mock_index.cleanup_stale_entries = AsyncMock(return_value=99)

        with (
            patch(
                "cortex.tools.phase1_foundation_cleanup.get_project_root",
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.phase1_foundation_cleanup.get_managers",
                return_value=make_test_managers(index=mock_index),
            ),
        ):
            # Act
            result = await cleanup_metadata_index(project_root=None, dry_run=True)

        # Assert
        assert result.status == "success"
        assert result.dry_run is True
        assert result.stale_files_found == 2
        assert result.stale_files == stale_files
        assert "Would clean 2 stale entries" in result.message

    async def test_cleanup_metadata_index_when_exception_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        with (
            patch(
                "cortex.tools.phase1_foundation_cleanup.get_project_root",
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.phase1_foundation_cleanup.get_managers",
                side_effect=RuntimeError("boom"),
            ),
        ):
            # Act
            result = await cleanup_metadata_index(project_root=None, dry_run=False)

        # Assert
        assert result.status == "error"
        assert result.error == "boom"
        assert result.error_type == "RuntimeError"
