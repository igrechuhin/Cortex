"""Factory methods for creating Phase 2 linking manager instances."""

from cortex.core.file_system import FileSystemManager
from cortex.linking.parser import LinkParser
from cortex.linking.transclusion_engine import TransclusionEngine
from cortex.linking.validator import LinkValidator

from .container_config import FoundationManagers, LinkingManagers


def create_linking_managers(
    file_system: FileSystemManager,
) -> tuple[LinkParser, TransclusionEngine, LinkValidator]:
    """Create Phase 2 linking managers."""
    link_parser = LinkParser()
    transclusion_engine = TransclusionEngine(
        file_system=file_system,
        link_parser=link_parser,
        max_depth=5,
        cache_enabled=True,
    )
    link_validator = LinkValidator(file_system=file_system, link_parser=link_parser)

    return link_parser, transclusion_engine, link_validator


def create_linking_managers_from_foundation(
    foundation_managers: FoundationManagers,
) -> LinkingManagers:
    """Create linking managers from foundation managers."""
    file_system = foundation_managers[0]
    return create_linking_managers(file_system)
