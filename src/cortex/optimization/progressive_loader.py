"""
Progressive context loading for incremental content delivery.

This module provides functionality to load context progressively based on
various strategies (priority, dependencies, relevance, budget).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import (
    FileContentMetadata,
    FileMetadataForScoring,
)
from cortex.optimization.optimization_strategies import OptimizationResult

from .context_optimizer import ContextOptimizer


class LoadedFileContent(BaseModel):
    """Type definition for loaded file content."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    content: str = Field(description="File content")
    tokens: int = Field(ge=0, description="Token count")
    cumulative_tokens: int = Field(ge=0, description="Cumulative token count")
    metadata: FileContentMetadata = Field(
        default_factory=FileContentMetadata, description="File metadata"
    )


@dataclass
class LoadedContent:
    """Represents a loaded piece of content."""

    file_name: str
    content: str
    tokens: int
    cumulative_tokens: int
    priority: int
    relevance_score: float
    more_available: bool
    metadata: FileContentMetadata


def _build_file_content_metadata(
    metadata: ModelDict | None,
    *,
    tokens: int | None,
    priority: int | None,
) -> FileContentMetadata:
    """Build FileContentMetadata from dict-shaped metadata index entry."""
    meta: dict[str, JsonValue] = metadata if isinstance(metadata, dict) else {}

    sections_raw = meta.get("sections", [])
    section_headings: list[str] = []
    if isinstance(sections_raw, list):
        for item in cast(list[JsonValue], sections_raw):
            if isinstance(item, str):
                section_headings.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_dict = cast(dict[str, JsonValue], item)
            heading = item_dict.get("heading")
            if isinstance(heading, str) and heading:
                section_headings.append(heading)

    sections_json = cast(list[JsonValue], section_headings)
    out: dict[str, JsonValue] = {
        "content_hash": meta.get("content_hash"),
        "last_modified": meta.get("last_modified"),
        "sections": sections_json,
        "tokens": tokens,
        "priority": priority,
    }
    return FileContentMetadata.model_validate(out)


