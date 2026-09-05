"""Tests for package-relative tool-directory resolution in health checks."""

from pathlib import Path

import pytest

from cortex.health_check.similarity_engine import SimilarityEngine
from cortex.health_check.tool_analyzer import ToolAnalyzer
from cortex.tools.session.health_check_operations import get_tools_dir


class TestGetToolsDir:
    """Tests for get_tools_dir."""

    def test_resolves_without_repo_layout(self, tmp_path: Path):
        """Test resolution does not depend on a src/cortex/tools project layout."""
        # Arrange
        assert not (tmp_path / "src" / "cortex" / "tools").exists()

        # Act
        tools_dir = get_tools_dir()

        # Assert
        assert tools_dir.is_dir()
        assert (tools_dir / "__init__.py").exists()

    @pytest.mark.asyncio
    async def test_resolved_dir_yields_nonzero_tool_count(self):
        """Test the resolved directory contains analyzable tool modules."""
        # Arrange
        analyzer = ToolAnalyzer(get_tools_dir(), SimilarityEngine())

        # Act
        result = await analyzer.analyze()

        # Assert
        assert result.total > 0
