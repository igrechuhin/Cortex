"""
Reorganization Planner for MCP Memory Bank

This module plans structural reorganization of Memory Bank files to improve
dependency structure, reduce complexity, and optimize file organization.
"""

from pathlib import Path
from typing import cast

from cortex.core.models import (
    EstimatedImpactMetrics,
    ModelDict,
    ReorganizationActionPreview,
    ReorganizationPreview,
    StructureComparison,
)
from cortex.refactoring.models import (
    DependencyGraphInput,
    MemoryBankStructureData,
    ReorganizationActionModel,
    ReorganizationImpactModel,
    ReorganizationPlanModel,
)
from cortex.refactoring.reorganization.analyzer import ReorganizationAnalyzer
from cortex.refactoring.reorganization.executor import (
    ReorganizationAction,
    ReorganizationExecutor,
)
from cortex.refactoring.reorganization.strategies import (
    ReorganizationStrategies,
)

__all__ = [
    "ReorganizationPlanner",
    "ReorganizationPlanModel",
]


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
        structure_data: MemoryBankStructureData | ModelDict | None = None,
        dependency_graph: DependencyGraphInput | ModelDict | None = None,
    ) -> ReorganizationPlanModel | None:
        """
        Create a reorganization plan.

        Args:
            optimize_for: Optimization goal ("dependency_depth",
            "category_based", "complexity")
            structure_data: Structure analysis results
            dependency_graph: Dependency graph data

        Returns:
            Reorganization plan or None if no changes needed
        """
        if not self._validate_reorganization_inputs(structure_data, dependency_graph):
            return None

        assert dependency_graph is not None
        assert structure_data is not None

        structure_model, graph_model = self._normalize_inputs(
            structure_data, dependency_graph
        )
        structure_dict = cast(ModelDict, structure_model.model_dump(mode="json"))
        graph_dict = cast(ModelDict, graph_model.model_dump(mode="json"))
        current_structure = await self.analyzer.analyze_current_structure(
            structure_dict, graph_dict
        )
        if not self._needs_reorganization(current_structure, optimize_for):
            return None
        proposed_structure = await self.strategies.generate_proposed_structure(
            current_structure, optimize_for, graph_dict
        )
        current_model = MemoryBankStructureData.model_validate(current_structure)
        proposed_model = MemoryBankStructureData.model_validate(proposed_structure)
        return await self._build_reorganization_plan(
            current_model, proposed_model, optimize_for, graph_dict
        )

    def _normalize_inputs(
        self,
        structure_data: MemoryBankStructureData | ModelDict | None,
        dependency_graph: DependencyGraphInput | ModelDict | None,
    ) -> tuple[MemoryBankStructureData, DependencyGraphInput]:
        """Normalize structure and graph inputs."""
        structure_model = (
            structure_data
            if isinstance(structure_data, MemoryBankStructureData)
            else MemoryBankStructureData.model_validate(
                self._normalize_structure_data_input(cast(ModelDict, structure_data))
            )
        )
        graph_model = (
            dependency_graph
            if isinstance(dependency_graph, DependencyGraphInput)
            else DependencyGraphInput.model_validate(dependency_graph)
        )
        return structure_model, graph_model

    def _needs_reorganization(
        self, current_structure: ModelDict, optimize_for: str
    ) -> bool:
        """Check if reorganization is needed."""
        needs_reorg, _reasons = self.analyzer.needs_reorganization(
            current_structure, optimize_for
        )
        return needs_reorg

    async def preview_reorganization(
        self, plan: ReorganizationPlanModel, show_details: bool = True
    ) -> ReorganizationPreview:
        """
        Preview the impact of a reorganization plan.

        Args:
            plan: The reorganization plan to preview
            show_details: Whether to include detailed action breakdown

        Returns:
            ReorganizationPreview with plan impact information
        """
        impact = plan.estimated_impact
        estimated_impact = EstimatedImpactMetrics(
            token_savings=0,
            files_affected=impact.files_moved,
            complexity_reduction=impact.complexity_reduction,
            dependency_depth_reduction=0,
        )

        actions, structure_comparison = self._build_preview_details(plan, show_details)

        return ReorganizationPreview(
            plan_id=plan.plan_id,
            optimization_goal=plan.optimization_goal,
            actions_count=len(plan.actions),
            estimated_impact=estimated_impact,
            risks=plan.risks,
            benefits=plan.benefits,
            actions=actions,
            structure_comparison=structure_comparison,
        )

    def _build_action_previews(
        self, plan: ReorganizationPlanModel
    ) -> list[ReorganizationActionPreview]:
        """Build action previews from plan."""
        actions: list[ReorganizationActionPreview] = []
        for action in plan.actions:
            actions.append(
                ReorganizationActionPreview(
                    type=action.action_type,
                    description=(
                        f"{action.action_type}: {action.source} -> " f"{action.target}"
                    ),
                    reason=action.reason,
                )
            )
        return actions

    def _build_structure_comparison(
        self, plan: ReorganizationPlanModel
    ) -> StructureComparison:
        """Build structure comparison from plan."""
        from cortex.core.models import StructureMetrics

        current_metrics = StructureMetrics(
            total_files=plan.current_structure.total_files,
            max_depth=plan.current_structure.dependency_depth,
            files_by_category={
                k: len(v) for k, v in plan.current_structure.categories.items()
            },
            organization=plan.current_structure.organization,
        )
        proposed_metrics = StructureMetrics(
            total_files=plan.proposed_structure.total_files,
            max_depth=plan.proposed_structure.dependency_depth,
            files_by_category={
                k: len(v) for k, v in plan.proposed_structure.categories.items()
            },
            organization=plan.proposed_structure.organization,
        )
        return StructureComparison(
            current=current_metrics,
            proposed=proposed_metrics,
        )

    def _build_preview_details(
        self, plan: ReorganizationPlanModel, show_details: bool
    ) -> tuple[list[ReorganizationActionPreview], StructureComparison | None]:
        """Build preview details from reorganization plan."""
        actions = self._build_action_previews(plan) if show_details else []
        structure_comparison = (
            self._build_structure_comparison(plan) if show_details else None
        )
        return actions, structure_comparison

    def _validate_reorganization_inputs(
        self,
        structure_data: MemoryBankStructureData | ModelDict | None,
        dependency_graph: DependencyGraphInput | ModelDict | None,
    ) -> bool:
        """Validate inputs for reorganization plan creation."""
        return structure_data is not None and dependency_graph is not None

    @staticmethod
    def _normalize_structure_data_input(structure_data: ModelDict) -> ModelDict:
        """Normalize legacy structure_data shapes for model validation."""
        organization = structure_data.get("organization")
        if isinstance(organization, dict):
            org_type = organization.get("type")
            if isinstance(org_type, str):
                normalized = dict(structure_data)
                normalized["organization"] = org_type
                return normalized
        return structure_data

    def needs_reorganization(
        self, current_structure: MemoryBankStructureData, optimize_for: str
    ) -> tuple[bool, list[str]]:
        """Check whether reorganization is needed for the given goal."""
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        return self.analyzer.needs_reorganization(current_dict, optimize_for)

    def optimize_dependency_order(
        self,
        current_structure: MemoryBankStructureData,
        dependency_graph: DependencyGraphInput,
    ) -> list[str]:
        """Compute an optimized dependency order for current structure."""
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        graph_dict = cast(ModelDict, dependency_graph.model_dump(mode="json"))
        return self.strategies.optimize_dependency_order(current_dict, graph_dict)

    def infer_categories(self, files: list[str]) -> dict[str, list[str]]:
        """Infer file categories based on names."""
        return self.analyzer.infer_categories(files)

    def propose_category_structure(
        self, current_structure: MemoryBankStructureData
    ) -> dict[str, list[str]]:
        """Propose category structure mapping."""
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        return self.strategies.propose_category_structure(current_dict)

    def propose_simplified_structure(
        self, current_structure: MemoryBankStructureData
    ) -> dict[str, list[str]]:
        """Propose simplified structure mapping."""
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        return self.strategies.propose_simplified_structure(current_dict)

    async def get_all_markdown_files(self) -> list[str]:
        """List all markdown files in the memory bank path."""
        return await self.analyzer.get_all_markdown_files()

    async def analyze_current_structure(
        self,
        structure_data: MemoryBankStructureData,
        dependency_graph: DependencyGraphInput,
    ) -> MemoryBankStructureData:
        """Analyze and enrich current structure using the dependency graph."""
        structure_dict = cast(ModelDict, structure_data.model_dump(mode="json"))
        graph_dict = cast(ModelDict, dependency_graph.model_dump(mode="json"))
        analyzed = await self.analyzer.analyze_current_structure(
            structure_dict, graph_dict
        )
        return MemoryBankStructureData.model_validate(analyzed)

    async def generate_proposed_structure(
        self,
        current_structure: MemoryBankStructureData,
        optimize_for: str,
        dependency_graph: DependencyGraphInput,
    ) -> MemoryBankStructureData:
        """Generate proposed structure model for the given optimization goal."""
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        graph_dict = cast(ModelDict, dependency_graph.model_dump(mode="json"))
        proposed = await self.strategies.generate_proposed_structure(
            current_dict, optimize_for, graph_dict
        )
        return MemoryBankStructureData.model_validate(proposed)

    async def generate_actions(
        self,
        current_structure: MemoryBankStructureData,
        proposed_structure: MemoryBankStructureData,
        optimize_for: str,
    ) -> list[ReorganizationActionModel]:
        """Generate reorganization actions for the given structures."""
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        proposed_dict = cast(ModelDict, proposed_structure.model_dump(mode="json"))
        actions = await self.executor.generate_actions(
            current_dict, proposed_dict, optimize_for
        )
        return [
            ReorganizationActionModel(
                action_type=a.action_type,
                source=a.source,
                target=a.target,
                reason=a.reason,
                dependencies_affected=a.dependencies_affected,
            )
            for a in actions
        ]

    def calculate_impact(
        self,
        current_structure: MemoryBankStructureData,
        proposed_structure: MemoryBankStructureData,
        actions: list[ReorganizationActionModel],
    ) -> ReorganizationImpactModel:
        """Calculate impact metrics for a set of actions."""
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        proposed_dict = cast(ModelDict, proposed_structure.model_dump(mode="json"))
        action_dataclasses = [
            ReorganizationAction(
                action_type=a.action_type,
                source=a.source,
                target=a.target,
                reason=a.reason,
                dependencies_affected=a.dependencies_affected,
            )
            for a in actions
        ]
        return self.executor.calculate_impact(
            current_dict, proposed_dict, action_dataclasses
        )

    def identify_risks(
        self,
        actions: list[ReorganizationActionModel],
        current_structure: MemoryBankStructureData,
    ) -> list[str]:
        """Identify risks for the given actions and current structure."""
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        action_dataclasses = [
            ReorganizationAction(
                action_type=a.action_type,
                source=a.source,
                target=a.target,
                reason=a.reason,
                dependencies_affected=a.dependencies_affected,
            )
            for a in actions
        ]
        return self.executor.identify_risks(action_dataclasses, current_dict)

    def identify_benefits(
        self,
        proposed_structure: MemoryBankStructureData,
        current_structure: MemoryBankStructureData,
    ) -> list[str]:
        """Identify benefits of the proposed structure."""
        proposed_dict = cast(ModelDict, proposed_structure.model_dump(mode="json"))
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        return self.executor.identify_benefits(proposed_dict, current_dict)

    def _should_reorganize(
        self, current_structure: MemoryBankStructureData, optimize_for: str
    ) -> bool:
        """Check if reorganization is needed."""
        needs_reorg, _reasons = self.needs_reorganization(
            current_structure, optimize_for
        )
        return needs_reorg

    async def _build_reorganization_plan(
        self,
        current_structure: MemoryBankStructureData,
        proposed_structure: MemoryBankStructureData,
        optimize_for: str,
        dependency_graph: ModelDict,
    ) -> ReorganizationPlanModel | None:
        """Build the reorganization plan from structures."""
        current_dict = cast(ModelDict, current_structure.model_dump(mode="json"))
        proposed_dict = cast(ModelDict, proposed_structure.model_dump(mode="json"))
        actions = await self.executor.generate_actions(
            current_dict, proposed_dict, optimize_for
        )
        if not actions:
            return None
        impact = self.executor.calculate_impact(current_dict, proposed_dict, actions)
        risks = self.executor.identify_risks(actions, current_dict)
        benefits = self.executor.identify_benefits(proposed_dict, current_dict)
        action_models = self._convert_actions_to_models(actions)
        return ReorganizationPlanModel(
            plan_id=self.generate_plan_id(),
            optimization_goal=optimize_for,
            current_structure=current_structure,
            proposed_structure=proposed_structure,
            actions=action_models,
            estimated_impact=impact,
            risks=risks,
            benefits=benefits,
            preserve_history=True,
        )

    def _convert_actions_to_models(
        self, actions: list[ReorganizationAction]
    ) -> list[ReorganizationActionModel]:
        """Convert actions to action models."""
        return [
            ReorganizationActionModel(
                action_type=a.action_type,
                source=a.source,
                target=a.target,
                reason=a.reason,
                dependencies_affected=a.dependencies_affected,
            )
            for a in actions
        ]
