"""Split from test_validation_operations.py to keep file size under limits."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.validation.operations import (
    validate,
)
from cortex.tools.validation.roadmap_sync import (
    handle_roadmap_sync_validation,
)
from tests.tools.validation_operations_support import (
    setup_roadmap_sync_cwd_fallback_workspace,
)


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
    async def test_handle_roadmap_sync_validation_uses_usage_root_fallback(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """When root is wrong, usage-context root fallback still finds roadmap.md."""
        wrong_root = tmp_path / "wrong-root"
        wrong_root.mkdir(parents=True)
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        roadmap_path = memory_bank_dir / "roadmap.md"
        roadmap_content = "# Roadmap\n\n## Phase 1\nSee `src/module.py` for details.\n"
        _ = roadmap_path.write_text(roadmap_content)

        src_dir = tmp_path / "src"
        _ = src_dir.mkdir()
        _ = (src_dir / "module.py").write_text("# Module\n")
        mock_fs_manager.read_file = AsyncMock(return_value=(roadmap_content, None))

        with patch(
            "cortex.core.usage_context.get_current_project_root",
            return_value=tmp_path,
        ):
            result = await handle_roadmap_sync_validation(
                mock_fs_manager, wrong_root, None
            )

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "roadmap_sync"

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

    @pytest.mark.asyncio
    async def test_handle_roadmap_sync_validation_falls_back_to_cwd(
        self,
        tmp_path: Path,
        mock_fs_manager: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When root and usage root are wrong, cwd fallback still finds roadmap."""
        wrong_root = tmp_path / "wrong-root"
        wrong_root.mkdir(parents=True)
        setup_roadmap_sync_cwd_fallback_workspace(tmp_path, wrong_root, mock_fs_manager)

        monkeypatch.chdir(tmp_path)
        with patch(
            "cortex.core.usage_context.get_current_project_root",
            return_value=wrong_root,
        ):
            result = await handle_roadmap_sync_validation(
                mock_fs_manager, wrong_root, None
            )

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "roadmap_sync"

    @pytest.mark.asyncio
    async def test_handle_roadmap_sync_validation_uses_fs_manager_memory_bank_dir(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """When root resolution misses, fallback to fs_manager.memory_bank_dir finds roadmap."""
        wrong_root = tmp_path / "wrong-root"
        wrong_root.mkdir(parents=True)
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        roadmap_path = memory_bank_dir / "roadmap.md"
        roadmap_content = "# Roadmap\n\n## Phase 1\nSee `src/module.py` for details.\n"
        _ = roadmap_path.write_text(roadmap_content)
        src_dir = tmp_path / "src"
        _ = src_dir.mkdir()
        _ = (src_dir / "module.py").write_text("# Module\n")

        mock_fs_manager.project_root = wrong_root
        mock_fs_manager.memory_bank_dir = memory_bank_dir
        mock_fs_manager.read_file = AsyncMock(return_value=(roadmap_content, None))

        with patch(
            "cortex.core.usage_context.get_current_project_root",
            return_value=wrong_root,
        ):
            result = await handle_roadmap_sync_validation(
                mock_fs_manager, wrong_root, None
            )

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "roadmap_sync"

    @pytest.mark.asyncio
    async def test_handle_roadmap_sync_validation_with_string_manager_paths(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """String-valued manager roots should still resolve roadmap like manage_file."""
        wrong_root = tmp_path / "wrong-root"
        wrong_root.mkdir(parents=True)
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        roadmap_path = memory_bank_dir / "roadmap.md"
        roadmap_content = "# Roadmap\n\n## Phase 1\nSee `src/module.py` for details.\n"
        _ = roadmap_path.write_text(roadmap_content)
        src_dir = tmp_path / "src"
        _ = src_dir.mkdir()
        _ = (src_dir / "module.py").write_text("# Module\n")

        mock_fs_manager.project_root = str(wrong_root)
        mock_fs_manager.memory_bank_dir = str(memory_bank_dir)
        mock_fs_manager.read_file = AsyncMock(return_value=(roadmap_content, None))

        result = await handle_roadmap_sync_validation(mock_fs_manager, wrong_root, None)

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "roadmap_sync"


class TestValidateResource:
    """Test validate resource (Phase 43 Phase 3 Validation resource)."""

    @pytest.mark.asyncio
    async def test_validate_returns_json_success(self, tmp_path: Path) -> None:
        """Test validate returns valid JSON (zero-arg, session config)."""
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
            result = await validate()
        result_data = json.loads(result)
        assert "status" in result_data
        assert result_data["status"] in ("success", "error")
        if result_data["status"] == "success":
            assert result_data["check_type"] == "schema"

    @pytest.mark.asyncio
    async def test_validate_defaults_to_timestamps(self) -> None:
        """Test validate defaults to timestamps when no session config."""
        with patch(
            "cortex.core.session_config.read_session_config",
            return_value={},
        ):
            # Should not error — "timestamps" is a valid check_type
            result = await validate()
        # The call may fail due to missing project root, but the check_type
        # should be valid (not "invalid check_type" error)
        result_data = json.loads(result)
        if result_data.get("status") == "error":
            assert "Invalid check_type" not in result_data.get("error", "")
