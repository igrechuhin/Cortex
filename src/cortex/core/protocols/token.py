#!/usr/bin/env python3
"""Token counting and dependency graph protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for token counting and
dependency graph operations, enabling structural subtyping for better
abstraction and reduced circular dependencies.
"""

from pathlib import Path
from typing import Protocol

from cortex.core.models import DependencyGraphDict

from .file_system import FileSystemProtocol
from .linking import LinkParserProtocol


class TokenCounterProtocol(Protocol):
    """Protocol for token counting operations using structural subtyping (PEP 544).

    This protocol defines the interface for counting tokens in text using
    tiktoken encoding. Token counting is essential for context optimization
    and staying within model context limits. A class implementing these
    methods automatically satisfies this protocol.

    Used by:
        - TokenCounter: tiktoken-based token counting with caching
        - MetadataIndex: For updating token counts in file metadata
        - ContextOptimizer: For ensuring context stays within token budgets
        - ProgressiveLoader: For progressive context loading by token count

    Example implementation:
        ```python
        import tiktoken

        class SimpleTokenCounter:
            def __init__(self, encoding_name: str = "cl100k_base"):
                self.encoding = tiktoken.get_encoding(encoding_name)
                self.cache = {}

            def count_tokens(self, text: str | None) -> int:
                if text is None:
                    return 0
                return len(self.encoding.encode(text))

            def count_tokens_with_cache(self, text: str, content_hash: str) -> int:
                if content_hash in self.cache:
                    return self.cache[content_hash]
                count = self.count_tokens(text)
                self.cache[content_hash] = count
                return count

            async def count_tokens_in_file(self, file_path: Path) -> int:
                from cortex.core.async_file_utils import open_async_text_file
                async with open_async_text_file(file_path, "r", "utf-8") as f:
                    content = await f.read()
                return self.count_tokens(content)

        # SimpleTokenCounter automatically satisfies TokenCounterProtocol
        ```

    Note:
        - Token counts are model-specific (different encodings)
        - Caching by content hash prevents redundant calculations
        - Critical for context optimization and budget management
    """

    def count_tokens(self, text: str | None) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens in

        Returns:
            Number of tokens
        """
        ...

    def count_tokens_with_cache(self, text: str, content_hash: str) -> int:
        """Count tokens with caching by content hash.

        Args:
            text: Text to count tokens in
            content_hash: Hash of text for cache key

        Returns:
            Number of tokens
        """
        ...

    async def count_tokens_in_file(self, file_path: Path) -> int:
        """Count tokens in a file.

        Args:
            file_path: Path to file

        Returns:
            Number of tokens

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        ...


class DependencyGraphProtocol(Protocol):
    """Protocol for dependency graph operations using structural subtyping (PEP 544).

    This protocol defines the interface for managing file dependencies, computing
    optimal loading orders, and detecting circular dependencies. The dependency
    graph tracks both static (transclusion) and dynamic (discovered) dependencies.
    A class implementing these methods automatically satisfies this protocol.

    Used by:
        - DependencyGraph: Graph-based dependency tracking with cycle detection
        - ProgressiveLoader: For computing optimal file loading order
        - TransclusionEngine: For detecting circular transclusions
        - StructureAnalyzer: For analyzing dependency complexity

    Example implementation:
        ```python
        class SimpleDependencyGraph:
            def __init__(self):
                self.graph = {}  # file -> list of dependencies
                self.reverse_graph = {}  # file -> list of dependents

            def compute_loading_order(
                self, files: list[str] | None = None
            ) -> list[str]:
                # Topological sort for dependency order
                return self._topological_sort(files)

            def get_dependencies(self, file_name: str) -> list[str]:
                return self.graph.get(file_name, [])

            def get_dependents(self, file_name: str) -> list[str]:
                return self.reverse_graph.get(file_name, [])

            def add_dynamic_dependency(self, from_file: str, to_file: str):
                if from_file not in self.graph:
                    self.graph[from_file] = []
                self.graph[from_file].append(to_file)

            def has_circular_dependency(self) -> bool:
                return len(self.detect_cycles()) > 0

            def detect_cycles(self) -> list[list[str]]:
                # Detect cycles using DFS
                return self._find_cycles()

            def to_dict(self) -> DependencyGraphDict:
                return DependencyGraphDict(
                    graph=self.graph,
                    reverse=self.reverse_graph,
                    loading_order=[],
                    cycles=[]
                )

            async def build_from_links(
                self,
                file_system: FileSystemProtocol,
                link_parser: LinkParserProtocol,
                memory_bank_path: Path,
            ):
                # Build graph from file links
                pass

        # SimpleDependencyGraph automatically satisfies DependencyGraphProtocol
        ```

    Note:
        - Topological sorting provides optimal loading order
        - Cycle detection prevents infinite recursion
        - Supports both static and dynamic dependency discovery
    """

    def compute_loading_order(self, files: list[str] | None = None) -> list[str]:
        """Compute optimal loading order for files.

        Args:
            files: Files to compute order for (None = all files)

        Returns:
            Ordered list of file names
        """
        ...

    def get_dependencies(self, file_name: str) -> list[str]:
        """Get direct dependencies of a file.

        Args:
            file_name: File to get dependencies for

        Returns:
            List of dependency file names
        """
        ...

    def get_dependents(self, file_name: str) -> list[str]:
        """Get files that depend on this file.

        Args:
            file_name: File to get dependents for

        Returns:
            List of dependent file names
        """
        ...

    def add_dynamic_dependency(self, from_file: str, to_file: str):
        """Add a dynamic dependency discovered at runtime.

        Args:
            from_file: Source file
            to_file: Target file
        """
        ...

    def has_circular_dependency(self) -> bool:
        """Check if graph has circular dependencies.

        Returns:
            True if cycles exist
        """
        ...

    def detect_cycles(self) -> list[list[str]]:
        """Detect all circular dependency chains.

        Returns:
            List of cycles, each cycle is a list of file names
        """
        ...

    def to_dict(self) -> DependencyGraphDict:
        """Export graph to dictionary format.

        Returns:
            Dependency graph dictionary model
        """
        ...

    async def build_from_links(
        self,
        file_system: FileSystemProtocol,
        link_parser: LinkParserProtocol,
        memory_bank_path: Path,
    ) -> None:
        """Build dynamic dependencies from actual file links.

        Args:
            file_system: File system manager
            link_parser: Link parser instance
            memory_bank_path: Path to memory bank directory
        """
        ...


__all__ = [
    "TokenCounterProtocol",
    "DependencyGraphProtocol",
]
