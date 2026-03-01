from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.foundation_cleanup import cleanup_metadata_index
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
                "cortex.tools.foundation_cleanup.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.foundation_cleanup.get_managers",
                return_value=make_test_managers(index=mock_index),
            ),
        ):
            # Act
            result = await cleanup_metadata_index(dry_run=False)

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
                "cortex.tools.foundation_cleanup.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.foundation_cleanup.get_managers",
                return_value=make_test_managers(index=mock_index),
            ),
        ):
            # Act
            result = await cleanup_metadata_index(dry_run=True)

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
                "cortex.tools.foundation_cleanup.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.foundation_cleanup.get_managers",
                side_effect=RuntimeError("boom"),
            ),
        ):
            # Act
            result = await cleanup_metadata_index(dry_run=False)

        # Assert
        assert result.status == "error"
        assert result.error == "boom"
        assert result.error_type == "RuntimeError"


@pytest.mark.asyncio
class TestCleanupMetadataIndexContextLogging:
    """Test cleanup_metadata_index uses log_client when ctx is passed."""

    async def test_cleanup_metadata_index_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, cleanup_metadata_index logs start and completion."""
        mock_ctx = AsyncMock()
        mock_index = AsyncMock()
        mock_index.validate_index_consistency = AsyncMock(return_value=[])

        with (
            patch(
                "cortex.tools.foundation_cleanup.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.foundation_cleanup.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.foundation_cleanup.get_managers",
                return_value=make_test_managers(index=mock_index),
            ),
        ):
            result = await cleanup_metadata_index(dry_run=False, ctx=mock_ctx)

        assert result.status == "success"
        args_list = [c[0] for c in mock_log.call_args_list]
        levels_and_messages = [(a[1], a[2]) for a in args_list]
        assert ("info", "cleanup_metadata_index: starting") in levels_and_messages
        assert ("info", "cleanup_metadata_index: completed") in levels_and_messages

    async def test_cleanup_metadata_index_calls_log_client_error_on_exception_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When exception and ctx passed, cleanup_metadata_index logs error."""
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.foundation_cleanup.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.foundation_cleanup.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.foundation_cleanup.get_managers",
                side_effect=RuntimeError("init failed"),
            ),
        ):
            result = await cleanup_metadata_index(dry_run=False, ctx=mock_ctx)

        assert result.status == "error"
        assert any(
            c[0][1] == "error" and "failed" in (c[0][2] or "")
            for c in mock_log.call_args_list
            if len(c[0]) >= 3
        )
