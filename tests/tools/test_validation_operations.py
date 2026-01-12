"""Tests for validation operations module."""

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.tools.validation_operations import (
    create_invalid_check_type_error,
    create_validation_error_response,
    generate_duplication_fixes,
    handle_duplications_validation,
    handle_infrastructure_validation,
    handle_quality_validation,
    handle_schema_validation,
    read_all_memory_bank_files,
    setup_validation_managers,
    validate,
    validate_duplications,
    validate_quality_all_files,
    validate_quality_single_file,
    validate_schema_all_files,
    validate_schema_single_file,
)


class TestValidateSchemaHelpers:
    """Test schema validation helper functions."""

    @pytest.mark.asyncio
    async def testvalidate_schema_single_file_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful single file schema validation."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()
        test_file = memory_bank_dir / "projectBrief.md"
        _ = test_file.write_text("# Test content\n## Section 1\n")

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(
            return_value=("# Test content\n## Section 1\n", None)
        )

        mock_validator = MagicMock()
        mock_validator.validate_file = AsyncMock(
            return_value={"valid": True, "errors": [], "warnings": []}
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
    async def testvalidate_schema_single_file_invalid_name(
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
    async def testvalidate_schema_single_file_permission_error(
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
    async def testvalidate_schema_single_file_not_found(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test schema validation when file does not exist."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()
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
    async def testvalidate_schema_all_files_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful all files schema validation."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

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
                {"valid": True, "errors": [], "warnings": []},
                {"valid": False, "errors": ["Missing section"], "warnings": []},
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
    async def testread_all_memory_bank_files_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful reading of all memory bank files."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

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
    async def testread_all_memory_bank_files_empty_dir(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test reading from empty memory bank directory."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        # Act
        result = await read_all_memory_bank_files(mock_fs_manager, tmp_path)

        # Assert
        assert result == {}


class TestGenerateDuplicationFixes:
    """Test duplication fix suggestion generation."""

    def testgenerate_duplication_fixes_exact_duplicates(self) -> None:
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
        fixes = generate_duplication_fixes(cast(dict[str, object], duplications_dict))

        # Assert
        assert len(fixes) == 1
        fix_dict = fixes[0]
        assert cast(list[object], fix_dict["files"]) == ["file1.md", "file2.md"]
        assert "transclusion" in cast(str, fix_dict["suggestion"])
        assert len(cast(list[object], fix_dict["steps"])) == 3

    def testgenerate_duplication_fixes_similar_content(self) -> None:
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
        fixes = generate_duplication_fixes(cast(dict[str, object], duplications_dict))

        # Assert
        assert len(fixes) == 1
        fix_dict = fixes[0]
        assert cast(list[object], fix_dict["files"]) == ["file1.md", "file2.md"]
        assert "transclusion" in cast(str, fix_dict["suggestion"])

    def testgenerate_duplication_fixes_combined(self) -> None:
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
        fixes = generate_duplication_fixes(cast(dict[str, object], duplications_dict))

        # Assert
        assert len(fixes) == 2

    def testgenerate_duplication_fixes_empty(self) -> None:
        """Test fix generation with no duplicates."""
        # Arrange
        duplications_dict: dict[str, object] = {
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
    async def testvalidate_duplications_with_custom_threshold(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test duplication validation with custom threshold."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        mock_fs_manager.read_file = AsyncMock(return_value=("Content", None))

        mock_detector = MagicMock()
        mock_detector.scan_all_files = AsyncMock(
            return_value={
                "duplicates_found": 0,
                "exact_duplicates": [],
                "similar_content": [],
            }
        )

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
    async def testvalidate_duplications_with_default_threshold(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test duplication validation with default threshold from config."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        mock_fs_manager.read_file = AsyncMock(return_value=("Content", None))

        mock_detector = MagicMock()
        mock_detector.scan_all_files = AsyncMock(
            return_value={
                "duplicates_found": 0,
                "exact_duplicates": [],
                "similar_content": [],
            }
        )

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
    async def testvalidate_duplications_with_fixes(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test duplication validation with fix suggestions."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        mock_fs_manager.read_file = AsyncMock(return_value=("Content", None))

        mock_detector = MagicMock()
        mock_detector.scan_all_files = AsyncMock(
            return_value={
                "duplicates_found": 1,
                "exact_duplicates": [
                    {"files": ["file1.md", "file2.md"], "content": "Duplicate"}
                ],
                "similar_content": [],
            }
        )

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
    async def testvalidate_quality_single_file_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful quality validation for single file."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()
        test_file = memory_bank_dir / "projectBrief.md"
        _ = test_file.write_text("# Content\n")

        mock_fs_manager.construct_safe_path.return_value = test_file
        mock_fs_manager.read_file = AsyncMock(return_value=("# Content\n", None))

        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"tokens": 100, "created": 123456}
        )

        mock_metrics = MagicMock()
        mock_metrics.calculate_file_score = AsyncMock(
            return_value={"overall": 85, "completeness": 90}
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
        assert result_data["score"]["overall"] == 85

    @pytest.mark.asyncio
    async def testvalidate_quality_single_file_invalid_name(
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
    async def testvalidate_quality_single_file_not_found(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test quality validation when file does not exist."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()
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
    async def testvalidate_quality_all_files_success(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test successful quality validation for all files."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()
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
            return_value={
                "overall_score": 80,
                "status": "good",
                "file_scores": {"file1.md": 85, "file2.md": 75},
            }
        )

        mock_detector = MagicMock()
        mock_detector.scan_all_files = AsyncMock(return_value={"duplicates_found": 0})

        # Act
        result = await validate_quality_all_files(
            mock_fs_manager, mock_index, mock_metrics, mock_detector, tmp_path
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "quality"
        assert result_data["overall_score"] == 80
        assert result_data["health_status"] == "good"


class TestValidationHandlers:
    """Test validation handler functions."""

    @pytest.mark.asyncio
    async def testhandle_schema_validation_with_file(self, tmp_path: Path) -> None:
        """Test schema validation handler with specific file."""
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "schema_validator": MagicMock(),
        }

        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()
        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("Content")

        mock_managers["fs_manager"].construct_safe_path.return_value = test_file
        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        mock_managers["schema_validator"].validate_file = AsyncMock(
            return_value={"valid": True, "errors": []}
        )

        # Act
        result = await handle_schema_validation(mock_managers, tmp_path, "test.md")

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["file_name"] == "test.md"

    @pytest.mark.asyncio
    async def testhandle_schema_validation_all_files(self, tmp_path: Path) -> None:
        """Test schema validation handler for all files."""
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "schema_validator": MagicMock(),
        }

        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        mock_managers["schema_validator"].validate_file = AsyncMock(
            return_value={"valid": True}
        )

        # Act
        result = await handle_schema_validation(mock_managers, tmp_path, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "schema"
        assert "results" in result_data

    @pytest.mark.asyncio
    async def testhandle_duplications_validation(self, tmp_path: Path) -> None:
        """Test duplications validation handler."""
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "duplication_detector": MagicMock(),
            "validation_config": MagicMock(),
        }

        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        mock_managers["duplication_detector"].scan_all_files = AsyncMock(
            return_value={"duplicates_found": 0}
        )
        mock_managers["validation_config"].get_duplication_threshold.return_value = 0.85

        # Act
        result = await handle_duplications_validation(
            mock_managers, tmp_path, 0.9, True
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "duplications"
        assert result_data["threshold"] == 0.9

    @pytest.mark.asyncio
    async def testhandle_quality_validation_with_file(self, tmp_path: Path) -> None:
        """Test quality validation handler with specific file."""
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "metadata_index": MagicMock(),
            "quality_metrics": MagicMock(),
        }

        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()
        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("Content")

        mock_managers["fs_manager"].construct_safe_path.return_value = test_file
        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        mock_managers["metadata_index"].get_file_metadata = AsyncMock(return_value={})
        mock_managers["quality_metrics"].calculate_file_score = AsyncMock(
            return_value={"overall": 85}
        )

        # Act
        result = await handle_quality_validation(mock_managers, tmp_path, "test.md")

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["file_name"] == "test.md"

    @pytest.mark.asyncio
    async def testhandle_quality_validation_all_files(self, tmp_path: Path) -> None:
        """Test quality validation handler for all files."""
        # Arrange
        mock_managers: dict[str, Any] = {
            "fs_manager": MagicMock(),
            "metadata_index": MagicMock(),
            "quality_metrics": MagicMock(),
            "duplication_detector": MagicMock(),
        }

        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        mock_managers["fs_manager"].read_file = AsyncMock(
            return_value=("Content", None)
        )
        mock_managers["metadata_index"].get_file_metadata = AsyncMock(return_value={})
        mock_managers["quality_metrics"].calculate_overall_score = AsyncMock(
            return_value={"overall_score": 80, "status": "good"}
        )
        mock_managers["duplication_detector"].scan_all_files = AsyncMock(
            return_value={}
        )

        # Act
        result = await handle_quality_validation(mock_managers, tmp_path, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "quality"


class TestErrorHelpers:
    """Test error response helper functions."""

    def testcreate_invalid_check_type_error(self) -> None:
        """Test creation of invalid check type error response."""
        # Act
        result = create_invalid_check_type_error("invalid_type")

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "invalid_type" in result_data["error"]
        assert "valid_check_types" in result_data
        assert "schema" in result_data["valid_check_types"]
        assert "duplications" in result_data["valid_check_types"]
        assert "quality" in result_data["valid_check_types"]

    def testcreate_validation_error_response(self) -> None:
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

    def testcreate_invalid_check_type_error_includes_infrastructure(self) -> None:
        """Test that invalid check type error includes infrastructure."""
        # Act
        result = create_invalid_check_type_error("invalid_type")

        # Assert
        result_data = json.loads(result)
        assert "infrastructure" in result_data["valid_check_types"]


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

        synapse_dir = tmp_path / ".cortex" / "synapse" / "prompts"
        synapse_dir.mkdir(parents=True)
        commit_file = synapse_dir / "commit.md"
        _ = commit_file.write_text("# Commit\n\n1. **Test step**\n   Description")

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        _ = (scripts_dir / "check_file_sizes.py").write_text("# Script")

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
        synapse_dir = tmp_path / ".cortex" / "synapse" / "prompts"
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

        synapse_dir = tmp_path / ".cortex" / "synapse" / "prompts"
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
    async def testsetup_validation_managers_success(self, tmp_path: Path) -> None:
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
                "cortex.tools.validation_operations.get_managers"
            ) as mock_get_managers,
            patch("cortex.tools.validation_operations.get_manager") as mock_get_manager,
        ):
            mock_get_managers.return_value = {
                "fs": mock_fs,
                "index": mock_index,
            }
            mock_get_manager.side_effect = [
                mock_schema,
                mock_detector,
                mock_metrics,
                mock_config,
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
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        with (
            patch(
                "cortex.tools.validation_operations.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation_operations.handle_schema_validation"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps({"status": "success"})

            # Act
            result = await validate(check_type="schema", project_root=str(tmp_path))

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def testvalidate_duplications_check(self, tmp_path: Path) -> None:
        """Test validate function with duplications check type."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        with (
            patch(
                "cortex.tools.validation_operations.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation_operations.handle_duplications_validation"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps({"status": "success"})

            # Act
            result = await validate(
                check_type="duplications", project_root=str(tmp_path)
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_quality_check(self, tmp_path: Path) -> None:
        """Test validate function with quality check type."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        with (
            patch(
                "cortex.tools.validation_operations.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation_operations.handle_quality_validation"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps({"status": "success"})

            # Act
            result = await validate(check_type="quality", project_root=str(tmp_path))

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_infrastructure_check(self, tmp_path: Path) -> None:
        """Test validate function with infrastructure check type."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        with patch(
            "cortex.tools.validation_operations.handle_infrastructure_validation"
        ) as mock_handle:
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
                project_root=str(tmp_path),
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["check_type"] == "infrastructure"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_invalid_check_type(self, tmp_path: Path) -> None:
        """Test validate function with invalid check type."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        with patch(
            "cortex.tools.validation_operations.setup_validation_managers"
        ) as mock_setup:
            mock_setup.return_value = {}

            # Act
            result = await validate(
                check_type="invalid",  # type: ignore[arg-type]
                project_root=str(tmp_path),
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
            "cortex.tools.validation_operations.setup_validation_managers"
        ) as mock_setup:
            mock_setup.side_effect = RuntimeError("Setup failed")

            # Act
            result = await validate(check_type="schema", project_root=str(tmp_path))

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Setup failed" in result_data["error"]
            assert result_data["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_validate_with_all_parameters(self, tmp_path: Path) -> None:
        """Test validate function with all optional parameters."""
        # Arrange
        memory_bank_dir = tmp_path / "memory-bank"
        _ = memory_bank_dir.mkdir()

        with (
            patch(
                "cortex.tools.validation_operations.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation_operations.handle_duplications_validation"
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
                project_root=str(tmp_path),
                strict_mode=True,
                similarity_threshold=0.9,
                suggest_fixes=False,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["threshold"] == 0.9