class ProgressiveLoader:
    """Load context progressively based on strategy."""

    def __init__(
        self,
        file_system: FileSystemManager,
        context_optimizer: ContextOptimizer,
        metadata_index: MetadataIndex,
    ):
        """
        Initialize progressive loader.

        Args:
            file_system: File system manager for reading files
            context_optimizer: Context optimizer for smart selection
            metadata_index: Metadata index for file information
        """
        self.file_system: FileSystemManager = file_system
        self.context_optimizer: ContextOptimizer = context_optimizer
        self.metadata_index: MetadataIndex = metadata_index

    async def load_by_priority(
        self,
        task_description: str,  # noqa: ARG002
        token_budget: int,
        priority_order: list[str] | None = None,
    ) -> list[LoadedContent]:
        """
        Load files in priority order.

        Args:
            task_description: Task description for relevance scoring
            token_budget: Maximum tokens to load
            priority_order: Optional explicit priority order

        Returns:
            List of LoadedContent objects
        """
        if priority_order is None:
            priority_order = self.get_default_priority_order()

        loaded_content: list[LoadedContent] = []
        cumulative_tokens = 0

        for priority, file_name in enumerate(priority_order):
            if cumulative_tokens >= token_budget:
                break

            result = await _process_priority_file(
                self,
                file_name,
                priority,
                priority_order,
                cumulative_tokens,
                token_budget,
            )
            if result is not None:
                loaded_content.append(result)
                cumulative_tokens = result.cumulative_tokens

        return loaded_content

    async def _process_file_for_dependencies(
        self,
        file_name: str,
        depth: int,
        cumulative_tokens: int,
        token_budget: int,
        to_visit: list[tuple[str, int]],
    ) -> tuple[LoadedContent | None, int]:
        """Process a single file and return LoadedContent if within budget."""
        try:
            content, _ = await self.file_system.read_file(Path(file_name))
            tokens = self.context_optimizer.token_counter.count_tokens(content)

            if cumulative_tokens + tokens <= token_budget:
                return (
                    await self._build_loaded_content(
                        file_name, content, tokens, depth, cumulative_tokens, to_visit
                    ),
                    cumulative_tokens + tokens,
                )
            return None, cumulative_tokens

        except FileNotFoundError:
            return None, cumulative_tokens

    async def _build_loaded_content(
        self,
        file_name: str,
        content: str,
        tokens: int,
        depth: int,
        cumulative_tokens: int,
        to_visit: list[tuple[str, int]],
    ) -> LoadedContent:
        """Build LoadedContent object from file data."""
        new_cumulative = cumulative_tokens + tokens
        metadata_obj = await self.metadata_index.get_file_metadata(file_name)
        metadata = _build_file_content_metadata(
            metadata_obj,
            tokens=tokens,
            priority=depth,
        )
        return LoadedContent(
            file_name=file_name,
            content=content,
            tokens=tokens,
            cumulative_tokens=new_cumulative,
            priority=depth,
            relevance_score=0.0,
            more_available=bool(to_visit),
            metadata=metadata,
        )

    def _add_dependencies_to_queue(
        self,
        file_name: str,
        depth: int,
        visited: set[str],
        to_visit: list[tuple[str, int]],
    ) -> None:
        """Add file dependencies to the visit queue."""
        deps = self.context_optimizer.dependency_graph.get_dependencies(file_name)
        for dep in deps:
            if dep not in visited:
                to_visit.append((dep, depth + 1))

    async def load_by_dependencies(
        self,
        entry_files: list[str],
        token_budget: int,
    ) -> list[LoadedContent]:
        """
        Load dependency chain starting from entry files.

        Args:
            entry_files: Entry point files
            token_budget: Maximum tokens to load

        Returns:
            List of LoadedContent objects
        """
        loaded_content: list[LoadedContent] = []
        cumulative_tokens = 0
        visited: set[str] = set()
        to_visit: list[tuple[str, int]] = [(file, 0) for file in entry_files]

        while to_visit and cumulative_tokens < token_budget:
            file_name, depth = to_visit.pop(0)

            if file_name in visited:
                continue

            visited.add(file_name)

            loaded, cumulative_tokens = await self._process_file_for_dependencies(
                file_name, depth, cumulative_tokens, token_budget, to_visit
            )

            if loaded:
                loaded_content.append(loaded)
                self._add_dependencies_to_queue(file_name, depth, visited, to_visit)

        return loaded_content

    async def load_by_relevance(
        self,
        task_description: str,
        token_budget: int,
        quality_scores: dict[str, float] | None = None,
    ) -> list[LoadedContent]:
        """
        Load most relevant files first.

        Args:
            task_description: Task description
            token_budget: Maximum tokens to load
            quality_scores: Optional quality scores

        Returns:
            List of LoadedContent objects
        """
        # Get all files and read them
        files_content, files_metadata = await _read_all_files_for_loading(
            self.metadata_index, self.file_system
        )

        # Optimize and build loaded content
        return await _optimize_and_build_loaded_content(
            self.context_optimizer,
            task_description,
            files_content,
            files_metadata,
            token_budget,
            quality_scores,
        )

    async def load_with_budget(
        self,
        files: list[str],
        token_budget: int,
        stop_at_budget: bool = True,
    ) -> list[LoadedContent]:
        """
        Load files until budget is reached.

        Args:
            files: List of files to load
            token_budget: Token budget
            stop_at_budget: Whether to stop at budget or load all

        Returns:
            List of LoadedContent objects
        """
        loaded_content: list[LoadedContent] = []
        cumulative_tokens = 0

        for priority, file_name in enumerate(files):
            if stop_at_budget and cumulative_tokens >= token_budget:
                break

            content_item = await self._load_file_with_budget_check(
                file_name, cumulative_tokens, token_budget, stop_at_budget
            )
            if not content_item:
                continue

            cumulative_tokens = content_item.cumulative_tokens
            loaded_content.append(
                LoadedContent(
                    file_name=file_name,
                    content=content_item.content,
                    tokens=content_item.tokens,
                    cumulative_tokens=cumulative_tokens,
                    priority=priority,
                    relevance_score=0.0,
                    more_available=priority < len(files) - 1,
                    metadata=content_item.metadata,
                )
            )

        return loaded_content

    async def _load_file_with_budget_check(
        self,
        file_name: str,
        cumulative_tokens: int,
        token_budget: int,
        stop_at_budget: bool,
    ) -> LoadedFileContent | None:
        """Load a single file and check budget constraints."""
        try:
            file_path = Path(file_name)
            if not file_path.is_absolute():
                file_path = self.file_system.memory_bank_dir / file_name
            content, _ = await self.file_system.read_file(file_path)

            tokens = self.context_optimizer.token_counter.count_tokens(content)

            if stop_at_budget and cumulative_tokens + tokens > token_budget:
                return None

            metadata = _build_file_content_metadata(
                await self.metadata_index.get_file_metadata(file_name),
                tokens=tokens,
                priority=None,
            )

            return LoadedFileContent(
                content=content,
                tokens=tokens,
                cumulative_tokens=cumulative_tokens + tokens,
                metadata=metadata,
            )
        except FileNotFoundError:
            return None

    def get_default_priority_order(self) -> list[str]:
        """
        Get default file priority order.

        Returns:
            List of file names in priority order
        """
        return [
            "memorybankinstructions.md",
            "projectBrief.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
            "progress.md",
        ]

    async def stream_by_priority(
        self,
        task_description: str,  # noqa: ARG002
        token_budget: int,
        priority_order: list[str] | None = None,
    ) -> AsyncIterator[LoadedContent]:
        """
        Stream files in priority order (async generator).

        Args:
            task_description: Task description
            token_budget: Maximum tokens
            priority_order: Optional priority order

        Yields:
            LoadedContent objects one at a time
        """
        if priority_order is None:
            priority_order = self.get_default_priority_order()

        cumulative_tokens = 0

        for priority, file_name in enumerate(priority_order):
            if cumulative_tokens >= token_budget:
                break

            content_item = await self._load_file_for_streaming(
                file_name, cumulative_tokens, token_budget
            )
            if not content_item:
                break

            cumulative_tokens = content_item.cumulative_tokens
            yield LoadedContent(
                file_name=file_name,
                content=content_item.content,
                tokens=content_item.tokens,
                cumulative_tokens=cumulative_tokens,
                priority=priority,
                relevance_score=0.0,
                more_available=priority < len(priority_order) - 1
                and cumulative_tokens < token_budget,
                metadata=content_item.metadata,
            )

    async def _load_file_for_streaming(
        self,
        file_name: str,
        cumulative_tokens: int,
        token_budget: int,
    ) -> LoadedFileContent | None:
        """Load a single file for streaming with budget check."""
        try:
            file_path = Path(file_name)
            if not file_path.is_absolute():
                file_path = self.file_system.memory_bank_dir / file_name
            content, _ = await self.file_system.read_file(file_path)

            tokens = self.context_optimizer.token_counter.count_tokens(content)

            if cumulative_tokens + tokens > token_budget:
                return None

            metadata = _build_file_content_metadata(
                await self.metadata_index.get_file_metadata(file_name),
                tokens=tokens,
                priority=None,
            )

            return LoadedFileContent(
                content=content,
                tokens=tokens,
                cumulative_tokens=cumulative_tokens + tokens,
                metadata=metadata,
            )
        except FileNotFoundError:
            return None

    async def stream_by_relevance(
        self,
        task_description: str,
        token_budget: int,
        quality_scores: dict[str, float] | None = None,
    ) -> AsyncIterator[LoadedContent]:
        """
        Stream files by relevance (async generator).

        Args:
            task_description: Task description
            token_budget: Maximum tokens
            quality_scores: Optional quality scores

        Yields:
            LoadedContent objects one at a time
        """
        # First, load and score all files
        loaded = await self.load_by_relevance(
            task_description, token_budget, quality_scores
        )

        # Stream them one by one
        for content in loaded:
            yield content


