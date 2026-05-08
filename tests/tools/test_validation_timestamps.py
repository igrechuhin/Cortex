"""Split from test_validation_operations.py to keep file size under limits."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.validation.helpers import (
    read_all_memory_bank_files,
)
from cortex.tools.validation.timestamps import handle_timestamps_validation
from cortex.validation.timestamp_validator import (
    validate_timestamps_all_files,
    validate_timestamps_single_file,
)
from tests.tools.validation_operations_support import (
    setup_timestamps_all_files_valid,
    setup_timestamps_all_files_with_violations,
)


class TestValidateTimestamps:
    """Test timestamp validation functions."""

    @pytest.mark.asyncio
    async def test_validate_timestamps_single_file_valid(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test timestamp validation with valid YYYY-MM-DD date-only timestamps."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "activeContext.md"
        content = (
            "# Active Context\n\n"
            "## Current Focus (2026-01-14)\n\n"
            "Some content here with timestamp 2026-01-15.\n"
        )
        _ = test_file.write_text(content)

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(return_value=(content, None))

        # Act
        result = await validate_timestamps_single_file(
            mock_fs_manager, tmp_path, "activeContext.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "timestamps"
        assert result_data["file_name"] == "activeContext.md"
        assert result_data["valid"] is True
        assert result_data["valid_count"] >= 2

    @pytest.mark.asyncio
    async def test_validate_timestamps_single_file_invalid_format(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test timestamp validation with invalid datetime formats."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "progress.md"
        content = (
            "# Progress\n\n"
            "- ✅ Feature X - COMPLETE (2026-01-13 12:00)\n"
            "- ✅ Feature Y - COMPLETE (2026-01-13T12:00:00)\n"
        )
        _ = test_file.write_text(content)

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(return_value=(content, None))

        # Act
        result = await validate_timestamps_single_file(
            mock_fs_manager, tmp_path, "progress.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "timestamps"
        assert result_data["invalid_format_count"] > 0
        assert result_data["valid"] is False
        assert len(result_data["violations"]) > 0

    @pytest.mark.asyncio
    async def test_validate_timestamps_single_file_invalid_datetime_and_non_standard_date(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test timestamp validation: invalid datetime (ValueError) and non-standard date format."""
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "progress.md"
        content = (
            "# Progress\n\n"
            "2026-01-20\n"
            "- Invalid day: 2026-02-30T12:00\n"
            "- Non-standard: 01/15/2026\n"
            "- Date part of datetime: 2026-01-15 2026-01-15T10:00\n"
        )
        _ = test_file.write_text(content)

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(return_value=(content, None))

        result = await validate_timestamps_single_file(
            mock_fs_manager, tmp_path, "progress.md"
        )

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "timestamps"
        assert result_data["valid"] is False
        assert (
            result_data["invalid_format_count"] > 0
            or len(result_data["violations"]) > 0
        )

    @pytest.mark.asyncio
    async def test_validate_timestamps_single_file_with_timezone(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test timestamp validation with timezone components."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "roadmap.md"
        content = (
            "# Roadmap\n\n"
            "- ✅ Feature A - COMPLETE (2026-01-13T12:00Z)\n"
            "- ✅ Feature B - COMPLETE (2026-01-13T12:00+05:00)\n"
        )
        _ = test_file.write_text(content)

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(return_value=(content, None))

        # Act
        result = await validate_timestamps_single_file(
            mock_fs_manager, tmp_path, "roadmap.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["invalid_format_count"] > 0
        assert result_data["valid"] is False

    @pytest.mark.asyncio
    async def test_validate_timestamps_single_file_not_found(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test timestamp validation when file doesn't exist."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "nonexistent.md"

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(return_value=("", None))

        # Act
        result = await validate_timestamps_single_file(
            mock_fs_manager, tmp_path, "nonexistent.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "does not exist" in result_data["error"]

    @pytest.mark.asyncio
    async def test_validate_timestamps_single_file_invalid_name(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test timestamp validation with invalid file name."""
        # Arrange
        mock_fs_manager.construct_safe_path.side_effect = ValueError(
            "Invalid file name: ../etc/passwd"
        )

        # Act
        result = await validate_timestamps_single_file(
            mock_fs_manager, tmp_path, "../etc/passwd"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid file name" in result_data["error"]

    @pytest.mark.asyncio
    async def test_validate_timestamps_all_files_valid(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test timestamp validation across all files with valid timestamps."""
        setup_timestamps_all_files_valid(tmp_path, mock_fs_manager)

        # Act
        result = await validate_timestamps_all_files(
            mock_fs_manager, tmp_path, read_all_memory_bank_files
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "timestamps"
        assert result_data["files_valid"] is True
        assert result_data["total_valid"] >= 2
        assert result_data["total_invalid_format"] == 0
        assert result_data["total_invalid_with_time"] == 0

    @pytest.mark.asyncio
    async def test_validate_timestamps_all_files_with_violations(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test timestamp validation across all files with violations."""
        setup_timestamps_all_files_with_violations(tmp_path, mock_fs_manager)

        # Act
        result = await validate_timestamps_all_files(
            mock_fs_manager, tmp_path, read_all_memory_bank_files
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "timestamps"
        assert result_data["files_valid"] is False
        assert result_data["total_invalid_format"] > 0
        assert "progress.md" in result_data["results"]
        assert "roadmap.md" in result_data["results"]


class TestHandleTimestampsValidation:
    """Test handle_timestamps_validation MCP tool handler."""

    @pytest.mark.asyncio
    async def test_handle_timestamps_validation_single_file(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test handle_timestamps_validation with file_name parameter."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "activeContext.md"
        content = "# Active Context\n\n## Current Focus (2026-01-14)\n"
        _ = test_file.write_text(content)

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(return_value=(content, None))

        # Act
        result = await handle_timestamps_validation(
            mock_fs_manager, tmp_path, "activeContext.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "timestamps"
        assert result_data["file_name"] == "activeContext.md"

    @pytest.mark.asyncio
    async def test_handle_timestamps_validation_all_files(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test handle_timestamps_validation without file_name parameter."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        _ = (memory_bank_dir / "activeContext.md").write_text(
            "# Active Context\n\n## Current Focus (2026-01-14)\n"
        )

        async def mock_list_files(directory: Path) -> list[Path]:
            return [memory_bank_dir / "activeContext.md"]

        mock_fs_manager.list_files = AsyncMock(side_effect=mock_list_files)
        mock_fs_manager.read_file = AsyncMock(
            return_value=("# Active Context\n\n## Current Focus (2026-01-14)\n", None)
        )

        # Act
        result = await handle_timestamps_validation(mock_fs_manager, tmp_path, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "timestamps"
