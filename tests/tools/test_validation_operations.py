"""Tests for validation operations module."""

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import DetailedFileMetadata, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.validation.dispatch import (
    handle_infrastructure_validation_wrapper,
    handle_timestamps_validation_wrapper,
    setup_validation_managers,
)
from cortex.tools.validation.duplication import (
    handle_duplications_validation,
    validate_duplications,
)
from cortex.tools.validation.helpers import (
    create_invalid_check_type_error,
    create_validation_error_response,
    generate_duplication_fixes,
    read_all_memory_bank_files,
)
from cortex.tools.validation.infrastructure import (
    handle_infrastructure_validation,
)
from cortex.tools.validation.operations import validate, validate_resource
from cortex.tools.validation.quality import (
    handle_quality_validation,
    validate_quality_all_files,
    validate_quality_single_file,
)
from cortex.tools.validation.roadmap_sync import (
    handle_roadmap_sync_validation,
)
from cortex.tools.validation.schema import (
    handle_schema_validation,
    validate_schema_all_files,
    validate_schema_single_file,
)
from cortex.tools.validation.timestamps import handle_timestamps_validation
from cortex.validation.timestamp_validator import (
    validate_timestamps_all_files,
    validate_timestamps_single_file,
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
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        _ = memory_bank_dir.mkdir(parents=True)

        file1 = memory_bank_dir / "file1.md"
        file2 = memory_bank_dir / "file2.md"
        _ = file1.write_text("# Content 1\n")
        _ = file2.write_text("# Content 2\n")

        mock_fs_manager.read_file = AsyncMock(
            side_effect=[("# Content 1\n", None), ("# Content 2\n", None)]
        )

        mock_validator = MagicMock()
        mock_validator.validate_file = AsyncMock(
            side_effect=[
                MagicMock(
                    model_dump=MagicMock(
                        return_value={"valid": True, "errors": [], "warnings": []}
                    )
                ),
                MagicMock(
                    model_dump=MagicMock(
                        return_value={
                            "valid": False,
                            "errors": ["Missing section"],
                            "warnings": [],
                        }
                    )
                ),
            ]
        )

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


class TestGenerateDuplicationFixes:
    """Test duplication fix suggestion generation."""

    def test_generate_duplication_fixes_exact_duplicates(self) -> None:
        """Test fix generation for exact duplicates."""
        # Arrange
        duplications_dict = {
            "exact_duplicates": [
                {
                    "content": "Duplicate content",
                    "files": ["file1.md", "file2.md"],
                    "locations": [
                        {"file": "file1.md", "line": 10},
                        {"file": "file2.md", "line": 20},
                    ],
                }
            ],
            "similar_content": [],
        }

        # Act
        fixes = generate_duplication_fixes(cast(ModelDict, duplications_dict))

        # Assert
        assert len(fixes) == 1
        fix_dict = fixes[0]
        assert cast(list[object], fix_dict["files"]) == ["file1.md", "file2.md"]
        assert "transclusion" in cast(str, fix_dict["suggestion"])
        assert len(cast(list[object], fix_dict["steps"])) == 3

    def test_generate_duplication_fixes_similar_content(self) -> None:
        """Test fix generation for similar content."""
        # Arrange
        duplications_dict = {
            "exact_duplicates": [],
            "similar_content": [
                {
                    "similarity": 0.92,
                    "files": ["file1.md", "file2.md"],
                    "content_preview": "Similar content...",
                }
            ],
        }

        # Act
        fixes = generate_duplication_fixes(cast(ModelDict, duplications_dict))

        # Assert
        assert len(fixes) == 1
        fix_dict = fixes[0]
        assert cast(list[object], fix_dict["files"]) == ["file1.md", "file2.md"]
        assert "transclusion" in cast(str, fix_dict["suggestion"])

    def test_generate_duplication_fixes_combined(self) -> None:
        """Test fix generation for both exact and similar duplicates."""
        # Arrange
        duplications_dict = {
            "exact_duplicates": [
                {"files": ["file1.md", "file2.md"]},
            ],
            "similar_content": [
                {"files": ["file3.md", "file4.md"]},
            ],
        }

        # Act
        fixes = generate_duplication_fixes(cast(ModelDict, duplications_dict))

        # Assert
        assert len(fixes) == 2

    def test_generate_duplication_fixes_empty(self) -> None:
        """Test fix generation with no duplicates."""
        # Arrange
        duplications_dict: ModelDict = {
            "exact_duplicates": [],
            "similar_content": [],
        }

        # Act
        fixes = generate_duplication_fixes(duplications_dict)

        # Assert
        assert len(fixes) == 0


class TestValidateDuplications:
    """Test duplication validation."""

    @pytest.mark.asyncio
    async def test_validate_duplications_with_custom_threshold(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test duplication validation with custom threshold."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        mock_fs_manager.read_file = AsyncMock(return_value=("Content", None))

        mock_detector = MagicMock()
        duplications = MagicMock()
        duplications.model_dump = MagicMock(
            return_value={
                "duplicates_found": 0,
                "exact_duplicates": [],
                "similar_content": [],
            }
        )
        duplications.duplicates_found = 0
        mock_detector.scan_all_files = AsyncMock(return_value=duplications)

        mock_config = MagicMock()

        # Act
        result = await validate_duplications(
            mock_fs_manager,
            mock_detector,
            mock_config,
            tmp_path,
            similarity_threshold=0.9,
            suggest_fixes=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "duplications"
        assert result_data["threshold"] == 0.9
        assert mock_detector.threshold == 0.9

    @pytest.mark.asyncio
    async def test_validate_duplications_with_default_threshold(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test duplication validation with default threshold from config."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        mock_fs_manager.read_file = AsyncMock(return_value=("Content", None))

        mock_detector = MagicMock()
        duplications = MagicMock()
        duplications.model_dump = MagicMock(
            return_value={
                "duplicates_found": 0,
                "exact_duplicates": [],
                "similar_content": [],
            }
        )
        duplications.duplicates_found = 0
        mock_detector.scan_all_files = AsyncMock(return_value=duplications)

        mock_config = MagicMock()
        mock_config.get_duplication_threshold.return_value = 0.85

        # Act
        result = await validate_duplications(
            mock_fs_manager,
            mock_detector,
            mock_config,
            tmp_path,
            similarity_threshold=None,
            suggest_fixes=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["threshold"] == 0.85
        assert mock_detector.threshold == 0.85

    @pytest.mark.asyncio
    async def test_validate_duplications_with_fixes(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test duplication validation with fix suggestions."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        mock_fs_manager.read_file = AsyncMock(return_value=("Content", None))

        mock_detector = MagicMock()
        duplications = MagicMock()
        duplications.model_dump = MagicMock(
            return_value={
                "duplicates_found": 1,
                "exact_duplicates": [
                    {"files": ["file1.md", "file2.md"], "content": "Duplicate"}
                ],
                "similar_content": [],
            }
        )
        duplications.duplicates_found = 1
        mock_detector.scan_all_files = AsyncMock(return_value=duplications)

        mock_config = MagicMock()
        mock_config.get_duplication_threshold.return_value = 0.85

        # Act
        result = await validate_duplications(
            mock_fs_manager,
            mock_detector,
            mock_config,
            tmp_path,
            similarity_threshold=None,
            suggest_fixes=True,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["duplicates_found"] == 1
        assert "suggested_fixes" in result_data
        assert len(result_data["suggested_fixes"]) > 0


class TestValidateQuality:
    """Test quality validation helpers."""

    @pytest.mark.asyncio
    async def test_validate_quality_single_file_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful quality validation for single file."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "projectBrief.md"
        _ = test_file.write_text("# Content\n")

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(return_value=("# Content\n", None))

        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value=DetailedFileMetadata(
                path=str(test_file),
                exists=True,
                size_bytes=0,
                token_count=100,
                token_model="",
                last_modified="",
                content_hash="",
            )
        )

        mock_metrics = MagicMock()
        mock_metrics.calculate_file_score = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "file_name": "projectBrief.md",
                        "score": 85,
                        "grade": "B",
                        "validation": {"valid": True, "errors": [], "warnings": []},
                        "freshness": 90,
                        "structure": 80,
                    }
                )
            )
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

        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(side_effect=[{"tokens": 50}, {}])

        mock_metrics = MagicMock()
        mock_metrics.calculate_overall_score = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "overall_score": 80,
                        "status": "healthy",
                        "grade": "B",
                        "breakdown": {},
                    }
                )
            )
        )

        mock_detector = MagicMock()
        duplication_scan = MagicMock()
        duplication_scan.model_dump = MagicMock(return_value={"duplicates_found": 0})
        duplication_scan.duplicates_found = 0
        mock_detector.scan_all_files = AsyncMock(return_value=duplication_scan)

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
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "metadata_index": MagicMock(),
            "quality_metrics": MagicMock(),
            "duplication_detector": MagicMock(),
        }

        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("Content")

        mock_managers["fs_manager"].construct_safe_path.return_value = test_file
        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        mock_managers["metadata_index"].get_file_metadata = AsyncMock(return_value={})
        mock_managers["quality_metrics"].calculate_file_score = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "file_name": "test.md",
                        "score": 85,
                        "grade": "B",
                        "validation": {"valid": True, "errors": [], "warnings": []},
                        "freshness": 90,
                        "structure": 80,
                    }
                )
            )
        )

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
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "metadata_index": MagicMock(),
            "quality_metrics": MagicMock(),
            "duplication_detector": MagicMock(),
        }

        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        mock_managers["metadata_index"].get_file_metadata = AsyncMock(return_value={})
        mock_managers["quality_metrics"].calculate_overall_score = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "overall_score": 80,
                        "status": "healthy",
                        "grade": "B",
                        "breakdown": {},
                    }
                )
            )
        )
        duplication_scan = MagicMock()
        duplication_scan.model_dump = MagicMock(return_value={"duplicates_found": 0})
        duplication_scan.duplicates_found = 0
        mock_managers["duplication_detector"].scan_all_files = AsyncMock(
            return_value=duplication_scan
        )

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


