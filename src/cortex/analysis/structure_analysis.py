"""
Structure Analysis - Analyze file organization.

This module analyzes the overall file organization of the Memory Bank,
including file sizes, statistics, and organizational issues.
"""

from pathlib import Path

from cortex.analysis.models import FileSizeInfo
from cortex.core.dependency_graph import DependencyGraph
from cortex.core.models import FileOrganizationResult, FileSizeEntry


def get_size_bytes_for_sort(file_info: FileSizeInfo | FileSizeEntry) -> int:
    """Extract size_bytes as int for sorting.

    Args:
        file_info: FileSizeInfo or FileSizeEntry model

    Returns:
        Size in bytes
    """
    return file_info.size_bytes


def build_empty_organization_result() -> FileOrganizationResult:
    """Build result for empty memory bank.

    Returns:
        Empty organization result model
    """
    return FileOrganizationResult(
        status="empty",
        file_count=0,
        issues=["No files found in memory bank"],
    )


def build_organization_analysis_result(
    file_count: int,
    stats: dict[str, int],
    file_sizes: list[FileSizeInfo],
    issues: list[str],
) -> FileOrganizationResult:
    """Build organization analysis result model.

    Args:
        file_count: Total number of files
        stats: Size statistics dictionary
        file_sizes: List of FileSizeInfo models
        issues: List of identified issues

    Returns:
        FileOrganizationResult model
    """
    # Convert FileSizeInfo to FileSizeEntry for the result model
    largest_files = [
        FileSizeEntry(file=f.file, size_bytes=f.size_bytes, tokens=f.tokens)
        for f in file_sizes[:5]
    ]
    smallest_files = [
        FileSizeEntry(file=f.file, size_bytes=f.size_bytes, tokens=f.tokens)
        for f in file_sizes[-5:]
    ]

    return FileOrganizationResult(
        status="analyzed",
        file_count=file_count,
        total_size_bytes=stats["total_size"],
        total_size_kb=round(stats["total_size"] / 1024, 2),
        avg_size_bytes=round(stats["avg_size"]),
        avg_size_kb=round(stats["avg_size"] / 1024, 2),
        max_size_bytes=stats["max_size"],
        min_size_bytes=stats["min_size"],
        largest_files=largest_files,
        smallest_files=smallest_files,
        issues=issues if issues else None,
    )


def calculate_size_statistics(
    file_sizes: list[FileSizeInfo], file_count: int
) -> dict[str, int]:
    """Calculate size statistics from file sizes.

    Args:
        file_sizes: List of FileSizeInfo models
        file_count: Total number of files

    Returns:
        Dictionary with size statistics
    """
    total_size = sum(f.size_bytes for f in file_sizes)
    avg_size = total_size // file_count if file_count > 0 else 0
    max_size = file_sizes[0].size_bytes if file_sizes else 0
    min_size = file_sizes[-1].size_bytes if file_sizes else 0

    return {
        "total_size": total_size,
        "avg_size": avg_size,
        "max_size": max_size,
        "min_size": min_size,
    }


def identify_size_issues(file_sizes: list[FileSizeInfo]) -> list[str]:
    """Identify size-related issues in files.

    Args:
        file_sizes: List of FileSizeInfo models

    Returns:
        List of identified issues
    """
    issues: list[str] = []

    large_files = [f for f in file_sizes if f.size_bytes > 50000]
    if large_files:
        issues.append(f"{len(large_files)} files are very large (>50KB)")

    small_files = [f for f in file_sizes if f.size_bytes < 500]
    if small_files:
        issues.append(f"{len(small_files)} files are very small (<500 bytes)")

    return issues


def collect_file_sizes(all_files: list[Path]) -> list[FileSizeInfo]:
    """Collect file size information for all files.

    Args:
        all_files: List of file paths to analyze

    Returns:
        List of FileSizeInfo models sorted by size descending
    """

    def _get_file_size(file_path: Path) -> FileSizeInfo | None:
        """Get file size info, returning None on error."""
        try:
            size = file_path.stat().st_size
            return FileSizeInfo(
                file=file_path.name,
                size_bytes=size,
                tokens=0,  # Will be calculated separately if needed
            )
        except OSError:
            return None

    file_sizes = [
        size_info
        for file_path in all_files
        if (size_info := _get_file_size(file_path)) is not None
    ]
    file_sizes.sort(key=get_size_bytes_for_sort, reverse=True)
    return file_sizes


def build_dependency_graph(
    dependency_graph: DependencyGraph,
) -> dict[str, dict[str, list[str]]]:
    """
    Build dependency graph from DependencyGraph manager.

    Args:
        dependency_graph: DependencyGraph manager instance

    Returns:
        Dictionary mapping file names to their dependencies and dependents
    """
    all_file_names = dependency_graph.get_all_files()
    graph: dict[str, dict[str, list[str]]] = {}

    for file_name in all_file_names:
        graph[file_name] = {
            "dependencies": dependency_graph.get_dependencies(file_name),
            "dependents": dependency_graph.get_dependents(file_name),
        }

    return graph
