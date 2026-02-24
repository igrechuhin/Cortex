"""Tool analyzer for health-check analysis."""

import ast
from pathlib import Path

from pydantic import BaseModel

from cortex.health_check.models import (
    MergeOpportunity,
    OptimizationOpportunity,
    ToolAnalysisResult,
)
from cortex.health_check.similarity_engine import SimilarityEngine


class AnalyzedTool(BaseModel):
    """Structured metadata for an MCP tool discovered in source code."""

    name: str
    params: list[str]
    docstring: str
    body: str
    signature: str


ToolFuncNode = ast.FunctionDef | ast.AsyncFunctionDef


class ToolAnalyzer:
    """Analyzes MCP tools for merge and optimization opportunities."""

    def __init__(
        self, tools_dir: Path, similarity_engine: SimilarityEngine | None = None
    ):
        """Initialize tool analyzer.

        Args:
            tools_dir: Directory containing tool implementations
            similarity_engine: Similarity engine instance. If None, creates new one.
        """
        self.tools_dir = Path(tools_dir)
        self.similarity_engine = similarity_engine or SimilarityEngine()

    async def analyze(self) -> ToolAnalysisResult:
        """Analyze all tools for merge and optimization opportunities.

        Returns:
            Analysis result with merge and optimization opportunities
        """
        tools = await self._scan_tools()
        merge_opportunities = await self._find_merge_opportunities(tools)
        consolidation_opportunities = await self._find_consolidation_opportunities(
            tools
        )
        optimization_opportunities = await self._find_optimization_opportunities(tools)

        return ToolAnalysisResult(
            total=len(tools),
            merge_opportunities=merge_opportunities,
            consolidation_opportunities=consolidation_opportunities,
            optimization_opportunities=optimization_opportunities,
        )

    async def get_registered_tools(self) -> dict[str, AnalyzedTool]:
        """Return mapping of MCP tools discovered in tools_dir.

        Public wrapper around the internal _scan_tools helper so callers do not
        depend on a private method.
        """
        return await self._scan_tools()

    async def _scan_tools(self) -> dict[str, AnalyzedTool]:
        """Scan all tool files and extract tool information.

        Returns:
            Dictionary mapping tool names to tool metadata
        """
        tools: dict[str, AnalyzedTool] = {}

        if not self.tools_dir.exists():
            return tools

        for file_path in self.tools_dir.glob("*.py"):
            try:
                file_tools = self._extract_tools_from_file(file_path)
                tools.update(file_tools)
            except Exception:
                # Skip files that can't be parsed
                continue

        return tools

    def _extract_tools_from_file(self, file_path: Path) -> dict[str, AnalyzedTool]:
        """Extract tool information from a Python file.

        Args:
            file_path: Path to Python file

        Returns:
            Dictionary mapping tool names to tool metadata
        """
        tools: dict[str, AnalyzedTool] = {}

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_node: ToolFuncNode = node
                    # Check if function has @mcp.tool() decorator
                    if self._has_mcp_tool_decorator(func_node):
                        tool_info = self._extract_tool_info(func_node, content)
                        if tool_info:
                            tool_name = tool_info.name
                            tools[tool_name] = tool_info
        except Exception:
            # Skip files that can't be parsed
            pass

        return tools

    def _has_mcp_tool_decorator(self, node: ToolFuncNode) -> bool:
        """Check if function has @mcp.tool() decorator.

        Args:
            node: AST function node

        Returns:
            True if function has @mcp.tool() decorator
        """
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if (
                        isinstance(decorator.func.value, ast.Name)
                        and decorator.func.value.id == "mcp"
                        and decorator.func.attr == "tool"
                    ):
                        return True
            elif isinstance(decorator, ast.Attribute):
                if (
                    isinstance(decorator.value, ast.Name)
                    and decorator.value.id == "mcp"
                    and decorator.attr == "tool"
                ):
                    return True

        return False

    def _extract_tool_info(
        self, node: ToolFuncNode, file_content: str
    ) -> AnalyzedTool | None:
        """Extract tool information from function node.

        Args:
            node: AST function node
            file_content: Full file content

        Returns:
            Dictionary with tool information or None
        """
        # Extract function signature
        params = [arg.arg for arg in node.args.args]
        docstring = ast.get_docstring(node) or ""

        # Extract function body (first 500 chars for similarity)
        start_line = node.lineno - 1
        end_line = node.end_lineno or start_line + 1
        lines = file_content.split("\n")
        body_lines = lines[start_line:end_line]
        body = "\n".join(body_lines[:50])  # First 50 lines

        return AnalyzedTool(
            name=node.name,
            params=params,
            docstring=docstring,
            body=body,
            signature=f"{node.name}({', '.join(params)})",
        )

    async def _find_merge_opportunities(
        self, tools: dict[str, AnalyzedTool]
    ) -> list[MergeOpportunity]:
        """Find merge opportunities between tools.

        Args:
            tools: Dictionary of tool names to tool metadata

        Returns:
            List of merge opportunities
        """
        opportunities: list[MergeOpportunity] = []
        tool_list = list(tools.items())

        for i, (name1, tool1) in enumerate(tool_list):
            for name2, tool2 in tool_list[i + 1 :]:
                # Compare docstrings and signatures
                doc1 = tool1.docstring
                doc2 = tool2.docstring
                sig1 = tool1.signature
                sig2 = tool2.signature

                similarity = self.similarity_engine.calculate_content_similarity(
                    doc1 + sig1, doc2 + sig2
                )

                if similarity >= 0.75:  # High confidence threshold
                    opportunities.append(
                        MergeOpportunity(
                            files=[name1, name2],
                            similarity=similarity,
                            merge_suggestion=f"Consider merging {name1} and {name2}",
                            quality_impact="positive",
                            estimated_savings=(
                                f"{int((1 - similarity) * 100)}% reduction"
                            ),
                        )
                    )

        return opportunities

    async def _find_consolidation_opportunities(
        self, tools: dict[str, AnalyzedTool]
    ) -> list[MergeOpportunity]:
        """Find consolidation opportunities (similar functionality).

        Args:
            tools: Dictionary of tool names to tool metadata

        Returns:
            List of consolidation opportunities
        """
        opportunities: list[MergeOpportunity] = []
        tool_list = list(tools.items())

        for i, (name1, tool1) in enumerate(tool_list):
            for name2, tool2 in tool_list[i + 1 :]:
                param_overlap = self._calculate_param_overlap(tool1, tool2)
                body_similarity = self._calculate_body_similarity(tool1, tool2)

                # If high parameter overlap and body similarity
                if param_overlap > 0.6 and body_similarity > 0.65:
                    opportunities.append(
                        MergeOpportunity(
                            files=[name1, name2],
                            similarity=(param_overlap + body_similarity) / 2,
                            merge_suggestion=f"Consider consolidating {name1} and {name2} (similar parameters and implementation)",
                            quality_impact="positive",
                            estimated_savings="Reduced maintenance overhead",
                        )
                    )

        return opportunities

    def _calculate_param_overlap(
        self, tool1: AnalyzedTool, tool2: AnalyzedTool
    ) -> float:
        """Calculate parameter overlap between two tools.

        Args:
            tool1: First tool metadata
            tool2: Second tool metadata

        Returns:
            Parameter overlap ratio (0.0-1.0)
        """
        params1_list = tool1.params
        params2_list = tool2.params

        # Convert to sets of strings
        params1: set[str] = set(params1_list)
        params2: set[str] = set(params2_list)

        union = params1 | params2
        return len(params1 & params2) / len(union) if union else 0.0

    def _calculate_body_similarity(
        self, tool1: AnalyzedTool, tool2: AnalyzedTool
    ) -> float:
        """Calculate body similarity between two tools.

        Args:
            tool1: First tool metadata
            tool2: Second tool metadata

        Returns:
            Body similarity ratio (0.0-1.0)
        """
        body1 = tool1.body
        body2 = tool2.body
        return self.similarity_engine.calculate_content_similarity(body1, body2)

    async def _find_optimization_opportunities(
        self, tools: dict[str, AnalyzedTool]
    ) -> list[OptimizationOpportunity]:
        """Find optimization opportunities in tools.

        Args:
            tools: Dictionary of tool names to tool metadata

        Returns:
            List of optimization opportunities
        """
        opportunities: list[OptimizationOpportunity] = []

        for name, tool in tools.items():
            docstring = tool.docstring

            # Check for very long docstrings (potential split)
            if len(docstring) > 5000:
                opportunities.append(
                    OptimizationOpportunity(
                        file=name,
                        issue=f"Very long docstring ({len(docstring)} chars)",
                        recommendation="Consider splitting documentation",
                        estimated_improvement="Improved readability",
                    )
                )

            # Check for missing docstrings
            if not docstring or len(docstring) < 50:
                opportunities.append(
                    OptimizationOpportunity(
                        file=name,
                        issue="Missing or very short docstring",
                        recommendation="Add comprehensive documentation",
                        estimated_improvement="Better tool discoverability",
                    )
                )

        return opportunities
