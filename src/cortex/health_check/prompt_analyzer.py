"""Prompt analyzer for health-check analysis."""

import re
from pathlib import Path

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.health_check.models import (
    MergeOpportunity,
    OptimizationOpportunity,
    PromptAnalysisResult,
)
from cortex.health_check.similarity_engine import SimilarityEngine


class PromptAnalyzer:
    """Analyzes prompts for merge and optimization opportunities."""

    def __init__(
        self, project_root: Path, similarity_engine: SimilarityEngine | None = None
    ):
        """Initialize prompt analyzer.

        Args:
            project_root: Root directory of the project
            similarity_engine: Similarity engine instance. If None, creates new one.
        """
        self.project_root = Path(project_root)
        self.similarity_engine = similarity_engine or SimilarityEngine()
        self.prompts_dir = (
            get_cortex_path(self.project_root, CortexResourceType.CORTEX_DIR)
            / "synapse"
            / "prompts"
        )

    async def analyze(self) -> PromptAnalysisResult:
        """Analyze all prompts for merge and optimization opportunities.

        Returns:
            Analysis result with merge and optimization opportunities
        """
        prompts = await self._scan_prompts()
        merge_opportunities = await self._find_merge_opportunities(prompts)
        optimization_opportunities = await self._find_optimization_opportunities(
            prompts
        )

        return PromptAnalysisResult(
            total=len(prompts),
            merge_opportunities=merge_opportunities,
            optimization_opportunities=optimization_opportunities,
        )

    async def _scan_prompts(self) -> dict[str, str]:
        """Scan all prompt files.

        Returns:
            Dictionary mapping file names to content
        """
        prompts: dict[str, str] = {}

        if not self.prompts_dir.exists():
            return prompts

        for file_path in self.prompts_dir.glob("*.md"):
            try:
                async with open_async_text_file(file_path, "r", "utf-8") as f:
                    content = await f.read()
                    prompts[file_path.name] = content
            except Exception:
                # Skip files that can't be read
                continue

        return prompts

    def _extract_sections(self, content: str) -> list[str]:
        """Extract sections from markdown content.

        Args:
            content: Markdown content

        Returns:
            List of section contents (text under headings)
        """
        sections: list[str] = []
        lines = content.split("\n")
        current_section: list[str] = []

        for line in lines:
            # Check if line is a heading (starts with #)
            if re.match(r"^#+\s+", line):
                if current_section:
                    sections.append("\n".join(current_section))
                    current_section = []
            else:
                current_section.append(line)

        # Add last section
        if current_section:
            sections.append("\n".join(current_section))

        return sections

    async def _find_merge_opportunities(
        self, prompts: dict[str, str]
    ) -> list[MergeOpportunity]:
        """Find merge opportunities between prompts.

        Args:
            prompts: Dictionary of prompt names to content

        Returns:
            List of merge opportunities
        """
        opportunities: list[MergeOpportunity] = []
        prompt_list = list(prompts.items())

        for i, (name1, content1) in enumerate(prompt_list):
            for name2, content2 in prompt_list[i + 1 :]:
                similarity = self.similarity_engine.calculate_content_similarity(
                    content1, content2
                )

                if similarity >= 0.75:  # High confidence threshold
                    opportunities.append(
                        MergeOpportunity(
                            files=[name1, name2],
                            similarity=similarity,
                            merge_suggestion=f"Consider merging {name1} and {name2}",
                            quality_impact="positive",
                            estimated_savings=f"{int((1 - similarity) * 100)}% reduction",
                        )
                    )

        return opportunities

    async def _find_optimization_opportunities(
        self, prompts: dict[str, str]
    ) -> list[OptimizationOpportunity]:
        """Find optimization opportunities in prompts.

        Args:
            prompts: Dictionary of prompt names to content

        Returns:
            List of optimization opportunities
        """
        opportunities: list[OptimizationOpportunity] = []

        for name, content in prompts.items():
            opportunities.extend(self._check_large_prompt(name, content))
            opportunities.extend(self._check_duplicate_sections(name, content))

        return opportunities

    def _check_large_prompt(
        self, name: str, content: str
    ) -> list[OptimizationOpportunity]:
        """Check for very large prompts.

        Args:
            name: Prompt file name
            content: Prompt content

        Returns:
            List of optimization opportunities
        """
        opportunities: list[OptimizationOpportunity] = []
        token_count = self.similarity_engine.token_counter.count_tokens(content)
        if token_count > 50000:  # Very large prompt
            opportunities.append(
                OptimizationOpportunity(
                    file=name,
                    issue=f"Very large prompt ({token_count} tokens)",
                    recommendation="Consider splitting into smaller prompts",
                    estimated_improvement="Improved maintainability",
                )
            )
        return opportunities

    def _check_duplicate_sections(
        self, name: str, content: str
    ) -> list[OptimizationOpportunity]:
        """Check for duplicate sections within prompt.

        Args:
            name: Prompt file name
            content: Prompt content

        Returns:
            List of optimization opportunities
        """
        opportunities: list[OptimizationOpportunity] = []
        sections = self._extract_sections(content)
        if len(sections) > 1:
            for i, sec1 in enumerate(sections):
                for sec2 in sections[i + 1 :]:
                    sim = self.similarity_engine.calculate_content_similarity(
                        sec1, sec2
                    )
                    if sim > 0.8:  # High similarity within same file
                        opportunities.append(
                            OptimizationOpportunity(
                                file=name,
                                issue=f"Duplicate sections detected (similarity: {sim:.2f})",
                                recommendation="Remove duplicate sections",
                                estimated_improvement="Reduced token usage",
                            )
                        )
                        break
        return opportunities
