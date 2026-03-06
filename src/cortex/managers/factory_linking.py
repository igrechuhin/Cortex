#!/usr/bin/env python3
"""Linking-phase manager factory helpers (Phase 2)."""

from cortex.linking.parser import LinkParser
from cortex.linking.transclusion_engine import TransclusionEngine
from cortex.linking.validator import LinkValidator
from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.types import CoreManagersDict
from cortex.optimization.config import OptimizationConfig


async def _create_link_parser() -> LinkParser:
    """Create LinkParser instance."""
    return LinkParser()


async def _create_transclusion_engine(
    core_managers: CoreManagersDict,
    managers: ManagersBuilder,
) -> TransclusionEngine:
    """Create TransclusionEngine instance."""
    from cortex.managers.utils import get_manager

    fs_manager = core_managers.fs
    link_parser = LinkParser()
    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    return TransclusionEngine(
        file_system=fs_manager,
        link_parser=link_parser,
        max_depth=5,
        cache_enabled=optimization_config.is_cache_enabled(),
    )


async def _create_link_validator(core_managers: CoreManagersDict) -> LinkValidator:
    """Create LinkValidator instance."""
    fs_manager = core_managers.fs
    link_parser = LinkParser()
    return LinkValidator(file_system=fs_manager, link_parser=link_parser)


def add_linking_managers(
    managers: ManagersBuilder, core_managers: CoreManagersDict
) -> None:
    """Add Phase 2 linking managers as lazy.

    Args:
        managers: Managers dictionary to update
        core_managers: Core managers dictionary
    """
    managers["link_parser"] = LazyManager(
        lambda: _create_link_parser(), name="link_parser"
    )
    managers["transclusion"] = LazyManager(
        lambda: _create_transclusion_engine(core_managers, managers),
        name="transclusion",
    )
    managers["link_validator"] = LazyManager(
        lambda: _create_link_validator(core_managers), name="link_validator"
    )
