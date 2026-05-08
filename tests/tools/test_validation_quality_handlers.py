"""Split from test_validation_operations.py to keep file size under limits."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.validation.duplication import (
    handle_duplications_validation,
)
from cortex.tools.validation.quality import (
    handle_quality_validation,
    validate_quality_all_files,
    validate_quality_single_file,
)
from cortex.tools.validation.schema import (
    handle_schema_validation,
)
from tests.tools.validation_operations_support import (
    setup_handle_quality_validation_all_files_mocks,
    setup_handle_quality_validation_with_file_mocks,
    setup_validate_quality_all_files_success,
    setup_validate_quality_single_file_success,
)


class TestValidateQuality:
    """Test quality validation helpers."""

    @pytest.mark.asyncio
    async def test_validate_quality_single_file_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful quality validation for single file."""
        mock_index, mock_metrics = setup_validate_quality_single_file_success(
            tmp_path, mock_fs_manager
        )

        # Act
        result = await validate_quality_single_file(
            mock_fs_manager, mock_index, mock_metrics, tmp_path, "projectBrief.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "quality"
        assert result_data["file_name"] == "projectBrief.md"
        assert result_data["score"]["score"] == 85

    @pytest.mark.asyncio
    async def test_validate_quality_single_file_invalid_name(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test quality validation with invalid file name."""
        # Arrange
        mock_fs_manager.construct_safe_path.side_effect = ValueError("Invalid path")

        mock_index = MagicMock()
        mock_metrics = MagicMock()

        # Act
        result = await validate_quality_single_file(
            mock_fs_manager,
            mock_index,
            mock_metrics,
            tmp_path,
            "../../../../etc/passwd",
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid file name" in result_data["error"]

    @pytest.mark.asyncio
    async def test_validate_quality_single_file_not_found(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test quality validation when file does not exist."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        nonexistent = memory_bank_dir / "nonexistent.md"

        mock_fs_manager.construct_safe_path.return_value = nonexistent

        mock_index = MagicMock()
        mock_metrics = MagicMock()

        # Act
        result = await validate_quality_single_file(
            mock_fs_manager, mock_index, mock_metrics, tmp_path, "nonexistent.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "does not exist" in result_data["error"]

    @pytest.mark.asyncio
    async def test_validate_quality_all_files_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful quality validation for all files."""
        mock_index, mock_metrics, mock_detector = (
            setup_validate_quality_all_files_success(tmp_path, mock_fs_manager)
        )

        # Act
        result = await validate_quality_all_files(
            mock_fs_manager, mock_index, mock_metrics, mock_detector, tmp_path
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "quality"
        assert result_data["overall_score"] == 80
        assert result_data["health_status"] == "healthy"


class TestValidationHandlers:
    """Test validation handler functions."""

    @pytest.mark.asyncio
    async def test_handle_schema_validation_with_file(self, tmp_path: Path) -> None:
        """Test schema validation handler with specific file."""
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "schema_validator": MagicMock(),
        }

        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("Content")

        mock_managers["fs_manager"].construct_safe_path.return_value = test_file
        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        mock_managers["schema_validator"].validate_file = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(return_value={"valid": True, "errors": []})
            )
        )

        # Act
        result = await handle_schema_validation(
            mock_managers["fs_manager"],
            mock_managers["schema_validator"],
            tmp_path,
            "test.md",
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["file_name"] == "test.md"

    @pytest.mark.asyncio
    async def test_handle_schema_validation_all_files(self, tmp_path: Path) -> None:
        """Test schema validation handler for all files."""
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "schema_validator": MagicMock(),
        }

        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        mock_managers["schema_validator"].validate_file = AsyncMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"valid": True}))
        )

        # Act
        result = await handle_schema_validation(
            mock_managers["fs_manager"],
            mock_managers["schema_validator"],
            tmp_path,
            None,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "schema"
        assert "results" in result_data

    @pytest.mark.asyncio
    async def test_handle_duplications_validation(self, tmp_path: Path) -> None:
        """Test duplications validation handler."""
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "duplication_detector": MagicMock(),
            "validation_config": MagicMock(),
        }

        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        duplication_scan = MagicMock()
        duplication_scan.model_dump = MagicMock(return_value={"duplicates_found": 0})
        duplication_scan.duplicates_found = 0
        mock_managers["duplication_detector"].scan_all_files = AsyncMock(
            return_value=duplication_scan
        )
        mock_managers["validation_config"].get_duplication_threshold.return_value = 0.85

        # Act
        result = await handle_duplications_validation(
            mock_managers["fs_manager"],
            mock_managers["duplication_detector"],
            mock_managers["validation_config"],
            tmp_path,
            0.9,
            True,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "duplications"
        assert result_data["threshold"] == 0.9

    @pytest.mark.asyncio
    async def test_handle_quality_validation_with_file(self, tmp_path: Path) -> None:
        """Test quality validation handler with specific file."""
        mock_managers = setup_handle_quality_validation_with_file_mocks(tmp_path)

        # Act
        result = await handle_quality_validation(
            mock_managers["fs_manager"],
            mock_managers["metadata_index"],
            mock_managers["quality_metrics"],
            mock_managers["duplication_detector"],
            tmp_path,
            "test.md",
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["file_name"] == "test.md"

    @pytest.mark.asyncio
    async def test_handle_quality_validation_all_files(self, tmp_path: Path) -> None:
        """Test quality validation handler for all files."""
        mock_managers = setup_handle_quality_validation_all_files_mocks(tmp_path)

        # Act
        result = await handle_quality_validation(
            mock_managers["fs_manager"],
            mock_managers["metadata_index"],
            mock_managers["quality_metrics"],
            mock_managers["duplication_detector"],
            tmp_path,
            None,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "quality"
