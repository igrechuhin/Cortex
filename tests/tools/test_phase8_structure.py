"""
Comprehensive tests for Phase 8: Project Structure Management Tools

This test suite provides comprehensive coverage for:
- check_structure_health() with and without cleanup
- get_structure_info()
- All helper functions and error paths
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from cortex.tools.phase8_structure import (
    build_health_result,
    check_structure_health,
    check_structure_initialized,
    find_stale_plans,
    get_structure_info,
    move_stale_plans,
    perform_archive_stale,
    perform_cleanup_actions,
    perform_fix_symlinks,
    perform_remove_empty,
    record_archive_action,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root."""
    return tmp_path


@pytest.fixture
def mock_structure_manager(tmp_path: Path) -> MagicMock:
    """Create mock StructureManager."""
    manager = MagicMock()

    # Create a real path that exists for testing
    existing_path = tmp_path / ".memory-bank"
    existing_path.mkdir(parents=True, exist_ok=True)

    manager.get_path.return_value = existing_path
    manager.check_structure_health.return_value = {
        "score": 85,
        "grade": "B",
        "status": "good",
        "checks": {"directories": True, "symlinks": True, "config": True},
        "issues": [],
        "recommendations": [],
    }
    manager.get_structure_info.return_value = {
        "version": "1.0.0",
        "structure_type": "standard",
        "components": {"root": "/mock", "plans": "/mock/plans"},
        "health": {"score": 85},
    }
    manager.setup_cursor_integration.return_value = {
        "symlinks_created": [".cursorrules", ".cursorrules-memory-bank"]
    }
    return manager


@pytest.fixture
def healthy_structure(tmp_path: Path) -> Path:
    """Create a healthy structure directory."""
    structure_root = tmp_path / ".memory-bank"
    structure_root.mkdir(parents=True)
    (structure_root / "knowledge").mkdir(parents=True)
    (structure_root / "plans" / "active").mkdir(parents=True)
    (structure_root / "plans" / "completed").mkdir(parents=True)
    (structure_root / "plans" / "archived").mkdir(parents=True)
    (structure_root / "config").mkdir(parents=True)
    return tmp_path


# ============================================================================
# Test check_structure_health() - Basic Functionality
# ============================================================================


