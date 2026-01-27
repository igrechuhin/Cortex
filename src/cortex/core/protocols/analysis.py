#!/usr/bin/env python3
"""Analysis protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for pattern analysis and
structure analysis.
"""

from pathlib import Path
from typing import Protocol

from cortex.analysis.models import (
    AccessFrequencyEntry,
    AntiPatternInfo,
    CoAccessPattern,
    StructureAnalysisData,
    UnusedFileInfo,
)


class PatternAnalyzerProtocol(Protocol):
    """Protocol for pattern analysis operations using structural subtyping (PEP 544).

    This protocol defines the interface for analyzing access patterns, co-access
    correlations, and identifying unused files. Pattern analysis provides insights
    for optimization and refactoring decisions. A class implementing these methods
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
            ) -> dict[str, AccessFrequencyEntry]:
                cutoff = datetime.utcnow() - timedelta(days=time_window_days)
                files_metadata = await self.metadata_index.get_all_files_metadata()

                freq = {}
                for fname, metadata in files_metadata.items():
                    last_access_str = metadata.last_read or "2000-01-01"
                    last_access = datetime.fromisoformat(last_access_str)
                    if last_access >= cutoff:
                        read_count = metadata.read_count
                        freq[fname] = AccessFrequencyEntry(
                            read_count=read_count,
                            access_count=read_count,
                            frequency=(
                                read_count / time_window_days
                                if time_window_days > 0 else 0.0
                            ),
                            avg_accesses_per_day=(
                                read_count / time_window_days
                                if time_window_days > 0 else 0.0
                            ),
                            last_access=last_access_str,
                        )
                return freq

            async def get_co_access_patterns(
                self, min_correlation: float = 0.5
            ) -> list[CoAccessPattern]:
                # Calculate files accessed together
                patterns = []
                # Implementation: track access sessions and calculate correlations
                return patterns

            async def get_unused_files(
                self, days_threshold: int = 90
            ) -> list[UnusedFileInfo]:
                cutoff = datetime.utcnow() - timedelta(days=days_threshold)
                files_metadata = await self.metadata_index.get_all_files_metadata()

                unused = []
                for fname, metadata in files_metadata.items():
                    last_access_str = metadata.last_read or "2000-01-01"
                    last_access = datetime.fromisoformat(last_access_str)
                    if last_access < cutoff:
                        unused.append(UnusedFileInfo(
                            file_name=fname,
                            file=fname,
                            days_since_access=(datetime.utcnow() - last_access).days,
                            last_access=last_access_str,
                            size_bytes=metadata.size_bytes,
                        ))
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
    ) -> dict[str, AccessFrequencyEntry]:
        """Get file access frequency within time window.

        Args:
            time_window_days: Days to look back

        Returns:
            Dict mapping file names to access frequency entry models
        """
        ...

    async def get_co_access_patterns(
        self, min_correlation: float = 0.5
    ) -> list[CoAccessPattern]:
        """Get files frequently accessed together.

        Args:
            min_correlation: Minimum correlation threshold

        Returns:
            List of co-access pattern models
        """
        ...

    async def get_unused_files(self, days_threshold: int = 90) -> list[UnusedFileInfo]:
        """Get files not accessed recently.

        Args:
            days_threshold: Days since last access

        Returns:
            List of unused file info models
        """
        ...


class StructureAnalyzerProtocol(Protocol):
    """Protocol for structure analysis operations using structural subtyping (PEP 544).

    This protocol defines the interface for analyzing Memory Bank file organization
    and detecting structural anti-patterns. Structure analysis identifies issues like
    deep nesting, circular dependencies, and orphaned files. A class implementing
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

            async def analyze_organization(
                self, memory_bank_path: Path
            ) -> StructureAnalysisData:
                from cortex.analysis.models import (
                    AntiPatternInfo,
                    ComplexityAnalysisResult,
                )
                files = list(memory_bank_path.rglob("*.md"))
                max_depth = max(
                    (len(f.relative_to(memory_bank_path).parts) for f in files),
                    default=0,
                )

                organization = FileOrganizationResult(
                    status="analyzed",
                    file_count=len(files),
                )

                anti_patterns = []
                # Check for deep nesting
                for file in memory_bank_path.rglob("*.md"):
                    depth = len(file.relative_to(memory_bank_path).parts)
                    if depth > 3:
                        anti_patterns.append(AntiPatternInfo(
                            type="deep_nesting",
                            path=str(file),
                            severity="warning",
                            description=f"File nested at depth {depth}",
                        ))

                # Check for circular dependencies
                cycles = self.dependency_graph.detect_cycles()
                for cycle in cycles:
                    anti_patterns.append(AntiPatternInfo(
                        type="circular_dependency",
                        path=", ".join(cycle),
                        severity="error",
                        description=f"Circular dependency: {' -> '.join(cycle)}",
                    ))

                from cortex.analysis.models import ComplexityAssessment
                complexity = ComplexityAnalysisResult(
                    status="analyzed",
                    metrics=ComplexityMetrics(
                        max_dependency_depth=max_depth,
                    ),
                    assessment=ComplexityAssessment(
                        status=(
                            "healthy"
                            if not self.dependency_graph.has_circular_dependency()
                            else "warning"
                        ),
                    ),
                )

                return StructureAnalysisData(  # noqa: E501
                    organization=organization,
                    anti_patterns=anti_patterns,
                    complexity_metrics=complexity,
                )

            async def detect_anti_patterns(
                self, memory_bank_path: Path
            ) -> list[AntiPatternInfo]:
                anti_patterns = []

                # Check for deep nesting
                for file in memory_bank_path.rglob("*.md"):
                    depth = len(file.relative_to(memory_bank_path).parts)
                    if depth > 3:
                        anti_patterns.append(AntiPatternInfo(
                            type="deep_nesting",
                            path=str(file),
                            severity="warning",
                            description=f"File nested at depth {depth}",
                        ))

                # Check for circular dependencies
                cycles = self.dependency_graph.detect_cycles()
                for cycle in cycles:
                    anti_patterns.append(AntiPatternInfo(
                        type="circular_dependency",
                        path=", ".join(cycle),
                        severity="error",
                        description=f"Circular dependency: {' -> '.join(cycle)}",
                    ))

                return anti_patterns

        # SimpleStructureAnalyzer automatically satisfies StructureAnalyzerProtocol
        ```

    Note:
        - Detects organizational smells
        - Identifies circular dependencies
        - Suggests structural improvements
    """

    async def analyze_organization(
        self, memory_bank_path: Path
    ) -> StructureAnalysisData:
        """Analyze Memory Bank file organization.

        Args:
            memory_bank_path: Path to Memory Bank directory

        Returns:
            Structure analysis data model
        """
        ...

    async def detect_anti_patterns(
        self, memory_bank_path: Path
    ) -> list[AntiPatternInfo]:
        """Detect structural anti-patterns.

        Args:
            memory_bank_path: Path to Memory Bank directory

        Returns:
            List of anti-pattern info models
        """
        ...


__all__ = [
    "PatternAnalyzerProtocol",
    "StructureAnalyzerProtocol",
]
