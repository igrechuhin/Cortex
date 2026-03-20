#!/usr/bin/env python3
"""Helper functions for manager unpacking and kwargs building.

Extracted from `cortex.core.container` to comply with the 400-line file limit.
These functions handle the mechanical unpacking of manager tuples into typed
kwargs models and the reverse building of kwargs from UnpackedManagers.
"""

from __future__ import annotations

from cortex.core.container_models import (
    AnalysisKwargs,
    ContainerKwargs,
    ExecutionKwargs,
    FoundationKwargs,
    LinkingKwargs,
    OptimizationKwargs,
    RefactoringKwargs,
    UnpackedManagers,
)
from cortex.managers.container_factory import (
    AnalysisManagers,
    ExecutionManagers,
    FoundationManagers,
    LinkingManagers,
    OptimizationManagers,
    RefactoringManagers,
)

# ---------------------------------------------------------------------------
# Unpacking: tuple -> typed kwargs model
# ---------------------------------------------------------------------------


def unpack_foundation_managers(
    foundation_managers: FoundationManagers,
) -> FoundationKwargs:
    """Unpack Phase 1 foundation managers."""
    (
        file_system,
        metadata_index,
        token_counter,
        dependency_graph,
        version_manager,
        migration_manager,
        file_watcher,
    ) = foundation_managers
    return FoundationKwargs(
        file_system=file_system,
        metadata_index=metadata_index,
        token_counter=token_counter,
        dependency_graph=dependency_graph,
        version_manager=version_manager,
        migration_manager=migration_manager,
        file_watcher=file_watcher,
    )


def unpack_linking_managers(
    linking_managers: LinkingManagers,
) -> LinkingKwargs:
    """Unpack Phase 2 linking managers."""
    link_parser, transclusion_engine, link_validator = linking_managers
    return LinkingKwargs(
        link_parser=link_parser,
        transclusion_engine=transclusion_engine,
        link_validator=link_validator,
    )


def unpack_optimization_managers(
    optimization_managers: OptimizationManagers,
) -> OptimizationKwargs:
    """Unpack Phase 4 optimization managers."""
    (
        optimization_config,
        relevance_scorer,
        context_optimizer,
        progressive_loader,
        summarization_engine,
        rules_manager,
    ) = optimization_managers
    return OptimizationKwargs(
        optimization_config=optimization_config,
        relevance_scorer=relevance_scorer,
        context_optimizer=context_optimizer,
        progressive_loader=progressive_loader,
        summarization_engine=summarization_engine,
        rules_manager=rules_manager,
    )


def unpack_analysis_managers(
    analysis_managers: AnalysisManagers,
) -> AnalysisKwargs:
    """Unpack Phase 5.1 analysis managers."""
    pattern_analyzer, structure_analyzer, insight_engine = analysis_managers
    return AnalysisKwargs(
        pattern_analyzer=pattern_analyzer,
        structure_analyzer=structure_analyzer,
        insight_engine=insight_engine,
    )


def unpack_refactoring_managers(
    refactoring_managers: RefactoringManagers,
) -> RefactoringKwargs:
    """Unpack Phase 5.2 refactoring managers."""
    (
        refactoring_engine,
        consolidation_detector,
        split_recommender,
        reorganization_planner,
    ) = refactoring_managers
    return RefactoringKwargs(
        refactoring_engine=refactoring_engine,
        consolidation_detector=consolidation_detector,
        split_recommender=split_recommender,
        reorganization_planner=reorganization_planner,
    )


def unpack_execution_managers(
    execution_managers: ExecutionManagers,
) -> ExecutionKwargs:
    """Unpack Phase 5.3-5.4 execution managers."""
    (
        refactoring_executor,
        approval_manager,
        rollback_manager,
        learning_engine,
        adaptation_config,
    ) = execution_managers
    return ExecutionKwargs(
        refactoring_executor=refactoring_executor,
        approval_manager=approval_manager,
        rollback_manager=rollback_manager,
        learning_engine=learning_engine,
        adaptation_config=adaptation_config,
    )


