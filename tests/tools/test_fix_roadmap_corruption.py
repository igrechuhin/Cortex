import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.tools.roadmap_corruption import fix_roadmap_corruption


@pytest.mark.asyncio
class TestFixRoadmapCorruption:
    async def test_fix_roadmap_corruption_when_file_missing_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        with patch(
            "cortex.tools.roadmap_corruption.get_project_root",
            return_value=str(tmp_path),
        ):
            # Act
            result_str = await fix_roadmap_corruption(
                project_root=str(tmp_path), dry_run=True
            )
            result = json.loads(result_str)

        # Assert
        assert result["success"] is False
        assert "not found" in result["error_message"]

    async def test_fix_roadmap_corruption_when_dry_run_does_not_modify_file(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        roadmap_path = tmp_path / ".cortex" / "memory-bank" / "roadmap.md"
        roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        original = "Target completion:2026-01-01P\n"
        _ = roadmap_path.write_text(original, encoding="utf-8")

        with patch(
            "cortex.tools.roadmap_corruption.get_project_root",
            return_value=str(tmp_path),
        ):
            # Act
            result_str = await fix_roadmap_corruption(
                project_root=str(tmp_path), dry_run=True
            )
            result = json.loads(result_str)

        # Assert
        assert result["success"] is True
        assert result["corruption_count"] >= 1
        assert roadmap_path.read_text(encoding="utf-8") == original

    async def test_fix_roadmap_corruption_when_not_dry_run_modifies_file(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        roadmap_path = tmp_path / ".cortex" / "memory-bank" / "roadmap.md"
        roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        original = "Target completion:2026-01-01P\n"
        _ = roadmap_path.write_text(original, encoding="utf-8")

        with patch(
            "cortex.tools.roadmap_corruption.get_project_root",
            return_value=str(tmp_path),
        ):
            # Act
            result_str = await fix_roadmap_corruption(
                project_root=str(tmp_path), dry_run=False
            )
            result = json.loads(result_str)

        # Assert
        assert result["success"] is True
        assert result["corruption_count"] >= 1
        updated = roadmap_path.read_text(encoding="utf-8")
        assert "Target completion: 2026-01-01" in updated