class TestCheckStructureHealthBasic:
    """Tests for check_structure_health() basic functionality."""

    async def test_check_structure_health_success(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Test successful structure health check."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await check_structure_health()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert "health" in result
            assert result["health"]["score"] == 85
            assert result["health"]["grade"] == "B"

    async def test_check_structure_health_not_initialized(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Test health check when structure not initialized."""
        # Arrange
        mock_structure_manager.get_path.return_value = Path("/nonexistent")
        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await check_structure_health()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert result["health"]["status"] == "not_initialized"
            assert result["health"]["score"] == 0

    async def test_check_structure_health_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in check_structure_health."""
        # Arrange
        with patch(
            "cortex.tools.phase8_structure.get_project_root",
            side_effect=RuntimeError("Failed to get project root"),
        ):
            # Act
            result_str = await check_structure_health()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is False
            assert "Failed to get project root" in result["error"]

    async def test_check_structure_health_with_custom_root(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Test health check with custom project root."""
        # Arrange
        custom_root = "/custom/project/root"
        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=Path(custom_root),
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await check_structure_health(project_root=custom_root)
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True


# ============================================================================
# Test check_structure_health() - Cleanup Functionality
# ============================================================================


class TestCheckStructureHealthCleanup:
    """Tests for check_structure_health() cleanup functionality."""

    async def test_check_structure_health_with_cleanup_dry_run(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Test health check with cleanup in dry run mode."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await check_structure_health(
                perform_cleanup=True, dry_run=True
            )
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert "cleanup" in result
            assert result["cleanup"]["dry_run"] is True
            assert "actions_performed" in result["cleanup"]

    async def test_check_structure_health_with_cleanup_execute(
        self, healthy_structure: Path, mock_structure_manager: MagicMock
    ) -> None:
        """Test health check with cleanup execution."""

        # Arrange
        def get_path_side_effect(x: str) -> Path:
            paths: dict[str, Path] = {
                "root": healthy_structure / ".memory-bank",
                "plans": healthy_structure / ".memory-bank" / "plans",
            }
            return paths[x]

        mock_structure_manager.get_path.side_effect = get_path_side_effect

        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=healthy_structure,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await check_structure_health(
                perform_cleanup=True, dry_run=False
            )
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert "cleanup" in result
            assert result["cleanup"]["dry_run"] is False

    async def test_check_structure_health_cleanup_specific_actions(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Test cleanup with specific actions only."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await check_structure_health(
                perform_cleanup=True,
                cleanup_actions=["fix_symlinks", "remove_empty"],
                dry_run=True,
            )
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert "cleanup" in result

    async def test_check_structure_health_cleanup_custom_stale_days(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Test cleanup with custom stale days threshold."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await check_structure_health(
                perform_cleanup=True, stale_days=30, dry_run=True
            )
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True


# ============================================================================
# Test get_structure_info()
# ============================================================================


class TestGetStructureInfo:
    """Tests for get_structure_info() tool."""

    async def test_get_structure_info_success(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Test successful structure info retrieval."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await get_structure_info()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert "structure_info" in result
            assert result["structure_info"]["version"] == "1.0.0"

    async def test_get_structure_info_with_custom_root(
        self, mock_structure_manager: MagicMock
    ) -> None:
        """Test structure info with custom project root."""
        # Arrange
        custom_root = "/custom/root"
        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=Path(custom_root),
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await get_structure_info(project_root=custom_root)
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True

    async def test_get_structure_info_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in get_structure_info."""
        # Arrange
        with patch(
            "cortex.tools.phase8_structure.get_project_root",
            side_effect=ValueError("Invalid project root"),
        ):
            # Act
            result_str = await get_structure_info()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is False
            assert "Invalid project root" in result["error"]


# ============================================================================
# Test Helper Functions
# ============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_check_structure_initialized_not_exists(
        self, mock_structure_manager: MagicMock
    ) -> None:
        """Test check_structure_initialized when path doesn't exist."""
        # Arrange
        nonexistent_path = Path("/nonexistent/path")
        mock_structure_manager.get_path.return_value = nonexistent_path

        # Act
        result_str = check_structure_initialized(mock_structure_manager)
        result = json.loads(result_str) if result_str else None

        # Assert
        assert result is not None
        assert result["health"]["status"] == "not_initialized"

    def test_check_structure_initialized_exists(
        self, mock_structure_manager: MagicMock, tmp_path: Path
    ) -> None:
        """Test check_structure_initialized when path exists."""
        # Arrange
        existing_path = tmp_path
        mock_structure_manager.get_path.return_value = existing_path

        # Act
        result = check_structure_initialized(mock_structure_manager)

        # Assert
        assert result is None

    def test_build_health_result(self) -> None:
        """Test build_health_result."""
        # Arrange
        health: dict[str, object] = {"score": 75, "grade": "C", "status": "fair"}

        # Act
        result = build_health_result(health)

        # Assert
        assert result["success"] is True
        assert result["health"] == health
        assert "FAIR" in str(result.get("summary", ""))
        assert result["action_required"] is False

    def test_build_health_result_warning_status(self) -> None:
        """Test build_health_result with warning status."""
        # Arrange
        health: dict[str, object] = {"score": 60, "grade": "D", "status": "warning"}

        # Act
        result = build_health_result(health)

        # Assert
        assert result["action_required"] is True

    def test_find_stale_plans(self, tmp_path: Path) -> None:
        """Test find_stale_plans."""
        # Arrange
        plans_active = tmp_path / "active"
        plans_active.mkdir(parents=True)

        # Create old file  (will be recent due to touch())
        old_plan = plans_active / "old.md"
        _ = old_plan.write_text("old content")

        # Create recent file
        recent_plan = plans_active / "recent.md"
        _ = recent_plan.write_text("recent content")

        # Use a far future threshold so all files are considered stale
        stale_threshold = datetime.now() + timedelta(days=1)

        # Act
        stale_plans = find_stale_plans(plans_active, stale_threshold)

        # Assert
        assert isinstance(stale_plans, list)
        assert len(stale_plans) == 2  # Both files should be stale

    def test_record_archive_action(self) -> None:
        """Test record_archive_action."""
        # Arrange
        report: dict[str, object] = {"actions_performed": []}
        stale_plans = [Path("/plan1.md"), Path("/plan2.md")]

        # Act
        record_archive_action(report, stale_plans)

        # Assert
        actions_raw = report["actions_performed"]
        assert isinstance(actions_raw, list)
        actions = cast(list[dict[str, object]], actions_raw)
        assert len(actions) == 1
        assert actions[0]["action"] == "archive_stale"
        assert actions[0]["stale_plans_found"] == 2

    def test_move_stale_plans(self, tmp_path: Path) -> None:
        """Test move_stale_plans."""
        # Arrange
        plans_archived = tmp_path / "archived"
        plans_active = tmp_path / "active"
        plans_active.mkdir(parents=True)

        plan1 = plans_active / "plan1.md"
        _ = plan1.write_text("content")

        stale_plans = [plan1]
        report: dict[str, object] = {"files_modified": []}

        # Act
        move_stale_plans(plans_archived, stale_plans, report)

        # Assert
        assert plans_archived.exists()
        assert (plans_archived / "plan1.md").exists()
        assert not plan1.exists()
        files_modified_raw = report["files_modified"]
        assert isinstance(files_modified_raw, list)
        files_modified = cast(list[str], files_modified_raw)
        assert len(files_modified) == 1

    def test_perform_cleanup_actions(self, mock_structure_manager: MagicMock) -> None:
        """Test perform_cleanup_actions."""
        # Arrange
        mock_structure_manager.get_path.return_value = Path("/mock")

        # Act
        result = perform_cleanup_actions(
            mock_structure_manager,
            cleanup_actions=["fix_symlinks"],
            stale_days=90,
            dry_run=True,
        )

        # Assert
        assert "dry_run" in result
        assert result["dry_run"] is True
        assert "actions_performed" in result
        assert "post_cleanup_health" in result

    def test_perform_archive_stale(
        self, tmp_path: Path, mock_structure_manager: MagicMock
    ) -> None:
        """Test perform_archive_stale."""
        # Arrange
        plans_active = tmp_path / "active"
        plans_active.mkdir(parents=True)

        def get_path_side_effect(x: str) -> Path:
            paths: dict[str, Path] = {"plans": tmp_path}
            return paths[x]

        mock_structure_manager.get_path.side_effect = get_path_side_effect

        report: dict[str, object] = {
            "actions_performed": [],
            "files_modified": [],
        }

        # Act
        perform_archive_stale(mock_structure_manager, 90, True, report)

        # Assert
        # Should not fail even with no stale plans
        assert isinstance(report["actions_performed"], list)

    def test_perform_fix_symlinks(self, mock_structure_manager: MagicMock) -> None:
        """Test perform_fix_symlinks."""
        # Arrange
        report: dict[str, object] = {"actions_performed": []}

        # Act
        perform_fix_symlinks(mock_structure_manager, report)

        # Assert
        actions_raw = report["actions_performed"]
        assert isinstance(actions_raw, list)
        actions = cast(list[dict[str, object]], actions_raw)
        assert len(actions) == 1
        assert actions[0]["action"] == "fix_symlinks"

    def test_perform_remove_empty(
        self, tmp_path: Path, mock_structure_manager: MagicMock
    ) -> None:
        """Test perform_remove_empty."""
        # Arrange
        plans = tmp_path / "plans"
        (plans / "active").mkdir(parents=True)
        (plans / "completed").mkdir(parents=True)
        (plans / "archived").mkdir(parents=True)

        mock_structure_manager.get_path.return_value = plans
        report: dict[str, object] = {"actions_performed": []}

        # Act
        perform_remove_empty(mock_structure_manager, report)

        # Assert
        actions_raw = report["actions_performed"]
        assert isinstance(actions_raw, list)
        actions = cast(list[dict[str, object]], actions_raw)
        assert len(actions) == 1
        assert actions[0]["action"] == "remove_empty"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for full workflows."""

    async def test_full_health_check_workflow(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Test complete workflow: check health -> perform cleanup -> recheck."""
        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act 1: Initial health check
            result1_str = await check_structure_health()
            result1 = json.loads(result1_str)

            # Assert 1
            assert result1["success"] is True

            # Act 2: Health check with cleanup
            result2_str = await check_structure_health(
                perform_cleanup=True, dry_run=False
            )
            result2 = json.loads(result2_str)

            # Assert 2
            assert result2["success"] is True
            assert "cleanup" in result2

            # Act 3: Get structure info
            info_str = await get_structure_info()
            info = json.loads(info_str)

            # Assert 3
            assert info["success"] is True
            assert "structure_info" in info

    async def test_health_check_all_cleanup_actions(
        self, healthy_structure: Path, mock_structure_manager: MagicMock
    ) -> None:
        """Test health check with all cleanup actions."""

        # Arrange
        def get_path_side_effect(x: str) -> Path:
            paths: dict[str, Path] = {
                "root": healthy_structure / ".memory-bank",
                "plans": healthy_structure / ".memory-bank" / "plans",
            }
            return paths[x]

        mock_structure_manager.get_path.side_effect = get_path_side_effect

        with (
            patch(
                "cortex.tools.phase8_structure.get_project_root",
                return_value=healthy_structure,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            # Act
            result_str = await check_structure_health(
                perform_cleanup=True,
                cleanup_actions=[
                    "archive_stale",
                    "organize_plans",
                    "fix_symlinks",
                    "remove_empty",
                ],
                stale_days=90,
                dry_run=False,
            )
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert "cleanup" in result
            assert "post_cleanup_health" in result["cleanup"]