async def _optimize_and_build_loaded_content(
    context_optimizer: ContextOptimizer,
    task_description: str,
    files_content: dict[str, str],
    files_metadata: dict[str, FileMetadataForScoring],
    token_budget: int,
    quality_scores: dict[str, float] | None,
) -> list[LoadedContent]:
    """Optimize context and build LoadedContent objects.

    Args:
        context_optimizer: ContextOptimizer instance
        task_description: Task description
        files_content: Dictionary mapping file names to content
        files_metadata: Dictionary mapping file names to metadata
        token_budget: Maximum tokens to load
        quality_scores: Optional quality scores

    Returns:
        List of LoadedContent objects
    """
    files_metadata_for_optimizer: dict[str, ModelDict] = {
        file_name: cast(ModelDict, meta.model_dump(mode="json"))
        for file_name, meta in files_metadata.items()
    }
    optimization_result = await context_optimizer.optimize_context(
        task_description=task_description,
        files_content=files_content,
        files_metadata=files_metadata_for_optimizer,
        token_budget=token_budget,
        strategy="priority",
        quality_scores=quality_scores,
    )

    relevance_scores = _extract_relevance_scores_from_metadata(
        optimization_result.metadata
    )

    return _build_loaded_content_from_optimization(
        optimization_result,
        files_content,
        files_metadata,
        relevance_scores,
        context_optimizer.token_counter,
    )


async def _read_all_files_for_loading(
    metadata_index: MetadataIndex,
    file_system: FileSystemManager,
) -> tuple[dict[str, str], dict[str, FileMetadataForScoring]]:
    """Read all files for loading.

    Args:
        metadata_index: MetadataIndex instance
        file_system: FileSystemManager instance

    Returns:
        Tuple of (files_content, files_metadata) dictionaries
    """
    all_files = await metadata_index.list_all_files()
    files_content: dict[str, str] = {}
    files_metadata: dict[str, FileMetadataForScoring] = {}

    for file_name in all_files:
        try:
            file_path = Path(metadata_index.memory_bank_dir) / file_name
            content, _ = await file_system.read_file(file_path)
            files_content[file_name] = content

            metadata = await metadata_index.get_file_metadata(file_name)
            if metadata:
                files_metadata[file_name] = FileMetadataForScoring.model_validate(
                    metadata
                )

        except FileNotFoundError:
            continue

    return files_content, files_metadata


