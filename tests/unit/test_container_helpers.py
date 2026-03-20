"""Unit tests for container_helpers (unpack_all_managers, build_container_kwargs).

Tests that unpacking manager tuples and building container kwargs preserves
order and shape so the container can be instantiated correctly. Uses real
managers from create_all_managers(temp_project_root) to satisfy Pydantic
instance checks.
"""

from __future__ import annotations

from pathlib import Path

from cortex.core.container import ManagerContainer
from cortex.core.container_helpers import (
    build_container_kwargs,
    unpack_all_managers,
)
from cortex.core.container_models import ContainerKwargs, UnpackedManagers
from cortex.managers.container_factory import create_all_managers


class TestUnpackAllManagers:
    """Tests for unpack_all_managers with real manager tuples."""

    def test_returns_unpacked_managers_model(self, temp_project_root: Path) -> None:
        all_managers = create_all_managers(temp_project_root)
        unpacked = unpack_all_managers(*all_managers)
        assert isinstance(unpacked, UnpackedManagers)

    def test_unpacked_maps_foundation_correctly(self, temp_project_root: Path) -> None:
        all_managers = create_all_managers(temp_project_root)
        foundation, linking, optimization, analysis, refactoring, execution = (
            all_managers
        )
        unpacked = unpack_all_managers(
            foundation, linking, optimization, analysis, refactoring, execution
        )
        assert unpacked.file_system is foundation[0]
        assert unpacked.metadata_index is foundation[1]
        assert unpacked.token_counter is foundation[2]
        assert unpacked.dependency_graph is foundation[3]
        assert unpacked.version_manager is foundation[4]
        assert unpacked.migration_manager is foundation[5]
        assert unpacked.file_watcher is foundation[6]

    def test_unpacked_maps_optimization_before_analysis(
        self, temp_project_root: Path
    ) -> None:
        """Unpacked order should be optimization then analysis (phase 4 before 5.1)."""
        all_managers = create_all_managers(temp_project_root)
        foundation, linking, optimization, analysis, refactoring, execution = (
            all_managers
        )
        unpacked = unpack_all_managers(
            foundation, linking, optimization, analysis, refactoring, execution
        )
        assert unpacked.rules_manager is optimization[5]
        assert unpacked.pattern_analyzer is analysis[0]
        assert unpacked.structure_analyzer is analysis[1]
        assert unpacked.insight_engine is analysis[2]


class TestBuildContainerKwargs:
    """Tests for build_container_kwargs."""

    def test_build_container_kwargs_returns_container_kwargs(
        self, temp_project_root: Path
    ) -> None:
        all_managers = create_all_managers(temp_project_root)
        unpacked = unpack_all_managers(*all_managers)
        kwargs = build_container_kwargs(unpacked)
        assert isinstance(kwargs, ContainerKwargs)

    def test_build_container_kwargs_roundtrip_validates(
        self, temp_project_root: Path
    ) -> None:
        all_managers = create_all_managers(temp_project_root)
        unpacked = unpack_all_managers(*all_managers)
        kwargs = build_container_kwargs(unpacked)
        combined = kwargs.model_dump()
        validated = ContainerKwargs.model_validate(combined)
        assert validated.model_dump() == combined

    def test_container_instantiable_from_unpacked_managers(
        self, temp_project_root: Path
    ) -> None:
        """ManagerContainer can be built from unpack_all_managers + build_container_kwargs."""
        all_managers = create_all_managers(temp_project_root)
        unpacked = unpack_all_managers(*all_managers)
        kwargs = build_container_kwargs(unpacked)
        container = ManagerContainer.model_validate(kwargs, from_attributes=True)
        assert container.file_system is unpacked.file_system
        assert container.rules_manager is unpacked.rules_manager
