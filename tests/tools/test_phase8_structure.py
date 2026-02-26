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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import JsonDict, ModelDict
from cortex.tools.models import CleanupReport
from cortex.tools.phase8_structure import (
    build_health_result,
    check_structure_health,
    check_structure_health_resource,
    check_structure_initialized,
    find_stale_plans,
    get_project_root_resource,
    get_structure_info,
    get_structure_info_resource,
    move_stale_plans,
    perform_archive_stale,
    perform_cleanup_actions,
    perform_fix_symlinks,
    perform_remove_empty,
    perform_update_index,
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
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
        # Arrange: raise inside impl so error is returned as JSON (not retried as connection)
        with (
            patch(
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure._check_structure_health_impl",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Failed to get project root"),
            ),
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path(custom_root),
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path(custom_root),
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

    async def test_get_structure_info_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in get_structure_info."""
        # Arrange
        with patch(
            "cortex.tools.phase8_structure.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid project root"),
        ):
            # Act
            result_str = await get_structure_info()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is False
            assert "Invalid project root" in result["error"]


# ============================================================================
# Test Phase 8 structure resources (Phase 43 Step 3.2)
# ============================================================================


@pytest.mark.asyncio
class TestPhase8StructureResources:
    """Tests for Phase 8 structure resources (cortex://structure/*)."""

    async def test_get_structure_info_resource_returns_success(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """get_structure_info_resource returns JSON success (Phase 43)."""
        with (
            patch(
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            result_str = await get_structure_info_resource()
            result = json.loads(result_str)
        assert result["success"] is True
        assert "structure_info" in result

    async def test_get_structure_info_resource_uses_cache_on_second_call(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Second call to get_structure_info_resource returns cached result."""
        from cortex.tools import phase8_structure

        phase8_structure.invalidate_structure_resource_cache()
        with (
            patch(
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
            patch(
                "cortex.tools.phase8_structure.get_structure_info",
                new_callable=AsyncMock,
                return_value='{"success": true, "structure_info": {"paths": {}}}',
            ) as mock_get_info,
        ):
            first = await get_structure_info_resource()
            second = await get_structure_info_resource()
        assert first == second
        mock_get_info.assert_called_once()

    async def test_check_structure_health_resource_returns_json(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """check_structure_health_resource returns JSON (read-only, no cleanup)."""
        with (
            patch(
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
            patch(
                "cortex.tools.phase8_structure.check_structure_initialized",
                return_value=None,
            ),
        ):
            result_str = await check_structure_health_resource()
            result = json.loads(result_str)
        assert "score" in result or "success" in result or "error" in result
        assert "cleanup" not in result

    async def test_check_structure_health_resource_uses_cache_on_second_call(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """Second call to check_structure_health_resource returns cached result."""
        from cortex.tools import phase8_structure

        phase8_structure.invalidate_structure_resource_cache()
        with (
            patch(
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
            patch(
                "cortex.tools.phase8_structure.check_structure_initialized",
                return_value=None,
            ),
            patch(
                "cortex.tools.phase8_structure.check_structure_health",
                new_callable=AsyncMock,
                return_value='{"success": true, "score": 90, "grade": "A"}',
            ) as mock_health,
        ):
            first = await check_structure_health_resource()
            second = await check_structure_health_resource()
        assert first == second
        mock_health.assert_called_once()

    async def test_get_project_root_resource_returns_json_with_absolute_path(
        self,
        mock_project_root: Path,
    ) -> None:
        """get_project_root_resource returns JSON with project_root key and absolute path."""
        with patch(
            "cortex.tools.phase8_structure.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ):
            result_str = await get_project_root_resource()
        result = json.loads(result_str)
        assert "project_root" in result
        path = Path(result["project_root"])
        assert path.is_absolute()
        assert path == mock_project_root.resolve()

    async def test_get_project_root_resource_idempotent(
        self,
        mock_project_root: Path,
    ) -> None:
        """Two consecutive reads of project root resource return the same path."""
        with patch(
            "cortex.tools.phase8_structure.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ):
            first = await get_project_root_resource()
            second = await get_project_root_resource()
        first_data = json.loads(first)
        second_data = json.loads(second)
        assert first_data["project_root"] == second_data["project_root"]

    async def test_get_project_root_resource_resolution_invoked(
        self,
        mock_project_root: Path,
    ) -> None:
        """get_project_root_resource invokes resolve_project_root_async and returns result."""
        from cortex.tools import phase8_structure

        phase8_structure.invalidate_structure_resource_cache("project/root")
        with patch(
            "cortex.tools.phase8_structure.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ) as resolve_mock:
            result_str = await get_project_root_resource()
        resolve_mock.assert_awaited_once_with(None, None)
        result = json.loads(result_str)
        assert result["project_root"] == str(mock_project_root.resolve())


# ============================================================================
# Test Helper Functions
# ============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_invalidate_structure_resource_cache_with_key(self) -> None:
        """invalidate_structure_resource_cache with key invalidates that entry."""
        from cortex.tools import phase8_structure

        phase8_structure.invalidate_structure_resource_cache("structure/info")

    def test_invalidate_structure_resource_cache_clear_all(self) -> None:
        """invalidate_structure_resource_cache with None clears all."""
        from cortex.tools import phase8_structure

        phase8_structure.invalidate_structure_resource_cache()

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
        health: ModelDict = {"score": 75, "grade": "C", "status": "fair"}

        # Act
        result = build_health_result(health)

        # Assert
        assert result.success is True
        assert isinstance(result.health, JsonDict)
        assert "FAIR" in str(result.summary)
        assert result.action_required is False

    def test_build_health_result_warning_status(self) -> None:
        """Test build_health_result with warning status."""
        # Arrange
        health: ModelDict = {"score": 60, "grade": "D", "status": "warning"}

        # Act
        result = build_health_result(health)

        # Assert
        assert result.action_required is True

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
        report = CleanupReport(
            dry_run=True,
            actions_performed=[],
            files_modified=[],
            recommendations=[],
            post_cleanup_health=JsonDict.from_dict({}),
        )
        stale_plans = [Path("/plan1.md"), Path("/plan2.md")]

        # Act
        record_archive_action(report, stale_plans)

        # Assert
        assert len(report.actions_performed) == 1
        assert report.actions_performed[0].action == "archive_stale"
        assert report.actions_performed[0].stale_plans_found == 2

    def test_move_stale_plans(self, tmp_path: Path) -> None:
        """Test move_stale_plans."""
        # Arrange
        plans_archived = tmp_path / "archived"
        plans_active = tmp_path / "active"
        plans_active.mkdir(parents=True)

        plan1 = plans_active / "plan1.md"
        _ = plan1.write_text("content")

        stale_plans = [plan1]
        report = CleanupReport(
            dry_run=False,
            actions_performed=[],
            files_modified=[],
            recommendations=[],
            post_cleanup_health=JsonDict.from_dict({}),
        )

        # Act
        move_stale_plans(plans_archived, stale_plans, report)

        # Assert
        assert plans_archived.exists()
        assert (plans_archived / "plan1.md").exists()
        assert not plan1.exists()
        assert len(report.files_modified) == 1

    @pytest.mark.asyncio
    async def test_perform_cleanup_actions(
        self, mock_structure_manager: MagicMock, tmp_path: Path
    ) -> None:
        """Test perform_cleanup_actions."""
        # Arrange
        mock_structure_manager.get_path.return_value = Path("/mock")

        # Act
        result = await perform_cleanup_actions(
            mock_structure_manager,
            cleanup_actions=["fix_symlinks"],
            stale_days=90,
            dry_run=True,
            project_root=tmp_path,
        )

        # Assert
        assert result.dry_run is True
        assert len(result.actions_performed) >= 0
        assert result.post_cleanup_health is not None

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

        report = CleanupReport(
            dry_run=True,
            actions_performed=[],
            files_modified=[],
            recommendations=[],
            post_cleanup_health=JsonDict.from_dict({}),
        )

        # Act
        perform_archive_stale(mock_structure_manager, 90, True, report)

        # Assert
        # Should not fail even with no stale plans
        assert isinstance(report.actions_performed, list)

    def test_perform_fix_symlinks(self, mock_structure_manager: MagicMock) -> None:
        """Test perform_fix_symlinks."""
        # Arrange
        report = CleanupReport(
            dry_run=True,
            actions_performed=[],
            files_modified=[],
            recommendations=[],
            post_cleanup_health=JsonDict.from_dict({}),
        )

        # Act
        perform_fix_symlinks(mock_structure_manager, report)

        # Assert
        assert len(report.actions_performed) == 1
        assert report.actions_performed[0].action == "fix_symlinks"

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
        report = CleanupReport(
            dry_run=True,
            actions_performed=[],
            files_modified=[],
            recommendations=[],
            post_cleanup_health=JsonDict.from_dict({}),
        )

        # Act
        perform_remove_empty(mock_structure_manager, report)

        # Assert
        assert len(report.actions_performed) == 1
        assert report.actions_performed[0].action == "remove_empty"


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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
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
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
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


class TestPerformUpdateIndex:
    """Tests for perform_update_index() function."""

    @pytest.mark.asyncio
    async def test_perform_update_index_dry_run(self, tmp_path: Path) -> None:
        """Test update_index in dry run mode."""
        # Arrange
        from cortex.core.path_resolver import CortexResourceType, get_cortex_path

        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True, exist_ok=True)

        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("# Test File\n\nContent here.")

        report = CleanupReport(
            dry_run=True,
            actions_performed=[],
            files_modified=[],
            recommendations=[],
            post_cleanup_health=JsonDict.from_dict({}),
        )

        # Act
        await perform_update_index(tmp_path, dry_run=True, report=report)

        # Assert
        assert len(report.actions_performed) == 1
        action = report.actions_performed[0]
        assert action.action == "update_index"
        assert "test.md" in action.files
        assert len(report.files_modified) == 1
        assert "Would refresh" in report.files_modified[0]

    @pytest.mark.asyncio
    async def test_perform_update_index_execute(self, tmp_path: Path) -> None:
        """Test update_index execution updates metadata."""
        # Arrange
        from cortex.core.path_resolver import CortexResourceType, get_cortex_path
        from cortex.managers.initialization import get_managers

        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True, exist_ok=True)

        test_file = memory_bank_dir / "test.md"
        content = "# Test File\n\nContent here."
        _ = test_file.write_text(content)

        report = CleanupReport(
            dry_run=False,
            actions_performed=[],
            files_modified=[],
            recommendations=[],
            post_cleanup_health=JsonDict.from_dict({}),
        )

        # Act
        await perform_update_index(tmp_path, dry_run=False, report=report)

        # Assert
        assert len(report.actions_performed) == 1
        action = report.actions_performed[0]
        assert action.action == "update_index"
        assert "test.md" in action.files
        assert len(report.files_modified) == 1
        assert "Refreshed metadata" in report.files_modified[0]

        # Verify metadata was actually updated
        mgrs = await get_managers(tmp_path)
        metadata = await mgrs.index.get_file_metadata("test.md")
        assert metadata is not None
        assert metadata.exists is True
        assert metadata.size_bytes == len(content.encode("utf-8"))

    @pytest.mark.asyncio
    async def test_perform_update_index_no_memory_bank_dir(
        self, tmp_path: Path
    ) -> None:
        """Test update_index when memory bank directory doesn't exist."""
        # Arrange
        report = CleanupReport(
            dry_run=False,
            actions_performed=[],
            files_modified=[],
            recommendations=[],
            post_cleanup_health=JsonDict.from_dict({}),
        )

        # Act
        await perform_update_index(tmp_path, dry_run=False, report=report)

        # Assert
        assert len(report.actions_performed) == 0
        assert len(report.files_modified) == 0

    @pytest.mark.asyncio
    async def test_perform_update_index_multiple_files(self, tmp_path: Path) -> None:
        """Test update_index with multiple memory bank files."""
        # Arrange
        from cortex.core.path_resolver import CortexResourceType, get_cortex_path

        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True, exist_ok=True)

        file1 = memory_bank_dir / "file1.md"
        file2 = memory_bank_dir / "file2.md"
        _ = file1.write_text("# File 1")
        _ = file2.write_text("# File 2")

        report = CleanupReport(
            dry_run=False,
            actions_performed=[],
            files_modified=[],
            recommendations=[],
            post_cleanup_health=JsonDict.from_dict({}),
        )

        # Act
        await perform_update_index(tmp_path, dry_run=False, report=report)

        # Assert
        assert len(report.actions_performed) == 1
        action = report.actions_performed[0]
        assert action.action == "update_index"
        assert len(action.files) == 2
        assert "file1.md" in action.files
        assert "file2.md" in action.files


# ============================================================================
# Context logging (FastMCP)
# ============================================================================


@pytest.mark.asyncio
class TestPhase8StructureContextLogging:
    """Test Phase 8 structure tools use log_client when ctx is passed."""

    async def test_get_structure_info_calls_log_client_when_ctx_passed(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """When ctx is passed, get_structure_info logs start and completion."""
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.phase8_structure.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            result_str = await get_structure_info(ctx=mock_ctx)
            result = json.loads(result_str)
        assert result["success"] is True
        args_list = [c[0] for c in mock_log.call_args_list]
        levels_and_messages = [(a[1], a[2]) for a in args_list]
        assert ("info", "get_structure_info: starting") in levels_and_messages
        assert ("info", "get_structure_info: completed") in levels_and_messages

    async def test_check_structure_health_calls_log_client_when_ctx_passed(
        self,
        mock_project_root: Path,
        mock_structure_manager: MagicMock,
    ) -> None:
        """When ctx is passed, check_structure_health logs start and completion."""
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.phase8_structure.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.phase8_structure.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase8_structure.StructureManager",
                return_value=mock_structure_manager,
            ),
        ):
            result_str = await check_structure_health(ctx=mock_ctx)
            result = json.loads(result_str)
        assert result["success"] is True
        args_list = [c[0] for c in mock_log.call_args_list]
        levels_and_messages = [(a[1], a[2]) for a in args_list]
        assert ("info", "check_structure_health: starting") in levels_and_messages
        assert ("info", "check_structure_health: completed") in levels_and_messages
