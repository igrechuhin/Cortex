"""Unit tests for container_models.py.

Tests Pydantic container models used by the dependency injection container.
Uses model_construct with mocks to avoid instantiating real managers.
"""

from unittest.mock import MagicMock

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


def _mock() -> MagicMock:
    """Return a MagicMock instance for manager placeholders."""
    return MagicMock()


class TestUnpackedManagers:
    """Tests for UnpackedManagers model."""

    def test_model_construct_with_mocks(self) -> None:
        """UnpackedManagers can be constructed with mock managers."""
        unpacked = UnpackedManagers.model_construct(
            file_system=_mock(),
            metadata_index=_mock(),
            token_counter=_mock(),
            dependency_graph=_mock(),
            version_manager=_mock(),
            migration_manager=_mock(),
            file_watcher=_mock(),
            link_parser=_mock(),
            transclusion_engine=_mock(),
            link_validator=_mock(),
            optimization_config=_mock(),
            relevance_scorer=_mock(),
            context_optimizer=_mock(),
            progressive_loader=_mock(),
            summarization_engine=_mock(),
            rules_manager=_mock(),
            pattern_analyzer=_mock(),
            structure_analyzer=_mock(),
            insight_engine=_mock(),
            refactoring_engine=_mock(),
            consolidation_detector=_mock(),
            split_recommender=_mock(),
            reorganization_planner=_mock(),
            refactoring_executor=_mock(),
            approval_manager=_mock(),
            rollback_manager=_mock(),
            learning_engine=_mock(),
            adaptation_config=_mock(),
        )
        assert unpacked.file_system is not None
        assert unpacked.approval_manager is not None
        assert unpacked.adaptation_config is not None

    def test_model_dump_roundtrip(self) -> None:
        """UnpackedManagers.model_dump() returns dict of attributes."""
        m = _mock()
        unpacked = UnpackedManagers.model_construct(
            file_system=m,
            metadata_index=m,
            token_counter=m,
            dependency_graph=m,
            version_manager=m,
            migration_manager=m,
            file_watcher=m,
            link_parser=m,
            transclusion_engine=m,
            link_validator=m,
            optimization_config=m,
            relevance_scorer=m,
            context_optimizer=m,
            progressive_loader=m,
            summarization_engine=m,
            rules_manager=m,
            pattern_analyzer=m,
            structure_analyzer=m,
            insight_engine=m,
            refactoring_engine=m,
            consolidation_detector=m,
            split_recommender=m,
            reorganization_planner=m,
            refactoring_executor=m,
            approval_manager=m,
            rollback_manager=m,
            learning_engine=m,
            adaptation_config=m,
        )
        dumped = unpacked.model_dump()
        assert "file_system" in dumped
        assert "approval_manager" in dumped


class TestFoundationKwargs:
    """Tests for FoundationKwargs model."""

    def test_model_construct(self) -> None:
        """FoundationKwargs can be constructed with mocks."""
        kwargs = FoundationKwargs.model_construct(
            file_system=_mock(),
            metadata_index=_mock(),
            token_counter=_mock(),
            dependency_graph=_mock(),
            version_manager=_mock(),
            migration_manager=_mock(),
            file_watcher=_mock(),
        )
        assert kwargs.file_system is not None
        assert kwargs.file_watcher is not None


class TestLinkingKwargs:
    """Tests for LinkingKwargs model."""

    def test_model_construct(self) -> None:
        """LinkingKwargs can be constructed with mocks."""
        kwargs = LinkingKwargs.model_construct(
            link_parser=_mock(),
            transclusion_engine=_mock(),
            link_validator=_mock(),
        )
        assert kwargs.link_parser is not None
        assert kwargs.transclusion_engine is not None


class TestOptimizationKwargs:
    """Tests for OptimizationKwargs model."""

    def test_model_construct(self) -> None:
        """OptimizationKwargs can be constructed with mocks."""
        kwargs = OptimizationKwargs.model_construct(
            optimization_config=_mock(),
            relevance_scorer=_mock(),
            context_optimizer=_mock(),
            progressive_loader=_mock(),
            summarization_engine=_mock(),
            rules_manager=_mock(),
        )
        assert kwargs.optimization_config is not None
        assert kwargs.rules_manager is not None


class TestAnalysisKwargs:
    """Tests for AnalysisKwargs model."""

    def test_model_construct(self) -> None:
        """AnalysisKwargs can be constructed with mocks."""
        kwargs = AnalysisKwargs.model_construct(
            pattern_analyzer=_mock(),
            structure_analyzer=_mock(),
            insight_engine=_mock(),
        )
        assert kwargs.pattern_analyzer is not None
        assert kwargs.insight_engine is not None


class TestRefactoringKwargs:
    """Tests for RefactoringKwargs model."""

    def test_model_construct(self) -> None:
        """RefactoringKwargs can be constructed with mocks."""
        kwargs = RefactoringKwargs.model_construct(
            refactoring_engine=_mock(),
            consolidation_detector=_mock(),
            split_recommender=_mock(),
            reorganization_planner=_mock(),
        )
        assert kwargs.refactoring_engine is not None
        assert kwargs.reorganization_planner is not None


class TestExecutionKwargs:
    """Tests for ExecutionKwargs model."""

    def test_model_construct(self) -> None:
        """ExecutionKwargs can be constructed with mocks."""
        kwargs = ExecutionKwargs.model_construct(
            refactoring_executor=_mock(),
            approval_manager=_mock(),
            rollback_manager=_mock(),
            learning_engine=_mock(),
            adaptation_config=_mock(),
        )
        assert kwargs.refactoring_executor is not None
        assert kwargs.adaptation_config is not None


class TestContainerKwargs:
    """Tests for ContainerKwargs model."""

    def test_model_validate_allow_extra(self) -> None:
        """ContainerKwargs allows extra keys (extra='allow')."""
        combined = {"custom_key": "allowed"}
        validated = ContainerKwargs.model_validate(combined)
        assert validated.model_dump().get("custom_key") == "allowed"

    def test_model_construct_empty(self) -> None:
        """ContainerKwargs can be constructed with no fields."""
        kwargs = ContainerKwargs.model_construct()
        assert kwargs.model_dump() == {}
