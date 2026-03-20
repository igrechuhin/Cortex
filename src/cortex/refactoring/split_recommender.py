"""
Split Recommender for MCP Memory Bank

This module recommends splitting large or complex files into smaller,
more focused components for better context management and maintainability.
Delegates analysis operations to SplitAnalyzer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.models import ModelDict
from cortex.refactoring.models import (
    NewSplitStructure,
    SplitFileInfo,
    SplitImpactMetrics,
    SplitIndexFile,
)

from .split_analyzer import SplitAnalyzer
from .split_generators import SplitAnalyzerProtocol, generate_split_points
from .split_models import SplitPoint, SplitRecommendation

# Re-export for backwards compatibility
__all__ = [
    "SplitPoint",
    "SplitRecommendation",
    "SplitRecommender",
]


class SplitRecommender:
    """
    Recommends file splitting strategies for large or complex files.

    Identifies files that should be split and suggests optimal split points.
    Delegates analysis operations to SplitAnalyzer.
    """

    def __init__(
        self,
        memory_bank_path: Path,
        max_file_size: int = 5000,  # tokens
        max_sections: int = 10,
        min_section_independence: float = 0.6,
    ):
        """
        Initialize the split recommender.

        Args:
            memory_bank_path: Path to Memory Bank directory
            max_file_size: Maximum recommended file size in tokens
            max_sections: Maximum recommended number of sections per file
            min_section_independence: Minimum independence score for split (0-1)
        """
        self.memory_bank_path: Path = Path(memory_bank_path)
        self.max_file_size: int = max_file_size
        self.max_sections: int = max_sections
        self.min_section_independence: float = min_section_independence

        # Create analyzer for file analysis
        self.analyzer: SplitAnalyzerProtocol = SplitAnalyzer(
            max_file_size=max_file_size,
            max_sections=max_sections,
            min_section_independence=min_section_independence,
        )

        self.recommendation_counter: int = 0

    def parse_file_structure(self, content: str) -> list[ModelDict]:
        """
        Parse file into structured sections.

        Delegates to SplitAnalyzer.

        Args:
            content: File content to parse

        Returns:
            List of section dictionaries with heading, level, lines, and content
        """
        return self.analyzer.parse_file_structure(content)

    def generate_recommendation_id(self) -> str:
        """Generate unique recommendation ID"""
        self.recommendation_counter += 1
        return f"SPLIT-{self.recommendation_counter:04d}"

    async def analyze_file(
        self,
        file_path: str,
        content: str | None = None,
        token_count: int | None = None,
    ) -> SplitRecommendation | None:
        """
        Analyze a file and recommend splitting if needed.

        Args:
            file_path: Path to the file to analyze
            content: File content (will read if not provided)
            token_count: Token count (will calculate if not provided)

        Returns:
            Split recommendation or None if file is fine
        """
        content = await _read_and_validate_content(self, file_path, content)
        if content is None:
            return None

        if token_count is None:
            token_count = len(content) // 4

        sections = self.analyzer.parse_file_structure(content)
        should_split, reasons = await self.analyzer.should_split_file(
            file_path, content, token_count, sections
        )

        if not should_split:
            return None

        split_strategy = self.analyzer.determine_split_strategy(
            token_count, len(sections), sections
        )
        split_points = await generate_split_points(
            self, file_path, content, sections, split_strategy
        )

        if not split_points:
            return None

        return _build_recommendation(
            self, file_path, reasons, split_strategy, split_points, token_count
        )

    async def suggest_file_splits(
        self, files: list[str] | None = None
    ) -> list[SplitRecommendation]:
        """
        Suggest splits for multiple files.

        Args:
            files: List of files to analyze (all if None)

        Returns:
            List of split recommendations
        """
        recommendations: list[SplitRecommendation] = []

        # Get files to analyze
        if files is None:
            files = await self.get_all_markdown_files()

        # Analyze each file
        for file_path in files:
            try:
                recommendation = await self.analyze_file(file_path)
                if recommendation:
                    recommendations.append(recommendation)
            except Exception as e:
                from cortex.core.logging_config import logger

                logger.warning(f"Failed to analyze file {file_path} for splitting: {e}")
                continue

        # Sort by estimated impact
        def get_complexity_reduction(r: SplitRecommendation) -> float:
            """Extract complexity reduction from estimated impact."""
            impact = r.estimated_impact
            value = impact.get("complexity_reduction", 0.0)
            if isinstance(value, (int, float)):
                return float(value)
            return 0.0

        recommendations.sort(key=get_complexity_reduction, reverse=True)

        return recommendations

    async def get_all_markdown_files(self) -> list[str]:
        """Get all markdown files in Memory Bank"""
        files: list[str] = []
        if self.memory_bank_path.exists():
            for file_path in self.memory_bank_path.rglob("*.md"):
                if file_path.is_file():
                    files.append(str(file_path))
        return files

    async def read_file(self, file_path: str) -> str:
        """Read file contents"""
        try:
            # Handle both absolute and relative paths
            if Path(file_path).is_absolute():
                full_path = Path(file_path)
            else:
                full_path = self.memory_bank_path / file_path
            async with open_async_text_file(full_path, "r", "utf-8") as f:
                return await f.read()
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to read file {file_path}: {e}")
            return ""

    def get_section_str(self, section: ModelDict, key: str, default: str = "") -> str:
        """Extract string value from section dict with type checking."""
        value = section.get(key, default)
        return str(value) if value is not None else default

    def get_section_int(self, section: ModelDict, key: str, default: int = 0) -> int:
        """Extract int value from section dict with type checking."""
        value = section.get(key, default)
        if isinstance(value, (int, float)):
            return int(value)
        return default

    def get_section_content(self, section: ModelDict) -> str:
        """Extract content from section dict with type checking."""
        content = section.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, (list, tuple)):
            return "\n".join(str(item) for item in content if item is not None)
        return str(content) if content is not None else ""

    def generate_split_filename(self, original_file: str, section_heading: str) -> str:
        """Generate a filename for a split section"""
        original_path = Path(original_file)
        base_name = original_path.stem

        # Slugify section heading
        slug = re.sub(r"[^a-z0-9]+", "-", section_heading.lower()).strip("-")
        slug = slug[:30]  # Limit length

        return f"{original_path.parent}/{base_name}-{slug}.md"

    async def generate_split_points(
        self,
        file_path: str,
        content: str,
        sections: list[ModelDict],
        strategy: str,
    ) -> list[SplitPoint]:
        """
        Generate specific split points based on strategy.

        Delegates to split_generators module.
        """
        return await generate_split_points(self, file_path, content, sections, strategy)

    def calculate_split_impact(
        self,
        file_path: str,
        original_tokens: int,
        split_points: list[SplitPoint],
    ) -> SplitImpactMetrics:
        """Calculate the impact of applying a split"""
        new_file_count = len(split_points) + 1  # +1 for index/main file
        return SplitImpactMetrics(
            original_file_tokens=original_tokens,
            new_file_count=new_file_count,
            average_file_size=(
                original_tokens // new_file_count if new_file_count > 0 else 0
            ),
            complexity_reduction=0.6 if len(split_points) > 2 else 0.3,
            maintainability_improvement=0.7,
            context_loading_improvement=0.5,
            benefits=[
                "Smaller, more focused files",
                "Better context selection granularity",
                "Easier to navigate and maintain",
                "Reduced token usage for specific queries",
            ],
            considerations=[
                "Will need to update links",
                "May need index file for navigation",
                "Dependency structure needs review",
            ],
        )

    def generate_new_structure(
        self, file_path: str, split_points: list[SplitPoint]
    ) -> ModelDict:
        """Generate proposed new file structure"""
        original_path = Path(file_path)

        new_files: list[SplitFileInfo] = []
        for sp in split_points:
            new_files.append(
                SplitFileInfo(
                    filename=sp.suggested_filename,
                    heading=sp.section_heading,
                    tokens=sp.token_count,
                    lines=f"{sp.start_line}-{sp.end_line}",
                )
            )

        # Add index file
        index_file = SplitIndexFile(
            filename=str(original_path),
            purpose="Index file with links to split sections",
            tokens=200,  # Estimated
            content_summary="Overview with links to all split files",
        )

        structure = NewSplitStructure(
            index_file=index_file,
            split_files=new_files,
            total_files=len(new_files) + 1,
        )
        return cast(ModelDict, structure.model_dump(mode="json"))


async def _read_and_validate_content(
    recommender: SplitRecommender,
    file_path: str,
    content: str | None,
) -> str | None:
    """Read and validate file content.

    Args:
        recommender: SplitRecommender instance
        file_path: Path to file
        content: Optional existing content

    Returns:
        Content string or None if read failed
    """
    if content is not None:
        return content

    try:
        return await recommender.read_file(file_path)
    except Exception as e:
        from cortex.core.logging_config import logger

        logger.warning(f"Failed to read file {file_path} for split analysis: {e}")
        return None


def _build_recommendation(
    recommender: SplitRecommender,
    file_path: str,
    reasons: list[str],
    split_strategy: str,
    split_points: list[SplitPoint],
    token_count: int,
) -> SplitRecommendation:
    """Build split recommendation object.

    Args:
        recommender: SplitRecommender instance
        file_path: Path to file
        reasons: List of reasons for splitting
        split_strategy: Split strategy name
        split_points: List of split points
        token_count: Token count

    Returns:
        SplitRecommendation object
    """
    estimated_impact = recommender.calculate_split_impact(
        file_path, token_count, split_points
    )
    estimated_impact_dict = cast(ModelDict, estimated_impact.model_dump(mode="json"))
    new_structure = recommender.generate_new_structure(file_path, split_points)

    return SplitRecommendation(
        recommendation_id=recommender.generate_recommendation_id(),
        file_path=file_path,
        reason=" | ".join(reasons),
        split_strategy=split_strategy,
        split_points=split_points,
        estimated_impact=estimated_impact_dict,
        new_structure=new_structure,
        maintain_dependencies=True,
    )
