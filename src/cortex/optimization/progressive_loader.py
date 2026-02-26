"""
Progressive context loading for incremental content delivery.

This module provides functionality to load context progressively based on
various strategies (priority, dependencies, relevance, budget).
"""

from collections.abc import AsyncIterator
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex

from .context_optimizer import ContextOptimizer
from .progressive_loader_budget import (
    load_file_with_budget_check,
    to_loaded_content,
)
from .progressive_loader_metadata import build_file_content_metadata
from .progressive_loader_models import LoadedContent, LoadedFileContent
from .progressive_loader_priority import process_priority_file
from .progressive_loader_relevance import (
    optimize_and_build_loaded_content,
    read_all_files_for_loading,
)

__all__ = ["LoadedContent", "LoadedFileContent", "ProgressiveLoader"]


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

            result = await process_priority_file(
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
        metadata = build_file_content_metadata(
            metadata_obj.model_dump(mode="json") if metadata_obj else None,
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
        files_content, files_metadata = await read_all_files_for_loading(
            self.metadata_index, self.file_system
        )

        return await optimize_and_build_loaded_content(
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
        """Load files until budget is reached."""
        loaded_content: list[LoadedContent] = []
        cumulative_tokens = 0

        for priority, file_name in enumerate(files):
            if stop_at_budget and cumulative_tokens >= token_budget:
                break

            content_item = await load_file_with_budget_check(
                self,
                file_name,
                cumulative_tokens,
                token_budget,
                stop_at_budget=stop_at_budget,
            )
            if not content_item:
                continue

            cumulative_tokens = content_item.cumulative_tokens
            loaded_content.append(
                to_loaded_content(
                    file_name,
                    content_item,
                    priority,
                    more_available=priority < len(files) - 1,
                )
            )

        return loaded_content

    def get_default_priority_order(self) -> list[str]:
        """
        Get default file priority order.

        Returns:
            List of file names in priority order
        """
        return [
            "memorybankinstructions.md",
            MemoryBankFile.PROJECT_BRIEF,
            MemoryBankFile.ACTIVE_CONTEXT,
            MemoryBankFile.SYSTEM_PATTERNS,
            MemoryBankFile.TECH_CONTEXT,
            MemoryBankFile.PRODUCT_CONTEXT,
            MemoryBankFile.PROGRESS,
        ]

    async def stream_by_priority(
        self,
        task_description: str,  # noqa: ARG002
        token_budget: int,
        priority_order: list[str] | None = None,
    ) -> AsyncIterator[LoadedContent]:
        """Stream files in priority order (async generator)."""
        if priority_order is None:
            priority_order = self.get_default_priority_order()

        cumulative_tokens = 0

        for priority, file_name in enumerate(priority_order):
            if cumulative_tokens >= token_budget:
                break

            content_item = await load_file_with_budget_check(
                self,
                file_name,
                cumulative_tokens,
                token_budget,
                stop_at_budget=True,
            )
            if not content_item:
                break

            cumulative_tokens = content_item.cumulative_tokens
            more = (
                priority < len(priority_order) - 1 and cumulative_tokens < token_budget
            )
            yield to_loaded_content(file_name, content_item, priority, more)

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
        loaded = await self.load_by_relevance(
            task_description, token_budget, quality_scores
        )

        for content in loaded:
            yield content
