"""Preview and validation helpers for reorganization plans.

Extracted from reorganization_planner for file size compliance.
"""

from cortex.core.models import (
    ModelDict,
    ReorganizationActionPreview,
    StructureComparison,
    StructureMetrics,
)
from cortex.refactoring.models import (
    DependencyGraphInput,
    MemoryBankStructureData,
    ReorganizationPlanModel,
)


def build_action_previews(
    plan: ReorganizationPlanModel,
) -> list[ReorganizationActionPreview]:
    """Build action previews from plan."""
    actions: list[ReorganizationActionPreview] = []
    for action in plan.actions:
        actions.append(
            ReorganizationActionPreview(
                type=action.action_type,
                description=(
                    f"{action.action_type}: {action.source} -> {action.target}"
                ),
                reason=action.reason,
            )
        )
    return actions


def build_structure_comparison(
    plan: ReorganizationPlanModel,
) -> StructureComparison:
    """Build structure comparison from plan."""
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


def build_preview_details(
    plan: ReorganizationPlanModel, show_details: bool
) -> tuple[list[ReorganizationActionPreview], StructureComparison | None]:
    """Build preview details from reorganization plan."""
    actions = build_action_previews(plan) if show_details else []
    structure_comparison = build_structure_comparison(plan) if show_details else None
    return actions, structure_comparison


def validate_reorganization_inputs(
    structure_data: MemoryBankStructureData | ModelDict | None,
    dependency_graph: DependencyGraphInput | ModelDict | None,
) -> bool:
    """Validate inputs for reorganization plan creation."""
    return structure_data is not None and dependency_graph is not None


def normalize_structure_data_input(structure_data: ModelDict) -> ModelDict:
    """Normalize legacy structure_data shapes for model validation."""
    organization = structure_data.get("organization")
    if isinstance(organization, dict):
        org_type = organization.get("type")
        if isinstance(org_type, str):
            normalized = dict(structure_data)
            normalized["organization"] = org_type
            return normalized
    return structure_data
