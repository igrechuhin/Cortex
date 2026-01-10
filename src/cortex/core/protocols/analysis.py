#!/usr/bin/env python3
"""Analysis protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for pattern analysis and
structure analysis.
"""

from pathlib import Path
from typing import Protocol


class PatternAnalyzerProtocol(Protocol):
    """Protocol for pattern analysis operations using structural subtyping (PEP 544).

    This protocol defines the interface for analyzing access patterns, co-access
    correlations, and identifying unused files. Pattern analysis provides insights
    for optimization and refactoring decisions. Any class implementing these methods
    automatically satisfies this protocol.

    Used by:
        - PatternAnalyzer: Analyzes file access patterns and correlations
        - InsightEngine: For generating usage-based insights
        - RefactoringEngine: For identifying refactoring opportunities
        - MCP Tools: For pattern analysis queries

    Example implementation:
        ```python
        from datetime import datetime, timedelta

        class SimplePatternAnalyzer:
            def __init__(self, metadata_index: MetadataIndexProtocol):
                self.metadata_index = metadata_index

            async def get_access_frequency(
                self, time_window_days: int = 30
            ) -> dict[str, dict[str, int | float]]:
                cutoff = datetime.utcnow() - timedelta(days=time_window_days)
                files_metadata = await self.metadata_index.get_all_files_metadata()

                freq = {}
                for fname, metadata in files_metadata.items():
                    last_access = datetime.fromisoformat(metadata.get("last_access", "2000-01-01"))
                    if last_access >= cutoff:
                        freq[fname] = {
                            "read_count": metadata.get("read_count", 0),
                            "frequency": metadata.get("read_count", 0) / time_window_days,
                        }
                return freq

            async def get_co_access_patterns(
                self, min_correlation: float = 0.5
            ) -> list[dict[str, object]]:
                # Calculate files accessed together
                patterns = []
                # Implementation: track access sessions and calculate correlations
                return patterns

            async def get_unused_files(
                self, days_threshold: int = 90
            ) -> list[dict[str, object]]:
                cutoff = datetime.utcnow() - timedelta(days=days_threshold)
                files_metadata = await self.metadata_index.get_all_files_metadata()

                unused = []
                for fname, metadata in files_metadata.items():
                    last_access = datetime.fromisoformat(metadata.get("last_access", "2000-01-01"))
                    if last_access < cutoff:
                        unused.append({"file_name": fname, "days_since_access": (datetime.utcnow() - last_access).days})
                return unused

        # SimplePatternAnalyzer automatically satisfies PatternAnalyzerProtocol
        ```

    Note:
        - Access frequency identifies hot files
        - Co-access patterns suggest consolidation opportunities
        - Unused file detection enables cleanup
    """

    async def get_access_frequency(
        self, time_window_days: int = 30
    ) -> dict[str, dict[str, int | float]]:
        """Get file access frequency within time window.

        Args:
            time_window_days: Days to look back

        Returns:
            Dict mapping file names to access statistics
        """
        ...

    async def get_co_access_patterns(
        self, min_correlation: float = 0.5
    ) -> list[dict[str, object]]:
        """Get files frequently accessed together.

        Args:
            min_correlation: Minimum correlation threshold

        Returns:
            List of co-access pattern dictionaries
        """
        ...

    async def get_unused_files(
        self, days_threshold: int = 90
    ) -> list[dict[str, object]]:
        """Get files not accessed recently.

        Args:
            days_threshold: Days since last access

        Returns:
            List of unused file dictionaries
        """
        ...


class StructureAnalyzerProtocol(Protocol):
    """Protocol for structure analysis operations using structural subtyping (PEP 544).

    This protocol defines the interface for analyzing Memory Bank file organization
    and detecting structural anti-patterns. Structure analysis identifies issues like
    deep nesting, circular dependencies, and orphaned files. Any class implementing
    these methods automatically satisfies this protocol.

    Used by:
        - StructureAnalyzer: Analyzes Memory Bank organization and anti-patterns
        - InsightEngine: For generating structural insights
        - RefactoringEngine: For generating reorganization suggestions
        - MCP Tools: For structure analysis queries

    Example implementation:
        ```python
        class SimpleStructureAnalyzer:
            def __init__(self, dependency_graph: DependencyGraphProtocol):
                self.dependency_graph = dependency_graph

            async def analyze_organization(self, memory_bank_path: Path) -> dict[str, object]:
                files = list(memory_bank_path.rglob("*.md"))
                max_depth = max((len(f.relative_to(memory_bank_path).parts) for f in files), default=0)

                return {
                    "total_files": len(files),
                    "max_depth": max_depth,
                    "avg_depth": sum(len(f.relative_to(memory_bank_path).parts) for f in files) / len(files) if files else 0,
                    "has_circular_deps": self.dependency_graph.has_circular_dependency(),
                }

            async def detect_anti_patterns(
                self, memory_bank_path: Path
            ) -> list[dict[str, object]]:
                anti_patterns = []

                # Check for deep nesting
                for file in memory_bank_path.rglob("*.md"):
                    depth = len(file.relative_to(memory_bank_path).parts)
                    if depth > 3:
                        anti_patterns.append({
                            "type": "deep_nesting",
                            "file": str(file),
                            "depth": depth,
                            "severity": "warning",
                        })

                # Check for circular dependencies
                cycles = self.dependency_graph.detect_cycles()
                for cycle in cycles:
                    anti_patterns.append({
                        "type": "circular_dependency",
                        "files": cycle,
                        "severity": "error",
                    })

                return anti_patterns

        # SimpleStructureAnalyzer automatically satisfies StructureAnalyzerProtocol
        ```

    Note:
        - Detects organizational smells
        - Identifies circular dependencies
        - Suggests structural improvements
    """

    async def analyze_organization(self, memory_bank_path: Path) -> dict[str, object]:
        """Analyze Memory Bank file organization.

        Args:
            memory_bank_path: Path to Memory Bank directory

        Returns:
            Organization analysis dictionary
        """
        ...

    async def detect_anti_patterns(
        self, memory_bank_path: Path
    ) -> list[dict[str, object]]:
        """Detect structural anti-patterns.

        Args:
            memory_bank_path: Path to Memory Bank directory

        Returns:
            List of anti-pattern dictionaries
        """
        ...


__all__ = [
    "PatternAnalyzerProtocol",
    "StructureAnalyzerProtocol",
]
