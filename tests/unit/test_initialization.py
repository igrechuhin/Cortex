#!/usr/bin/env python3
"""
Unit tests for initialization module.

Tests project root detection and manager initialization.
"""

import os
from pathlib import Path
from unittest.mock import patch

from cortex.managers.initialization import get_project_root

# ============================================================================
# Test get_project_root
# ============================================================================


class TestGetProjectRoot:
    """Test get_project_root function."""

    def test_get_project_root_with_explicit_path(self, tmp_path: Path) -> None:
        """Test get_project_root returns resolved path when provided."""
        # Arrange
        project_root = tmp_path / "project"

        # Act
        result = get_project_root(str(project_root))

        # Assert
        assert result == project_root.resolve()
        assert result.is_absolute()

    def test_get_project_root_detects_from_cortex_dir(self, tmp_path: Path) -> None:
        """Test get_project_root detects project root from .cortex/ directory."""
        # Arrange
        project_root = tmp_path / "project"
        cortex_dir = project_root / ".cortex"
        cortex_dir.mkdir(parents=True)
        subdir = project_root / "subdir" / "nested"
        subdir.mkdir(parents=True)

        # Act - call from nested subdirectory
        with patch("cortex.managers.initialization.Path.cwd", return_value=subdir):
            result = get_project_root(None)

        # Assert
        assert result == project_root.resolve()
        assert result.is_absolute()

    def test_get_project_root_falls_back_to_cwd_when_no_cortex(
        self, tmp_path: Path
    ) -> None:
        """Test get_project_root falls back to cwd when .cortex/ not found."""
        # Arrange
        no_cortex_dir = tmp_path / "no-cortex"
        no_cortex_dir.mkdir()

        # Act
        with patch(
            "cortex.managers.initialization.Path.cwd", return_value=no_cortex_dir
        ):
            result = get_project_root(None)

        # Assert
        assert result == no_cortex_dir.resolve()
        assert result.is_absolute()

    def test_get_project_root_detects_from_parent(self, tmp_path: Path) -> None:
        """Test get_project_root detects project root in parent directory."""
        # Arrange
        project_root = tmp_path / "project"
        cortex_dir = project_root / ".cortex"
        cortex_dir.mkdir(parents=True)
        subdir = project_root / "src" / "deep" / "nested"
        subdir.mkdir(parents=True)

        # Act - call from deep nested subdirectory
        with patch("cortex.managers.initialization.Path.cwd", return_value=subdir):
            result = get_project_root(None)

        # Assert
        assert result == project_root.resolve()
        assert result.is_absolute()

    def test_get_project_root_resolves_relative_path(self, tmp_path: Path) -> None:
        """Test get_project_root resolves relative paths correctly."""
        # Arrange
        project_root = tmp_path / "project"
        project_root.mkdir()
        # Change to tmp_path directory to make relative path work
        original_cwd = Path.cwd()

        try:
            import os

            os.chdir(tmp_path)
            relative_path = "project"

            # Act
            result = get_project_root(relative_path)

            # Assert
            assert result == project_root.resolve()
            assert result.is_absolute()
        finally:
            os.chdir(original_cwd)

    def test_get_project_root_handles_root_filesystem(self) -> None:
        """Test get_project_root handles root filesystem correctly."""
        # Arrange
        root_path = Path("/")

        # Act
        with patch("cortex.managers.initialization.Path.cwd", return_value=root_path):
            result = get_project_root(None)

        # Assert
        assert result == root_path.resolve()
        assert result.is_absolute()