def unpack_all_managers(
    foundation_managers: FoundationManagers,
    linking_managers: LinkingManagers,
    optimization_managers: OptimizationManagers,
    analysis_managers: AnalysisManagers,
    refactoring_managers: RefactoringManagers,
    execution_managers: ExecutionManagers,
) -> UnpackedManagers:
    """Unpack all manager tuples into a single model.

    Args:
        foundation_managers: Phase 1 managers
        linking_managers: Phase 2 managers
        optimization_managers: Phase 4 managers
        analysis_managers: Phase 5.1 managers
        refactoring_managers: Phase 5.2 managers
        execution_managers: Phase 5.3-5.4 managers

    Returns:
        UnpackedManagers model with all managers
    """
    foundation_kwargs = unpack_foundation_managers(foundation_managers)
    linking_kwargs = unpack_linking_managers(linking_managers)
    optimization_kwargs = unpack_optimization_managers(optimization_managers)
    analysis_kwargs = unpack_analysis_managers(analysis_managers)
    refactoring_kwargs = unpack_refactoring_managers(refactoring_managers)
    execution_kwargs = unpack_execution_managers(execution_managers)

    return UnpackedManagers.model_construct(
        **foundation_kwargs.model_dump(),
        **linking_kwargs.model_dump(),
        **optimization_kwargs.model_dump(),
        **analysis_kwargs.model_dump(),
        **refactoring_kwargs.model_dump(),
        **execution_kwargs.model_dump(),
    )


# ---------------------------------------------------------------------------
# Building: UnpackedManagers -> typed kwargs model
# ---------------------------------------------------------------------------


def build_foundation_kwargs(unpacked: UnpackedManagers) -> FoundationKwargs:
    """Build Phase 1 foundation keyword arguments."""
    return FoundationKwargs(
        file_system=unpacked.file_system,
        metadata_index=unpacked.metadata_index,
        token_counter=unpacked.token_counter,
        dependency_graph=unpacked.dependency_graph,
        version_manager=unpacked.version_manager,
        migration_manager=unpacked.migration_manager,
        file_watcher=unpacked.file_watcher,
    )


def build_linking_kwargs(unpacked: UnpackedManagers) -> LinkingKwargs:
    """Build Phase 2 linking keyword arguments."""
    return LinkingKwargs(
        link_parser=unpacked.link_parser,
        transclusion_engine=unpacked.transclusion_engine,
        link_validator=unpacked.link_validator,
    )


def build_optimization_kwargs(
    unpacked: UnpackedManagers,
) -> OptimizationKwargs:
    """Build Phase 4 optimization keyword arguments."""
    return OptimizationKwargs(
        optimization_config=unpacked.optimization_config,
        relevance_scorer=unpacked.relevance_scorer,
        context_optimizer=unpacked.context_optimizer,
        progressive_loader=unpacked.progressive_loader,
        summarization_engine=unpacked.summarization_engine,
        rules_manager=unpacked.rules_manager,
    )


def build_analysis_kwargs(unpacked: UnpackedManagers) -> AnalysisKwargs:
    """Build Phase 5.1 analysis keyword arguments."""
    return AnalysisKwargs(
        pattern_analyzer=unpacked.pattern_analyzer,
        structure_analyzer=unpacked.structure_analyzer,
        insight_engine=unpacked.insight_engine,
    )


def build_refactoring_kwargs(
    unpacked: UnpackedManagers,
) -> RefactoringKwargs:
    """Build Phase 5.2 refactoring keyword arguments."""
    return RefactoringKwargs(
        refactoring_engine=unpacked.refactoring_engine,
        consolidation_detector=unpacked.consolidation_detector,
        split_recommender=unpacked.split_recommender,
        reorganization_planner=unpacked.reorganization_planner,
    )


def build_execution_kwargs(unpacked: UnpackedManagers) -> ExecutionKwargs:
    """Build Phase 5.3-5.4 execution keyword arguments."""
    return ExecutionKwargs(
        refactoring_executor=unpacked.refactoring_executor,
        approval_manager=unpacked.approval_manager,
        rollback_manager=unpacked.rollback_manager,
        learning_engine=unpacked.learning_engine,
        adaptation_config=unpacked.adaptation_config,
    )


def build_container_kwargs(unpacked: UnpackedManagers) -> ContainerKwargs:
    """Build combined keyword arguments for container instantiation.

    Args:
        unpacked: UnpackedManagers model with all managers

    Returns:
        ContainerKwargs with all manager references
    """
    combined_data = {
        **build_foundation_kwargs(unpacked).model_dump(),
        **build_linking_kwargs(unpacked).model_dump(),
        **build_optimization_kwargs(unpacked).model_dump(),
        **build_analysis_kwargs(unpacked).model_dump(),
        **build_refactoring_kwargs(unpacked).model_dump(),
        **build_execution_kwargs(unpacked).model_dump(),
    }

    return ContainerKwargs.model_validate(combined_data)
