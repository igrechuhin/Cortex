"""Rule analyzer for health-check analysis."""

from pathlib import Path

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.health_check.models import (
    MergeOpportunity,
    OptimizationOpportunity,
    RuleAnalysisResult,
)
from cortex.health_check.similarity_engine import SimilarityEngine


class RuleAnalyzer:
    """Analyzes rules for merge and optimization opportunities."""

    def __init__(
        self, project_root: Path, similarity_engine: SimilarityEngine | None = None
    ):
        """Initialize rule analyzer.

        Args:
            project_root: Root directory of the project
            similarity_engine: Similarity engine instance. If None, creates new one.
        """
        self.project_root = Path(project_root)
        self.similarity_engine = similarity_engine or SimilarityEngine()
        self.rules_dir = (
            get_cortex_path(self.project_root, CortexResourceType.CORTEX_DIR)
            / "synapse"
            / "rules"
        )

    async def analyze(self) -> RuleAnalysisResult:
        """Analyze all rules for merge and optimization opportunities.

        Returns:
            Analysis result with merge and optimization opportunities
        """
        rules = await self._scan_rules()
        categories = self._get_categories(rules)
        merge_opportunities = await self._find_merge_opportunities(rules)
        optimization_opportunities = await self._find_optimization_opportunities(rules)

        return RuleAnalysisResult(
            total=len(rules),
            categories=categories,
            merge_opportunities=merge_opportunities,
            optimization_opportunities=optimization_opportunities,
        )

    async def _scan_rules(self) -> dict[str, dict[str, str]]:
        """Scan all rule files organized by category.

        Returns:
            Dictionary mapping category -> file_name -> content
        """
        rules: dict[str, dict[str, str]] = {}

        if not self.rules_dir.exists():
            return rules

        # Scan category directories
        for category_dir in self.rules_dir.iterdir():
            if not category_dir.is_dir():
                continue

            category = category_dir.name
            rules[category] = {}

            # Scan .mdc files in category
            for file_path in category_dir.glob("*.mdc"):
                try:
                    async with open_async_text_file(file_path, "r", "utf-8") as f:
                        content = await f.read()
                        rules[category][file_path.name] = content
                except Exception:
                    # Skip files that can't be read
                    continue

        return rules

    def _get_categories(self, rules: dict[str, dict[str, str]]) -> list[str]:
        """Get list of rule categories.

        Args:
            rules: Dictionary of rules by category

        Returns:
            List of category names
        """
        return list(rules.keys())

    async def _find_merge_opportunities(
        self, rules: dict[str, dict[str, str]]
    ) -> list[MergeOpportunity]:
        """Find merge opportunities between rules.

        Args:
            rules: Dictionary of rules by category

        Returns:
            List of merge opportunities
        """
        opportunities: list[MergeOpportunity] = []

        opportunities.extend(self._find_within_category_opportunities(rules))
        opportunities.extend(self._find_cross_category_opportunities(rules))

        return opportunities

    def _find_within_category_opportunities(
        self, rules: dict[str, dict[str, str]]
    ) -> list[MergeOpportunity]:
        """Find merge opportunities within same category.

        Args:
            rules: Dictionary of rules by category

        Returns:
            List of merge opportunities
        """
        opportunities: list[MergeOpportunity] = []

        for category, category_rules in rules.items():
            rule_list = list(category_rules.items())
            for i, (name1, content1) in enumerate(rule_list):
                for name2, content2 in rule_list[i + 1 :]:
                    similarity = self.similarity_engine.calculate_content_similarity(
                        content1, content2
                    )

                    if similarity >= 0.75:  # High confidence threshold
                        opportunities.append(
                            MergeOpportunity(
                                files=[f"{category}/{name1}", f"{category}/{name2}"],
                                similarity=similarity,
                                merge_suggestion=f"Consider merging {name1} and {name2} in {category}",
                                quality_impact="positive",
                                estimated_savings=f"{int((1 - similarity) * 100)}% reduction",
                            )
                        )

        return opportunities

    def _find_cross_category_opportunities(
        self, rules: dict[str, dict[str, str]]
    ) -> list[MergeOpportunity]:
        """Find merge opportunities across categories.

        Args:
            rules: Dictionary of rules by category

        Returns:
            List of merge opportunities
        """
        opportunities: list[MergeOpportunity] = []
        categories = list(rules.keys())

        for i, cat1 in enumerate(categories):
            for cat2 in categories[i + 1 :]:
                for name1, content1 in rules[cat1].items():
                    for name2, content2 in rules[cat2].items():
                        similarity = (
                            self.similarity_engine.calculate_content_similarity(
                                content1, content2
                            )
                        )

                        if similarity >= 0.80:  # Higher threshold for cross-category
                            opportunities.append(
                                MergeOpportunity(
                                    files=[
                                        f"{cat1}/{name1}",
                                        f"{cat2}/{name2}",
                                    ],
                                    similarity=similarity,
                                    merge_suggestion=f"Consider consolidating {name1} ({cat1}) and {name2} ({cat2})",
                                    quality_impact="positive",
                                    estimated_savings=f"{int((1 - similarity) * 100)}% reduction",
                                )
                            )

        return opportunities

    async def _find_optimization_opportunities(
        self, rules: dict[str, dict[str, str]]
    ) -> list[OptimizationOpportunity]:
        """Find optimization opportunities in rules.

        Args:
            rules: Dictionary of rules by category

        Returns:
            List of optimization opportunities
        """
        opportunities: list[OptimizationOpportunity] = []

        for category, category_rules in rules.items():
            for name, content in category_rules.items():
                # Check for very long rules (potential split opportunity)
                token_count = self.similarity_engine.token_counter.count_tokens(content)
                if token_count > 20000:  # Large rule file
                    opportunities.append(
                        OptimizationOpportunity(
                            file=f"{category}/{name}",
                            issue=f"Very large rule file ({token_count} tokens)",
                            recommendation="Consider splitting into smaller rules",
                            estimated_improvement="Improved maintainability",
                        )
                    )

        return opportunities
