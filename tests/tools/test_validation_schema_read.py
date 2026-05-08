"""Split from test_validation_operations.py to keep file size under limits."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.validation.helpers import (
    read_all_memory_bank_files,
)
from cortex.tools.validation.schema import (
    validate_schema_all_files,
    validate_schema_single_file,
)
from tests.tools.validation_operations_support import (
    setup_schema_all_files_success,
)


class TestValidateSchemaHelpers:
    """Test schema validation helper functions."""

    @pytest.mark.asyncio
    async def test_validate_schema_single_file_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful single file schema validation."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "projectBrief.md"
        _ = test_file.write_text("# Test content\n## Section 1\n")

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(
            return_value=("# Test content\n## Section 1\n", None)
        )

        mock_validator = MagicMock()
        mock_validator.validate_file = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(
                    return_value={"valid": True, "errors": [], "warnings": []}
                )
            )
        )

        # Act
        result = await validate_schema_single_file(
            mock_fs_manager, mock_validator, tmp_path, "projectBrief.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "schema"
        assert result_data["file_name"] == "projectBrief.md"
        assert result_data["validation"]["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_schema_single_file_invalid_name(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test schema validation with invalid file name."""
        # Arrange
        mock_fs_manager.construct_safe_path.side_effect = ValueError(
            "Path traversal detected"
        )

        mock_validator = MagicMock()

        # Act
        result = await validate_schema_single_file(
            mock_fs_manager, mock_validator, tmp_path, "../../../etc/passwd"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid file name" in result_data["error"]
        assert "Path traversal detected" in result_data["error"]

    @pytest.mark.asyncio
    async def test_validate_schema_single_file_permission_error(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test schema validation with permission error."""
        # Arrange
        mock_fs_manager.construct_safe_path.side_effect = PermissionError(
            "Access denied"
        )

        mock_validator = MagicMock()

        # Act
        result = await validate_schema_single_file(
            mock_fs_manager, mock_validator, tmp_path, "restricted.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid file name" in result_data["error"]
        assert "Access denied" in result_data["error"]

    @pytest.mark.asyncio
    async def test_validate_schema_single_file_not_found(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test schema validation when file does not exist."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        nonexistent_file = memory_bank_dir / "nonexistent.md"

        mock_fs_manager.construct_safe_path.return_value = nonexistent_file

        mock_validator = MagicMock()

        # Act
        result = await validate_schema_single_file(
            mock_fs_manager, mock_validator, tmp_path, "nonexistent.md"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "does not exist" in result_data["error"]

    @pytest.mark.asyncio
    async def test_validate_schema_all_files_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful all files schema validation."""
        mock_validator = setup_schema_all_files_success(tmp_path, mock_fs_manager)

        # Act
        result = await validate_schema_all_files(
            mock_fs_manager, mock_validator, tmp_path
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "schema"
        assert "file1.md" in result_data["results"]
        assert "file2.md" in result_data["results"]
        assert result_data["results"]["file1.md"]["valid"] is True
        assert result_data["results"]["file2.md"]["valid"] is False


class TestReadAllMemoryBankFiles:
    """Test reading all memory bank files."""

    @pytest.mark.asyncio
    async def test_read_all_memory_bank_files_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful reading of all memory bank files."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        file1 = memory_bank_dir / "file1.md"
        file2 = memory_bank_dir / "file2.md"
        _ = file1.write_text("Content 1")
        _ = file2.write_text("Content 2")

        mock_fs_manager.read_file = AsyncMock(
            side_effect=[("Content 1", None), ("Content 2", None)]
        )

        # Act
        result = await read_all_memory_bank_files(mock_fs_manager, tmp_path)

        # Assert
        assert "file1.md" in result
        assert "file2.md" in result
        assert result["file1.md"] == "Content 1"
        assert result["file2.md"] == "Content 2"

    @pytest.mark.asyncio
    async def test_read_all_memory_bank_files_empty_dir(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test reading from empty memory bank directory."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        # Act
        result = await read_all_memory_bank_files(mock_fs_manager, tmp_path)

        # Assert
        assert result == {}
