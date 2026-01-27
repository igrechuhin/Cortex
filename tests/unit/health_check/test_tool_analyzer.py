"""Tests for tool analyzer."""

from pathlib import Path

import pytest

from cortex.health_check.tool_analyzer import ToolAnalyzer


class TestToolAnalyzer:
    """Test tool analyzer functionality."""

    @pytest.fixture
    def tools_dir(self, tmp_path: Path) -> Path:
        """Create temporary tools directory."""
        return tmp_path

    @pytest.fixture
    def analyzer(self, tools_dir: Path) -> ToolAnalyzer:
        """Create tool analyzer instance."""
        return ToolAnalyzer(tools_dir)

    @pytest.mark.asyncio
    async def test_analyze_no_tools_dir(self, analyzer: ToolAnalyzer):
        """Test analyze when tools directory doesn't exist."""
        result = await analyzer.analyze()
        assert "total" in result
        assert result["total"] == 0
        assert result["merge_opportunities"] == []
        assert result["consolidation_opportunities"] == []
        assert result["optimization_opportunities"] == []

    def test_calculate_param_overlap(self, analyzer: ToolAnalyzer):
        """Test calculating parameter overlap."""
        tool1 = {"params": ["param1", "param2"]}
        tool2 = {"params": ["param1", "param3"]}
        overlap = analyzer._calculate_param_overlap(tool1, tool2)  # type: ignore[attr-defined]
        assert 0.0 <= overlap <= 1.0
        assert overlap > 0.0  # Should have some overlap

    def test_calculate_body_similarity(self, analyzer: ToolAnalyzer):
        """Test calculating body similarity."""
        tool1 = {"body": "This is test content."}
        tool2 = {"body": "This is test content."}
        similarity = analyzer._calculate_body_similarity(tool1, tool2)  # type: ignore[attr-defined]
        assert similarity == 1.0

    @pytest.mark.asyncio
    async def test_find_consolidation_opportunities(self, analyzer: ToolAnalyzer):
        """Test finding consolidation opportunities."""
        tools = {
            "tool1": {
                "params": ["param1", "param2"],
                "body": "This is test content.",
            },
            "tool2": {
                "params": ["param1", "param2"],
                "body": "This is test content.",
            },
        }
        opportunities = await analyzer._find_consolidation_opportunities(tools)  # type: ignore[attr-defined]
        assert len(opportunities) > 0

    @pytest.mark.asyncio
    async def test_find_merge_opportunities(self, analyzer: ToolAnalyzer):
        """Test finding merge opportunities."""
        tools = {
            "tool1": {
                "docstring": "This is test documentation.",
                "signature": "tool1(param1, param2)",
            },
            "tool2": {
                "docstring": "This is test documentation.",
                "signature": "tool2(param1, param2)",
            },
        }
        opportunities = await analyzer._find_merge_opportunities(tools)  # type: ignore[attr-defined]
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio
    async def test_find_optimization_opportunities(self, analyzer: ToolAnalyzer):
        """Test finding optimization opportunities."""
        tools = {
            "tool1": {"docstring": "Short doc."},
            "tool2": {"docstring": ""},
        }
        opportunities = await analyzer._find_optimization_opportunities(tools)  # type: ignore[attr-defined]
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio
    async def test_scan_tools_no_dir(self, analyzer: ToolAnalyzer):
        """Test scanning tools when directory doesn't exist."""
        tools = await analyzer._scan_tools()  # type: ignore[attr-defined]
        assert tools == {}

    def test_extract_tools_from_file(self, analyzer: ToolAnalyzer, tmp_path: Path):
        """Test extracting tools from a Python file."""
        test_file = tmp_path / "test_tools.py"
        _ = test_file.write_text(
            '''"""Test file."""
import mcp

@mcp.tool()
def test_tool(param1: str) -> str:
    """Test tool."""
    return "test"
'''
        )
        tools = analyzer._extract_tools_from_file(test_file)  # type: ignore[attr-defined]
        assert "test_tool" in tools

    def test_has_mcp_tool_decorator(self, analyzer: ToolAnalyzer):
        """Test checking for MCP tool decorator."""
        import ast

        code = "@mcp.tool()\ndef test(): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert analyzer._has_mcp_tool_decorator(func_node) is True  # type: ignore[attr-defined]

    def test_extract_tool_info(self, analyzer: ToolAnalyzer):
        """Test extracting tool information from function node."""
        import ast

        code = '''@mcp.tool()
def test_tool(param1: str, param2: int) -> str:
    """Test tool docstring."""
    return "test"
'''
        tree = ast.parse(code)
        func_node = tree.body[0]
        tool_info = analyzer._extract_tool_info(func_node, code)  # type: ignore[attr-defined]
        assert tool_info is not None
        assert tool_info["name"] == "test_tool"
        params = tool_info.get("params", [])
        assert isinstance(params, list)
        assert "param1" in params
        assert "param2" in params

    def test_calculate_param_overlap_no_overlap(self, analyzer: ToolAnalyzer):
        """Test calculating parameter overlap with no overlap."""
        tool1: dict[str, object] = {"params": ["param1", "param2"]}
        tool2: dict[str, object] = {"params": ["param3", "param4"]}
        overlap = analyzer._calculate_param_overlap(tool1, tool2)  # type: ignore[attr-defined]
        assert overlap == 0.0

    def test_calculate_param_overlap_empty(self, analyzer: ToolAnalyzer):
        """Test calculating parameter overlap with empty params."""
        tool1: dict[str, object] = {"params": []}
        tool2: dict[str, object] = {"params": []}
        overlap = analyzer._calculate_param_overlap(tool1, tool2)  # type: ignore[attr-defined]
        assert overlap == 0.0
