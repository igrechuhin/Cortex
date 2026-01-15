"""
Unit tests for config_status module.
"""

from pathlib import Path
from unittest.mock import patch

from cortex.tools.config_status import (
    get_project_config_status,
)


class TestGetProjectConfigStatus:
    """Test get_project_config_status function."""

    def test_memory_bank_initialized(self, tmp_path: Path):
        """Test memory bank initialized detection."""
        # Arrange
        cortex_dir = tmp_path / ".cortex"
        memory_bank_dir = cortex_dir / "memory-bank"
        memory_bank_dir.mkdir(parents=True)
        core_files = [
            "projectBrief.md",
            "productContext.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "progress.md",
            "roadmap.md",
        ]
        for fname in core_files:
            (memory_bank_dir / fname).write_text("# Test")

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["memory_bank_initialized"] is True

    def test_memory_bank_not_initialized_missing_files(self, tmp_path: Path):
        """Test memory bank not initialized when files missing."""
        # Arrange
        cortex_dir = tmp_path / ".cortex"
        memory_bank_dir = cortex_dir / "memory-bank"
        memory_bank_dir.mkdir(parents=True)
        # Only create some files, not all
        (memory_bank_dir / "projectBrief.md").write_text("# Test")

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["memory_bank_initialized"] is False

    def test_memory_bank_not_initialized_missing_directory(self, tmp_path: Path):
        """Test memory bank not initialized when directory missing."""
        # Arrange
        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["memory_bank_initialized"] is False

    def test_structure_configured(self, tmp_path: Path):
        """Test structure configured detection."""
        # Arrange
        cortex_dir = tmp_path / ".cortex"
        for subdir in ["memory-bank", "rules", "plans", "config"]:
            (cortex_dir / subdir).mkdir(parents=True)

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["structure_configured"] is True

    def test_structure_not_configured_missing_dirs(self, tmp_path: Path):
        """Test structure not configured when directories missing."""
        # Arrange
        cortex_dir = tmp_path / ".cortex"
        cortex_dir.mkdir()
        # Only create some directories
        (cortex_dir / "memory-bank").mkdir()

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["structure_configured"] is False

    def test_cursor_integration_configured(self, tmp_path: Path):
        """Test Cursor integration configured detection."""
        # Arrange
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()

        # Create symlinks
        for symlink_name in ["memory-bank", "synapse", "plans"]:
            target = tmp_path / ".cortex" / symlink_name
            target.mkdir(parents=True, exist_ok=True)
            symlink = cursor_dir / symlink_name
            symlink.symlink_to(f"../.cortex/{symlink_name}")

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["cursor_integration_configured"] is True

    def test_cursor_integration_not_configured_missing_symlinks(self, tmp_path: Path):
        """Test Cursor integration not configured when symlinks missing."""
        # Arrange
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        # Don't create symlinks

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["cursor_integration_configured"] is False

    def test_cursor_integration_not_configured_broken_symlinks(self, tmp_path: Path):
        """Test Cursor integration not configured when symlinks broken."""
        # Arrange
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()

        # Create symlink pointing to wrong location
        symlink = cursor_dir / "memory-bank"
        symlink.symlink_to("../wrong/path")

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["cursor_integration_configured"] is False

    def test_migration_needed_legacy_cursor_format(self, tmp_path: Path):
        """Test migration needed when legacy .cursor/memory-bank/ exists."""
        # Arrange
        legacy_dir = tmp_path / ".cursor" / "memory-bank"
        legacy_dir.mkdir(parents=True)

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["migration_needed"] is True
            assert status["memory_bank_initialized"] is False

    def test_migration_needed_legacy_root_format(self, tmp_path: Path):
        """Test migration needed when legacy memory-bank/ exists."""
        # Arrange
        legacy_dir = tmp_path / "memory-bank"
        legacy_dir.mkdir()

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["migration_needed"] is True

    def test_migration_needed_legacy_dot_format(self, tmp_path: Path):
        """Test migration needed when legacy .memory-bank/ exists."""
        # Arrange
        legacy_dir = tmp_path / ".memory-bank"
        legacy_dir.mkdir()

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["migration_needed"] is True

    def test_migration_not_needed_when_initialized(self, tmp_path: Path):
        """Test migration not needed when memory bank is initialized."""
        # Arrange
        cortex_dir = tmp_path / ".cortex"
        memory_bank_dir = cortex_dir / "memory-bank"
        memory_bank_dir.mkdir(parents=True)
        core_files = [
            "projectBrief.md",
            "productContext.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "progress.md",
            "roadmap.md",
        ]
        for fname in core_files:
            (memory_bank_dir / fname).write_text("# Test")

        # Also create legacy format (should not trigger migration)
        legacy_dir = tmp_path / "memory-bank"
        legacy_dir.mkdir()

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["migration_needed"] is False
            assert status["memory_bank_initialized"] is True

    def test_fail_safe_on_exception(self, tmp_path: Path):
        """Test fail-safe behavior when exception occurs."""
        # Arrange
        with patch(
            "cortex.tools.config_status.get_project_root",
            side_effect=Exception("Test error"),
        ):
            # Act
            status = get_project_config_status()

            # Assert
            # Fail-safe assumes configured (all True) to avoid showing setup prompts on error
            # This is safer than showing all prompts when we can't determine status
            assert status["memory_bank_initialized"] is True
            assert status["structure_configured"] is True
            assert status["cursor_integration_configured"] is True
            assert status["migration_needed"] is False

    def test_fully_configured_project(self, tmp_path: Path):
        """Test fully configured project returns all True except migration."""
        # Arrange
        cortex_dir = tmp_path / ".cortex"
        memory_bank_dir = cortex_dir / "memory-bank"
        memory_bank_dir.mkdir(parents=True)
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()

        # Create all required directories
        for subdir in ["memory-bank", "rules", "plans", "config"]:
            (cortex_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Create core files
        core_files = [
            "projectBrief.md",
            "productContext.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "progress.md",
            "roadmap.md",
        ]
        for fname in core_files:
            (memory_bank_dir / fname).write_text("# Test")

        # Create valid symlinks
        for symlink_name in ["memory-bank", "synapse", "plans"]:
            target = cortex_dir / symlink_name
            target.mkdir(parents=True, exist_ok=True)
            symlink = cursor_dir / symlink_name
            symlink.symlink_to(f"../.cortex/{symlink_name}")

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["memory_bank_initialized"] is True
            assert status["structure_configured"] is True
            assert status["cursor_integration_configured"] is True
            assert status["migration_needed"] is False
