"""Split from test_validation_operations.py to keep file size under limits."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.validation.duplication import (
    validate_duplications,
)
from cortex.tools.validation.helpers import (
    generate_duplication_fixes,
)
from tests.tools.validation_operations_support import (
    setup_validate_duplications_with_fixes,
)


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
        mock_detector, mock_config = setup_validate_duplications_with_fixes(
            tmp_path, mock_fs_manager
        )

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
