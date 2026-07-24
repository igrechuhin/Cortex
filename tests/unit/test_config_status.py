"""
Unit tests for config_status module.
"""

import json
from pathlib import Path
from unittest.mock import patch

from cortex.core.path_resolver import (
    CortexResourceType,
    get_cortex_path,
)
from cortex.tools.config import get_project_config_status


def _write_core_memory_bank_files(memory_bank_dir: Path) -> None:
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
        _ = (memory_bank_dir / fname).write_text("# Test")


class TestGetProjectConfigStatus:
    """Test get_project_config_status function."""

    def test_memory_bank_initialized(self, tmp_path: Path):
        """Test memory bank initialized detection."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        _write_core_memory_bank_files(memory_bank_dir)

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["memory_bank_initialized"] is True

    def test_memory_bank_not_initialized_missing_files(self, tmp_path: Path):
        """Test memory bank not initialized when files missing."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        # Only create some files, not all
        _ = (memory_bank_dir / "projectBrief.md").write_text("# Test")

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["memory_bank_initialized"] is False

    def test_memory_bank_not_initialized_missing_directory(self, tmp_path: Path):
        """Test memory bank not initialized when directory missing."""
        # Arrange
        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["memory_bank_initialized"] is False

    def test_structure_configured(self, tmp_path: Path):
        """Test structure configured detection."""
        # Arrange
        cortex_dir = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
        for subdir in ["memory-bank", "rules", "plans", "config"]:
            (cortex_dir / subdir).mkdir(parents=True)

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["structure_configured"] is True

    def test_structure_not_configured_missing_dirs(self, tmp_path: Path):
        """Test structure not configured when directories missing."""
        # Arrange
        cortex_dir = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
        cortex_dir.mkdir()
        # Only create some directories
        (cortex_dir / "memory-bank").mkdir()

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["structure_configured"] is False

    def test_codegraph_configured_when_present_in_mcp_json(self, tmp_path: Path):
        """Test codegraph configured detection reads project_root/.mcp.json."""
        # Arrange
        mcp_config = {"mcpServers": {"codegraph": {"command": "codegraph"}}}
        _ = (tmp_path / ".mcp.json").write_text(json.dumps(mcp_config))

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["codegraph_configured"] is True

    def test_codegraph_not_configured_when_mcp_json_missing(self, tmp_path: Path):
        """Test codegraph not configured when .mcp.json is absent."""
        # Arrange – no .mcp.json file

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["codegraph_configured"] is False

    def test_codegraph_not_configured_when_server_absent(self, tmp_path: Path):
        """Test codegraph not configured when .mcp.json lacks the codegraph server."""
        # Arrange
        mcp_config = {"mcpServers": {"cortex": {"command": "cortex"}}}
        _ = (tmp_path / ".mcp.json").write_text(json.dumps(mcp_config))

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["codegraph_configured"] is False

    def test_migration_needed_legacy_root_format(self, tmp_path: Path):
        """Test migration needed when legacy memory-bank/ exists."""
        # Arrange
        legacy_dir = tmp_path / "memory-bank"
        legacy_dir.mkdir()

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
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
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["migration_needed"] is True

    def test_migration_not_needed_when_initialized(self, tmp_path: Path):
        """Test migration not needed when memory bank is initialized."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        _write_core_memory_bank_files(memory_bank_dir)

        # Also create legacy format (should not trigger migration)
        legacy_dir = tmp_path / "memory-bank"
        legacy_dir.mkdir()

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
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
            "cortex.tools.config.status.get_project_root",
            side_effect=Exception("Test error"),
        ):
            # Act
            status = get_project_config_status()

            # Assert
            # Fail-safe assumes configured (all True) to avoid showing setup
            # prompts on error
            # This is safer than showing all prompts when we can't determine status
            assert status["memory_bank_initialized"] is True
            assert status["structure_configured"] is True
            assert status["codegraph_configured"] is True
            assert status["migration_needed"] is False

    def test_fully_configured_project(self, tmp_path: Path):
        """Test fully configured project returns all True except migration."""
        # Arrange
        cortex_dir = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        # Create all required directories
        for subdir in ["memory-bank", "rules", "plans", "config"]:
            (cortex_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Create core files
        _write_core_memory_bank_files(memory_bank_dir)

        mcp_config = {"mcpServers": {"codegraph": {"command": "codegraph"}}}
        _ = (tmp_path / ".mcp.json").write_text(json.dumps(mcp_config))

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            # Act
            status = get_project_config_status()

            # Assert
            assert status["memory_bank_initialized"] is True
            assert status["structure_configured"] is True
            assert status["codegraph_configured"] is True
            assert status["migration_needed"] is False