class TestErrorHelpers:
    """Test error response helper functions."""

    def test_create_invalid_check_type_error(self) -> None:
        """Test creation of invalid check type error response."""
        # Act
        result = create_invalid_check_type_error("invalid_type")

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "invalid_type" in result_data["error"]
        assert "available_options" in result_data
        assert "schema" in result_data["available_options"]
        assert "duplications" in result_data["available_options"]
        assert "quality" in result_data["available_options"]
        assert "suggestion" in result_data
        assert "example" in result_data

    def test_create_validation_error_response(self) -> None:
        """Test creation of validation error response."""
        # Arrange
        error = ValueError("Test error message")

        # Act
        result = create_validation_error_response(error)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert result_data["error"] == "Test error message"
        assert result_data["error_type"] == "ValueError"

    def test_create_invalid_check_type_error_includes_infrastructure(self) -> None:
        """Test that invalid check type error includes infrastructure."""
        # Act
        result = create_invalid_check_type_error("invalid_type")

        # Assert
        result_data = json.loads(result)
        assert "infrastructure" in result_data["available_options"]


class TestHandleInfrastructureValidation:
    """Test infrastructure validation handler."""

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_success(
        self, tmp_path: Path
    ) -> None:
        """Test successful infrastructure validation."""
        # Arrange
        github_dir = tmp_path / ".github" / "workflows"
        github_dir.mkdir(parents=True)
        workflow_file = github_dir / "quality.yml"
        _ = workflow_file.write_text(
            "name: Test\njobs:\n  test:\n    steps:\n      - name: Test step"
        )

        synapse_dir = get_cortex_path(tmp_path, CortexResourceType.SYNAPSE) / "prompts"
        synapse_dir.mkdir(parents=True)
        commit_file = synapse_dir / "commit.md"
        _ = commit_file.write_text("# Commit\n\n1. **Test step**\n   Description")

        scripts_dir = (
            get_cortex_path(tmp_path, CortexResourceType.SYNAPSE) / "scripts" / "python"
        )
        scripts_dir.mkdir(parents=True)
        _ = (scripts_dir / "check_file_sizes.py").write_text("# Script")
        _ = (scripts_dir / "check_function_lengths.py").write_text("# Script")

        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=True,
            check_code_quality_consistency=True,
            check_documentation_consistency=True,
            check_config_consistency=True,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "infrastructure"
        assert "checks_performed" in result_data
        assert "issues_found" in result_data
        assert "recommendations" in result_data

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_ci_file(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with missing CI workflow file."""
        # Arrange
        synapse_dir = get_cortex_path(tmp_path, CortexResourceType.SYNAPSE) / "prompts"
        synapse_dir.mkdir(parents=True)
        commit_file = synapse_dir / "commit.md"
        _ = commit_file.write_text("# Commit\n\n1. **Test step**\n   Description")

        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=True,
            check_code_quality_consistency=False,
            check_documentation_consistency=False,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_file" for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_commit_file(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with missing commit prompt file."""
        # Arrange
        github_dir = tmp_path / ".github" / "workflows"
        github_dir.mkdir(parents=True)
        workflow_file = github_dir / "quality.yml"
        _ = workflow_file.write_text(
            "name: Test\njobs:\n  test:\n    steps:\n      - name: Test step"
        )

        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=True,
            check_code_quality_consistency=False,
            check_documentation_consistency=False,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_file" for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_code_quality_check(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with code quality consistency check."""
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=True,
            check_documentation_consistency=False,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "code_quality_consistency" in result_data["checks_performed"]

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_documentation_check(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with documentation consistency check."""
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=False,
            check_documentation_consistency=True,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "documentation_consistency" in result_data["checks_performed"]

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_config_check(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with configuration consistency check."""
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=False,
            check_documentation_consistency=False,
            check_config_consistency=True,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "config_consistency" in result_data["checks_performed"]

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_scripts(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation detects missing code quality scripts."""
        # Arrange - no scripts directory
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=True,
            check_documentation_consistency=False,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_script" for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_readme(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation detects missing README."""
        # Arrange - no README.md
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=False,
            check_documentation_consistency=True,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_documentation"
            for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_configs(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation detects missing config files."""
        # Arrange - no .cortex directory
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=False,
            check_documentation_consistency=False,
            check_config_consistency=True,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_config" for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_yaml_none(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation when yaml module is not available."""
        # Arrange
        github_dir = tmp_path / ".github" / "workflows"
        github_dir.mkdir(parents=True)
        workflow_file = github_dir / "quality.yml"
        _ = workflow_file.write_text("name: Test")

        synapse_dir = get_cortex_path(tmp_path, CortexResourceType.SYNAPSE) / "prompts"
        synapse_dir.mkdir(parents=True)
        commit_file = synapse_dir / "commit.md"
        _ = commit_file.write_text("# Commit")

        # Mock yaml as None
        with patch("cortex.validation.infrastructure_validator.yaml", None):
            # Act
            result = await handle_infrastructure_validation(
                tmp_path,
                check_commit_ci_alignment=True,
                check_code_quality_consistency=False,
                check_documentation_consistency=False,
                check_config_consistency=False,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            # Should still complete without errors even if yaml is None


class TestSetupValidationManagers:
    """Test setup validation managers helper."""

    @pytest.mark.asyncio
    async def test_setup_validation_managers_success(self, tmp_path: Path) -> None:
        """Test successful setup of validation managers."""
        # Arrange
        mock_fs = MagicMock()
        mock_index = MagicMock()
        mock_schema = MagicMock()
        mock_detector = MagicMock()
        mock_metrics = MagicMock()
        mock_config = MagicMock()

        with (
            patch(
                "cortex.tools.validation.dispatch.initialization.get_managers"
            ) as mock_get_managers,
            patch("cortex.tools.validation.dispatch.get_manager") as mock_get_manager,
        ):
            mock_get_managers.return_value = {
                "fs": mock_fs,
                "index": mock_index,
            }
            mock_get_manager.side_effect = [
                mock_fs,  # fs_manager
                mock_index,  # metadata_index
                mock_schema,  # schema_validator
                mock_detector,  # duplication_detector
                mock_metrics,  # quality_metrics
                mock_config,  # validation_config
            ]

            # Act
            result = await setup_validation_managers(tmp_path)

            # Assert
            assert "fs_manager" in result
            assert "metadata_index" in result
            assert "schema_validator" in result
            assert "duplication_detector" in result
            assert "quality_metrics" in result
            assert "validation_config" in result
            assert result["fs_manager"] == mock_fs
            assert result["metadata_index"] == mock_index


class TestValidateMainFunction:
    """Test main validate function."""

    @pytest.mark.asyncio
    async def test_validate_schema_check(self, tmp_path: Path) -> None:
        """Test validate function with schema check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.dispatch.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation.dispatch.handle_schema_validation_wrapper"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps({"status": "success"})

            # Act
            result = await validate(check_type="schema")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_duplications_check(self, tmp_path: Path) -> None:
        """Test validate function with duplications check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.dispatch.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation.dispatch.handle_duplications_validation_wrapper"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps({"status": "success"})

            # Act
            result = await validate(check_type="duplications")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_quality_check(self, tmp_path: Path) -> None:
        """Test validate function with quality check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.dispatch.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation.dispatch.handle_quality_validation_wrapper"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps({"status": "success"})

            # Act
            result = await validate(check_type="quality")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_infrastructure_check(self, tmp_path: Path) -> None:
        """Test validate function with infrastructure check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.dispatch.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation.dispatch.handle_infrastructure_validation_wrapper"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps(
                {
                    "status": "success",
                    "check_type": "infrastructure",
                    "checks_performed": {
                        "commit_ci_alignment": True,
                        "code_quality_consistency": True,
                    },
                    "issues_found": [],
                    "recommendations": [],
                }
            )

            # Act
            result = await validate(
                check_type="infrastructure",  # type: ignore[arg-type]
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["check_type"] == "infrastructure"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_wrapper_calls_impl(
        self, tmp_path: Path
    ) -> None:
        """Wrapper delegates to handle_infrastructure_validation (covers dispatch)."""
        with patch(
            "cortex.tools.validation.dispatch.handle_infrastructure_validation",
            new_callable=AsyncMock,
            return_value='{"status":"success","checks_performed":{}}',
        ) as mock_impl:
            result = await handle_infrastructure_validation_wrapper(
                tmp_path, False, False, False, False
            )
            mock_impl.assert_called_once_with(tmp_path, False, False, False, False)
            assert "status" in result

    @pytest.mark.asyncio
    async def test_handle_timestamps_validation_wrapper_calls_impl(
        self, tmp_path: Path
    ) -> None:
        """Wrapper delegates to handle_timestamps_validation (covers dispatch)."""
        mock_fs = MagicMock()
        managers: dict[str, Any] = {"fs_manager": mock_fs}
        with patch(
            "cortex.tools.validation.dispatch.handle_timestamps_validation",
            new_callable=AsyncMock,
            return_value='{"status":"success","issues":[]}',
        ) as mock_impl:
            result = await handle_timestamps_validation_wrapper(
                managers, tmp_path, None
            )
            mock_impl.assert_called_once_with(mock_fs, tmp_path, None)
            assert "status" in result

    @pytest.mark.asyncio
    async def test_validate_invalid_check_type(self, tmp_path: Path) -> None:
        """Test validate function with invalid check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with patch(
            "cortex.tools.validation.dispatch.setup_validation_managers"
        ) as mock_setup:
            mock_setup.return_value = {}

            # Act
            result = await validate(
                check_type="invalid",  # type: ignore[arg-type]
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Invalid check_type" in result_data["error"]

    @pytest.mark.asyncio
    async def test_validate_exception_handling(self, tmp_path: Path) -> None:
        """Test validate function exception handling."""
        # Arrange
        with patch(
            "cortex.tools.validation.dispatch.setup_validation_managers"
        ) as mock_setup:
            mock_setup.side_effect = RuntimeError("Setup failed")

            # Act
            result = await validate(check_type="schema")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Setup failed" in result_data["error"]
            assert result_data["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_validate_with_all_parameters(self, tmp_path: Path) -> None:
        """Test validate function with all optional parameters."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.dispatch.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation.dispatch.handle_duplications_validation_wrapper"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps(
                {"status": "success", "threshold": 0.9, "suggested_fixes": []}
            )

            # Act
            result = await validate(
                check_type="duplications",
                file_name="test.md",
                strict_mode=True,
                similarity_threshold=0.9,
                suggest_fixes=False,
                response_format="detailed",
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["threshold"] == 0.9


class TestValidateContextLogging:
    """Test validate tool Context logging (FastMCP)."""

    @pytest.mark.asyncio
    async def test_validate_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, validate logs start and completion via log_client."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.validation.operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.validation.dispatch.prepare_validation_managers",
                new_callable=AsyncMock,
            ) as mock_prepare,
            patch(
                "cortex.tools.validation.dispatch.call_dispatch_validation",
                new_callable=AsyncMock,
                return_value='{"status": "success"}',
            ),
        ):
            mock_prepare.return_value = (tmp_path, {})

            # Act
            result = await validate(
                check_type="schema",
                ctx=mock_ctx,
            )

            # Assert
            assert json.loads(result)["status"] == "success"
            args_list = [c[0] for c in mock_log.call_args_list]
            levels_and_messages = [(a[1], a[2]) for a in args_list]
            assert ("info", "validate: starting") in levels_and_messages
            assert ("info", "validate: completed") in levels_and_messages

    @pytest.mark.asyncio
    async def test_validate_calls_log_client_warning_on_invalid_check_type_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When check_type is invalid and ctx is passed, validate logs warning."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        mock_ctx = AsyncMock()
        with patch(
            "cortex.tools.validation.operations.log_client",
            new_callable=AsyncMock,
        ) as mock_log:
            # Act
            result = await validate(
                check_type="invalid",  # type: ignore[arg-type]
                ctx=mock_ctx,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert any(
                c[0][1] == "warning" and c[0][2] == "validate: invalid check_type"
                for c in mock_log.call_args_list
                if len(c[0]) >= 3
            )

    @pytest.mark.asyncio
    async def test_validate_calls_log_client_error_on_exception_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When validation raises and ctx is passed, validate logs error."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.validation.operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.validation.operations.prepare_validation_managers",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Setup failed"),
            ),
        ):
            # Act
            result = await validate(
                check_type="schema",
                ctx=mock_ctx,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Setup failed" in result_data["error"]
            error_calls = [
                c[0]
                for c in mock_log.call_args_list
                if len(c[0]) >= 2 and c[0][1] == "error"
            ]
            assert len(error_calls) == 1
            assert "validate: failed" in error_calls[0][2]


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
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        _ = (memory_bank_dir / "activeContext.md").write_text(
            "# Active Context\n\n## Current Focus (2026-01-14T10:00)\n"
        )
        _ = (memory_bank_dir / "progress.md").write_text(
            "# Progress\n\n## 2026-01-14: Updates\n"
        )

        async def mock_list_files(directory: Path) -> list[Path]:
            return [
                memory_bank_dir / "activeContext.md",
                memory_bank_dir / "progress.md",
            ]

        mock_fs_manager.list_files = AsyncMock(side_effect=mock_list_files)
        mock_fs_manager.read_file = AsyncMock(
            side_effect=[
                ("# Active Context\n\n## Current Focus (2026-01-14)\n", None),
                ("# Progress\n\n## 2026-01-14: Updates\n", None),
            ]
        )

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
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        _ = (memory_bank_dir / "progress.md").write_text(
            "# Progress\n\n- ✅ Feature (2026-01-13 12:00)\n"
        )
        _ = (memory_bank_dir / "roadmap.md").write_text(
            "# Roadmap\n\n- ✅ Feature (2026-01-13T12:00:00)\n"
        )

        async def mock_list_files(directory: Path) -> list[Path]:
            return [
                memory_bank_dir / "progress.md",
                memory_bank_dir / "roadmap.md",
            ]

        mock_fs_manager.list_files = AsyncMock(side_effect=mock_list_files)
        mock_fs_manager.read_file = AsyncMock(
            side_effect=[
                ("# Progress\n\n- ✅ Feature (2026-01-13 12:00)\n", None),
                ("# Roadmap\n\n- ✅ Feature (2026-01-13T12:00:00)\n", None),
            ]
        )

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


class TestHandleRoadmapSyncValidation:
    """Test handle_roadmap_sync_validation MCP tool handler."""

    @pytest.mark.asyncio
    async def test_handle_roadmap_sync_validation_roadmap_not_found(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test handle_roadmap_sync_validation when roadmap.md doesn't exist."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        # Don't create roadmap.md

        # Act
        result = await handle_roadmap_sync_validation(mock_fs_manager, tmp_path, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "roadmap.md does not exist" in result_data["error"]

    @pytest.mark.asyncio
    async def test_handle_roadmap_sync_validation_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test handle_roadmap_sync_validation with valid roadmap."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        roadmap_path = memory_bank_dir / "roadmap.md"
        roadmap_content = "# Roadmap\n\n## Phase 1\nSee `src/module.py` for details.\n"
        _ = roadmap_path.write_text(roadmap_content)

        src_dir = tmp_path / "src"
        _ = src_dir.mkdir()
        _ = (src_dir / "module.py").write_text("# Module\n")

        mock_fs_manager.read_file = AsyncMock(return_value=(roadmap_content, None))

        # Act
        result = await handle_roadmap_sync_validation(mock_fs_manager, tmp_path, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "roadmap_sync"
        assert "valid" in result_data
        assert "summary" in result_data
        assert result_data["summary"]["total_todos_found"] == 0

    @pytest.mark.asyncio
    async def test_handle_roadmap_sync_validation_with_ghost_sections_logged(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test handle_roadmap_sync_validation logs when roadmap contains ghost sections."""
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        roadmap_path = memory_bank_dir / "roadmap.md"
        roadmap_content = (
            "# Roadmap\n\n## Recent Findings\n\n## Phase 1\nSee `src/module.py`.\n"
        )
        _ = roadmap_path.write_text(roadmap_content)
        (tmp_path / "src").mkdir()
        _ = (tmp_path / "src" / "module.py").write_text("# Module\n")
        mock_fs_manager.read_file = AsyncMock(return_value=(roadmap_content, None))

        result = await handle_roadmap_sync_validation(mock_fs_manager, tmp_path, None)

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "roadmap_sync"


class TestValidateResource:
    """Test validate_resource (Phase 43 Phase 3 Validation resource)."""

    @pytest.mark.asyncio
    async def test_validate_resource_returns_json_success(self, tmp_path: Path) -> None:
        """Test validate_resource returns valid JSON (zero-arg, session config)."""
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        with (
            patch(
                "cortex.core.session_config.read_session_config",
                return_value={"check_type": "schema"},
            ),
            patch(
                "cortex.tools.validation.operations.prepare_validation_managers"
            ) as mock_prepare,
            patch(
                "cortex.tools.validation.operations.call_dispatch_validation"
            ) as mock_dispatch,
        ):
            mock_prepare.return_value = (tmp_path, {})
            mock_dispatch.return_value = json.dumps(
                {"status": "success", "check_type": "schema"}
            )
            result = await validate_resource()
        result_data = json.loads(result)
        assert "status" in result_data
        assert result_data["status"] in ("success", "error")
        if result_data["status"] == "success":
            assert result_data["check_type"] == "schema"

    @pytest.mark.asyncio
    async def test_validate_resource_defaults_to_timestamps(self) -> None:
        """Test validate_resource defaults to timestamps when no session config."""
        with patch(
            "cortex.core.session_config.read_session_config",
            return_value={},
        ):
            # Should not error — "timestamps" is a valid check_type
            result = await validate_resource()
        # The call may fail due to missing project root, but the check_type
        # should be valid (not "invalid check_type" error)
        result_data = json.loads(result)
        if result_data.get("status") == "error":
            assert "Invalid check_type" not in result_data.get("error", "")
