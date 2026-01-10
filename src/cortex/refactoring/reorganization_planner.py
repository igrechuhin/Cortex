"""
Reorganization Planner for MCP Memory Bank

This module plans structural reorganization of Memory Bank files to improve
dependency structure, reduce complexity, and optimize file organization.
"""

from dataclasses import dataclass
from pathlib import Path

from cortex.refactoring.reorganization.analyzer import ReorganizationAnalyzer
from cortex.refactoring.reorganization.executor import (
    ReorganizationAction,
    ReorganizationExecutor,
)
from cortex.refactoring.reorganization.strategies import (
    ReorganizationStrategies,
)

# Re-export for backward compatibility
__all__ = [
    "ReorganizationPlanner",
    "ReorganizationPlan",
    "ReorganizationAction",
]


@dataclass
class ReorganizationPlan:
    """Represents a complete reorganization plan"""

    plan_id: str
    optimization_goal: str  # "dependency_depth", "category_based", "complexity"
    current_structure: dict[str, object]
    proposed_structure: dict[str, object]
    actions: list[ReorganizationAction]
    estimated_impact: dict[str, object]
    risks: list[str]
    benefits: list[str]
    preserve_history: bool = True

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary"""
        return {
            "plan_id": self.plan_id,
            "optimization_goal": self.optimization_goal,
            "current_structure": self.current_structure,
            "proposed_structure": self.proposed_structure,
            "actions": [
                {
                    "type": a.action_type,
                    "source": a.source,
                    "target": a.target,
                    "reason": a.reason,
                    "dependencies_affected": len(a.dependencies_affected),
                }
                for a in self.actions
            ],
            "estimated_impact": self.estimated_impact,
            "risks": self.risks,
            "benefits": self.benefits,
            "preserve_history": self.preserve_history,
        }


class ReorganizationPlanner:
    """
    Plans structural reorganization of Memory Bank files.

    Analyzes current structure and suggests improvements:
    - Optimize dependency depth
    - Group files by category/topic
    - Reduce complexity
    - Improve naming conventions
    """

    def __init__(
        self,
        memory_bank_path: Path | str,
        max_dependency_depth: int = 5,
        enable_categories: bool = True,
    ):
        """
        Initialize the reorganization planner.

        Args:
            memory_bank_path: Path to Memory Bank directory
            max_dependency_depth: Maximum acceptable dependency depth
            enable_categories: Whether to suggest category-based organization
        """
        self.memory_bank_path: Path = Path(memory_bank_path)
        self.max_dependency_depth: int = max_dependency_depth
        self.enable_categories: bool = enable_categories

        self.plan_counter: int = 0

        # Initialize components
        self.analyzer = ReorganizationAnalyzer(
            self.memory_bank_path, max_dependency_depth, enable_categories
        )
        self.strategies = ReorganizationStrategies(self.memory_bank_path)
        self.executor = ReorganizationExecutor(self.memory_bank_path)

    def generate_plan_id(self) -> str:
        """Generate unique plan ID"""
        self.plan_counter += 1
        return f"REORG-{self.plan_counter:04d}"

    async def create_reorganization_plan(
        self,
        optimize_for: str = "dependency_depth",
        structure_data: dict[str, object] | None = None,
        dependency_graph: dict[str, object] | None = None,
    ) -> ReorganizationPlan | None:
        """
        Create a reorganization plan.

        Args:
            optimize_for: Optimization goal ("dependency_depth", "category_based", "complexity")
            structure_data: Structure analysis results
            dependency_graph: Dependency graph data

        Returns:
            Reorganization plan or None if no changes needed
        """
        if not self._validate_reorganization_inputs(structure_data, dependency_graph):
            return None

        assert dependency_graph is not None
        assert structure_data is not None
        current_structure = await self.analyzer.analyze_current_structure(
            structure_data, dependency_graph
        )

        if not self._should_reorganize(current_structure, optimize_for):
            return None

        proposed_structure = await self.strategies.generate_proposed_structure(
            current_structure, optimize_for, dependency_graph
        )

        return await self._build_reorganization_plan(
            current_structure, proposed_structure, optimize_for
        )

    async def preview_reorganization(
        self, plan: ReorganizationPlan, show_details: bool = True
    ) -> dict[str, object]:
        """
        Preview the impact of a reorganization plan.

        Args:
            plan: The reorganization plan to preview
            show_details: Whether to include detailed action breakdown

        Returns:
            Preview information
        """
        from typing import cast

        preview: dict[str, object] = {
            "plan_id": plan.plan_id,
            "optimization_goal": plan.optimization_goal,
            "actions_count": len(plan.actions),
            "estimated_impact": plan.estimated_impact,
            "risks": plan.risks,
            "benefits": plan.benefits,
        }

        if show_details:
            actions_list: list[dict[str, object]] = [
                {
                    "type": a.action_type,
                    "description": f"{a.action_type.upper()}: {Path(a.source).name if a.source else 'N/A'} -> {Path(a.target).name}",
                    "reason": a.reason,
                }
                for a in plan.actions
            ]
            preview["actions"] = cast(list[object], actions_list)

            preview["structure_comparison"] = {
                "current": plan.current_structure.get("organization"),
                "proposed": plan.proposed_structure.get("organization"),
            }

        return preview

    def _validate_reorganization_inputs(
        self,
        structure_data: dict[str, object] | None,
        dependency_graph: dict[str, object] | None,
    ) -> bool:
        """Validate inputs for reorganization plan creation."""
        return structure_data is not None and dependency_graph is not None

    def _should_reorganize(
        self, current_structure: dict[str, object], optimize_for: str
    ) -> bool:
        """Check if reorganization is needed."""
        needs_reorg, _reasons = self.analyzer.needs_reorganization(
            current_structure, optimize_for
        )
        return needs_reorg

    async def _build_reorganization_plan(
        self,
        current_structure: dict[str, object],
        proposed_structure: dict[str, object],
        optimize_for: str,
    ) -> ReorganizationPlan | None:
        """Build the reorganization plan from structures."""
        actions = await self.executor.generate_actions(
            current_structure, proposed_structure, optimize_for
        )

        if not actions:
            return None

        estimated_impact = self.executor.calculate_impact(
            current_structure, proposed_structure, actions
        )
        risks = self.executor.identify_risks(actions, current_structure)
        benefits = self.executor.identify_benefits(
            proposed_structure, current_structure
        )

        return ReorganizationPlan(
            plan_id=self.generate_plan_id(),
            optimization_goal=optimize_for,
            current_structure=current_structure,
            proposed_structure=proposed_structure,
            actions=actions,
            estimated_impact=estimated_impact,
            risks=risks,
            benefits=benefits,
            preserve_history=True,
        )

    # Backward compatibility delegation methods

    def infer_categories(self, files: list[str]) -> dict[str, list[str]]:
        """Delegate to analyzer for backward compatibility."""
        return self.analyzer.infer_categories(files)

    def needs_reorganization(
        self, current_structure: dict[str, object], optimize_for: str
    ) -> tuple[bool, list[str]]:
        """Delegate to analyzer for backward compatibility."""
        return self.analyzer.needs_reorganization(current_structure, optimize_for)

    def optimize_dependency_order(
        self, current_structure: dict[str, object], dependency_graph: dict[str, object]
    ) -> list[str]:
        """Delegate to strategies for backward compatibility."""
        return self.strategies.optimize_dependency_order(
            current_structure, dependency_graph
        )

    def propose_category_structure(
        self, current_structure: dict[str, object]
    ) -> dict[str, list[str]]:
        """Delegate to strategies for backward compatibility."""
        return self.strategies.propose_category_structure(current_structure)

    def propose_simplified_structure(
        self, current_structure: dict[str, object]
    ) -> dict[str, list[str]]:
        """Delegate to strategies for backward compatibility."""
        return self.strategies.propose_simplified_structure(current_structure)

    async def get_all_markdown_files(self) -> list[str]:
        """Delegate to analyzer for backward compatibility."""
        return await self.analyzer.get_all_markdown_files()

    async def analyze_current_structure(
        self, structure_data: dict[str, object], dependency_graph: dict[str, object]
    ) -> dict[str, object]:
        """Delegate to analyzer for backward compatibility."""
        return await self.analyzer.analyze_current_structure(
            structure_data, dependency_graph
        )

    async def generate_proposed_structure(
        self,
        current_structure: dict[str, object],
        optimize_for: str,
        dependency_graph: dict[str, object],
    ) -> dict[str, object]:
        """Delegate to strategies for backward compatibility."""
        return await self.strategies.generate_proposed_structure(
            current_structure, optimize_for, dependency_graph
        )

    async def generate_actions(
        self,
        current_structure: dict[str, object],
        proposed_structure: dict[str, object],
        optimize_for: str,
    ) -> list[ReorganizationAction]:
        """Delegate to executor for backward compatibility."""
        return await self.executor.generate_actions(
            current_structure, proposed_structure, optimize_for
        )

    def calculate_impact(
        self,
        current_structure: dict[str, object],
        proposed_structure: dict[str, object],
        actions: list[ReorganizationAction],
    ) -> dict[str, object]:
        """Delegate to executor for backward compatibility."""
        return self.executor.calculate_impact(
            current_structure, proposed_structure, actions
        )

    def identify_risks(
        self, actions: list[ReorganizationAction], current_structure: dict[str, object]
    ) -> list[str]:
        """Delegate to executor for backward compatibility."""
        return self.executor.identify_risks(actions, current_structure)

    def identify_benefits(
        self,
        proposed_structure: dict[str, object],
        current_structure: dict[str, object],
    ) -> list[str]:
        """Delegate to executor for backward compatibility."""
        return self.executor.identify_benefits(proposed_structure, current_structure)
