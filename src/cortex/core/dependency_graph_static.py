"""Static dependency data and graph construction helpers for dependency_graph."""

from collections.abc import Callable
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MemoryBankFile
from cortex.core.models import ModelDict
from cortex.linking.parser import LinkParser

from .async_file_utils import open_async_text_file
from .models import DependencyEdge, DependencyNode

# Re-export for use by dependency_graph and callers
__all__ = [
    "FileDependencyInfo",
    "STATIC_DEPENDENCIES",
    "build_dynamic_deps_from_links",
    "add_link_to_maps",
    "build_dependency_nodes",
    "create_dependency_edge",
]


class FileDependencyInfo(BaseModel):
    """Type definition for file dependency information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    depends_on: list[str] = Field(
        default_factory=list, description="List of files this file depends on"
    )
    priority: int = Field(ge=0, description="Loading priority (0 = highest)")
    category: str = Field(description="File category")


# Static dependency hierarchy based on template structure
STATIC_DEPENDENCIES: dict[str, FileDependencyInfo] = {
    MemoryBankFile.PROJECT_BRIEF: FileDependencyInfo(
        depends_on=[],
        priority=0,  # Foundation — always load first
        category="foundation",
    ),
    MemoryBankFile.PRODUCT_CONTEXT: FileDependencyInfo(
        depends_on=[MemoryBankFile.PROJECT_BRIEF],
        priority=2,  # Context layer
        category="context",
    ),
    MemoryBankFile.SYSTEM_PATTERNS: FileDependencyInfo(
        depends_on=[MemoryBankFile.PROJECT_BRIEF],
        priority=2,
        category="context",
    ),
    MemoryBankFile.TECH_CONTEXT: FileDependencyInfo(
        depends_on=[MemoryBankFile.PROJECT_BRIEF],
        priority=2,
        category="context",
    ),
    MemoryBankFile.ACTIVE_CONTEXT: FileDependencyInfo(
        depends_on=[
            MemoryBankFile.PRODUCT_CONTEXT,
            MemoryBankFile.SYSTEM_PATTERNS,
            MemoryBankFile.TECH_CONTEXT,
        ],
        priority=3,  # Active work
        category="active",
    ),
    MemoryBankFile.PROGRESS: FileDependencyInfo(
        depends_on=[MemoryBankFile.ACTIVE_CONTEXT],
        priority=4,  # Status
        category="status",
    ),
}


def build_dependency_nodes(
    static_deps: dict[str, FileDependencyInfo],
) -> list[DependencyNode]:
    """Build node list from static dependencies."""
    return [
        DependencyNode(
            file=file_name,
            priority=info.priority,
            category=info.category,
        )
        for file_name, info in static_deps.items()
    ]


def create_dependency_edge(
    file_name: str,
    dep: str,
    dynamic_deps: dict[str, list[str]],
    get_file_priority: Callable[[str], int],
) -> DependencyEdge:
    """Create a single dependency edge."""
    is_dynamic = dep in dynamic_deps.get(file_name, [])
    edge_type = "links" if is_dynamic else "informs"
    from_priority = get_file_priority(file_name)
    to_priority = get_file_priority(dep)
    strength = "strong" if abs(from_priority - to_priority) == 1 else "medium"
    return DependencyEdge(
        **{
            "from": dep,
            "to": file_name,
            "type": edge_type,
            "strength": strength,
        }
    )


def add_link_to_maps(
    dynamic_deps: dict[str, list[str]],
    link_types: dict[str, dict[str, str]],
    source_file: str,
    target_file: str,
    link_type: str = "reference",
) -> None:
    """Add a link to dynamic_deps and link_types (mutates in place)."""
    if source_file not in dynamic_deps:
        dynamic_deps[source_file] = []
    if target_file not in dynamic_deps[source_file]:
        dynamic_deps[source_file].append(target_file)
    if source_file not in link_types:
        link_types[source_file] = {}
    link_types[source_file][target_file] = link_type


async def build_dynamic_deps_from_links(
    memory_bank_dir: Path,
    link_parser: LinkParser,
) -> tuple[dict[str, list[str]], dict[str, dict[str, str]]]:
    """
    Build dynamic dependencies and link types by scanning markdown files.

    Returns:
        Tuple of (dynamic_deps, link_types).
    """
    dynamic_deps: dict[str, list[str]] = {}
    link_types: dict[str, dict[str, str]] = {}
    md_files = list(memory_bank_dir.glob("*.md"))
    for file_path in md_files:
        await _process_file_links(file_path, link_parser, dynamic_deps, link_types)
    return (dynamic_deps, link_types)


async def _process_file_links(
    file_path: Path,
    link_parser: LinkParser,
    dynamic_deps: dict[str, list[str]],
    link_types: dict[str, dict[str, str]],
) -> None:
    """Process links in a single file."""
    try:
        async with open_async_text_file(file_path, "r", "utf-8") as f:
            content = await f.read()
        parsed = await link_parser.parse_file(content)
        _process_markdown_links(parsed, file_path.name, dynamic_deps, link_types)
        _process_transclusions(parsed, file_path.name, dynamic_deps, link_types)
    except Exception as e:
        from cortex.core.logging_config import logger

        logger.warning("Failed to parse links from %s: %s", file_path, e)


def _process_markdown_links(
    parsed: ModelDict,
    file_name: str,
    dynamic_deps: dict[str, list[str]],
    link_types: dict[str, dict[str, str]],
) -> None:
    """Process markdown links from parsed content."""
    markdown_links_raw = parsed.get("markdown_links", [])
    if isinstance(markdown_links_raw, list):
        for link_obj in markdown_links_raw:
            if not isinstance(link_obj, dict):
                continue
            link = cast(ModelDict, link_obj)
            if not isinstance(link.get("target"), str):
                continue
            add_link_to_maps(
                dynamic_deps,
                link_types,
                file_name,
                cast(str, link["target"]),
                "reference",
            )


def _process_transclusions(
    parsed: ModelDict,
    file_name: str,
    dynamic_deps: dict[str, list[str]],
    link_types: dict[str, dict[str, str]],
) -> None:
    """Process transclusions from parsed content."""
    transclusions_raw = parsed.get("transclusions", [])
    if isinstance(transclusions_raw, list):
        for trans_obj in transclusions_raw:
            if not isinstance(trans_obj, dict):
                continue
            trans = cast(ModelDict, trans_obj)
            if not isinstance(trans.get("target"), str):
                continue
            add_link_to_maps(
                dynamic_deps,
                link_types,
                file_name,
                cast(str, trans["target"]),
                "transclusion",
            )