def _extract_relevance_scores_from_metadata(
    metadata: dict[str, JsonValue] | None,
) -> dict[str, float]:
    """Extract relevance scores from optimization result metadata.

    Args:
        metadata: Optimization result metadata dictionary

    Returns:
        Dictionary mapping file names to relevance scores
    """
    relevance_scores: dict[str, float] = {}
    if not metadata:
        return relevance_scores

    raw = metadata.get("relevance_scores")
    if isinstance(raw, dict):
        raw_dict = cast(dict[str, JsonValue], raw)
        for key, value_raw in raw_dict.items():
            if isinstance(value_raw, (int, float)):
                relevance_scores[str(key)] = float(value_raw)

    return relevance_scores


def _build_loaded_content_from_optimization(
    optimization_result: OptimizationResult,
    files_content: dict[str, str],
    files_metadata: dict[str, FileMetadataForScoring],
    relevance_scores: dict[str, float],
    token_counter: TokenCounter,
) -> list[LoadedContent]:
    """Build LoadedContent objects from optimization result.

    Args:
        optimization_result: OptimizationResult object
        files_content: Dictionary mapping file names to content
        files_metadata: Dictionary mapping file names to metadata
        relevance_scores: Dictionary mapping file names to relevance scores
        token_counter: TokenCounter instance

    Returns:
        List of LoadedContent objects
    """
    loaded_content: list[LoadedContent] = []
    cumulative_tokens = 0

    for priority, file_name in enumerate(optimization_result.selected_files):
        content_item = _build_single_loaded_content(
            file_name,
            files_content,
            files_metadata,
            relevance_scores,
            token_counter,
            priority,
            cumulative_tokens,
        )
        loaded_content.append(content_item)
        cumulative_tokens += content_item.tokens

    return loaded_content


def _build_single_loaded_content(
    file_name: str,
    files_content: dict[str, str],
    files_metadata: dict[str, FileMetadataForScoring],
    relevance_scores: dict[str, float],
    token_counter: TokenCounter,
    priority: int,
    cumulative_tokens: int,
) -> LoadedContent:
    """Build a single LoadedContent object."""
    content = files_content[file_name]
    tokens = token_counter.count_tokens(content)
    relevance_score = relevance_scores.get(file_name, 0.0)
    file_metadata = files_metadata.get(file_name)
    meta_dict: dict[str, JsonValue] = (
        file_metadata.model_dump(mode="json") if file_metadata is not None else {}
    )
    meta_dict["tokens"] = tokens
    meta_dict["priority"] = priority
    metadata_model = FileContentMetadata.model_validate(meta_dict)
    return LoadedContent(
        file_name=file_name,
        content=content,
        tokens=tokens,
        cumulative_tokens=cumulative_tokens + tokens,
        priority=priority,
        relevance_score=relevance_score,
        more_available=True,
        metadata=metadata_model,
    )


async def _process_priority_file(
    loader: ProgressiveLoader,
    file_name: str,
    priority: int,
    priority_order: list[str],
    cumulative_tokens: int,
    token_budget: int,
) -> LoadedContent | None:
    """Process a single file for priority loading."""
    try:
        file_path = _resolve_file_path(loader, file_name)
        content, _ = await loader.file_system.read_file(file_path)
        tokens = loader.context_optimizer.token_counter.count_tokens(content)

        if cumulative_tokens + tokens > token_budget:
            return None

        return await _build_priority_loaded_content(
            loader,
            file_name,
            content,
            tokens,
            priority,
            priority_order,
            cumulative_tokens,
        )

    except FileNotFoundError:
        return None


async def _build_priority_loaded_content(
    loader: ProgressiveLoader,
    file_name: str,
    content: str,
    tokens: int,
    priority: int,
    priority_order: list[str],
    cumulative_tokens: int,
) -> LoadedContent:
    """Build LoadedContent for priority file."""
    cumulative_tokens += tokens
    more_available = priority < len(priority_order) - 1
    metadata = _build_file_content_metadata(
        await loader.metadata_index.get_file_metadata(file_name),
        tokens=tokens,
        priority=priority,
    )
    return LoadedContent(
        file_name=file_name,
        content=content,
        tokens=tokens,
        cumulative_tokens=cumulative_tokens,
        priority=priority,
        relevance_score=0.0,
        more_available=more_available,
        metadata=metadata,
    )


def _resolve_file_path(loader: ProgressiveLoader, file_name: str) -> Path:
    """Resolve file path for priority loading."""
    file_path = Path(file_name)
    if not file_path.is_absolute():
        file_path = loader.file_system.memory_bank_dir / file_name
    return file_path
