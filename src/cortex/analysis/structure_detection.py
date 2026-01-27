"""
Structure Detection - Detect organizational anti-patterns.

This module detects various anti-patterns in Memory Bank structure,
including oversized files, orphaned files, excessive dependencies, etc.
"""

from pathlib import Path
from typing import Literal

from cortex.analysis.models import AntiPatternInfo


def detect_oversized_files(all_files: list[Path]) -> list[AntiPatternInfo]:
    """Detect oversized files (>100KB).

    Args:
        all_files: List of file paths to check

    Returns:
        List of oversized file anti-patterns
    """

    def _check_oversized(file_path: Path) -> AntiPatternInfo | None:
        """Check if file is oversized, returning AntiPatternInfo or None."""
        try:
            size = file_path.stat().st_size
            if size > 100000:  # > 100KB
                return AntiPatternInfo(
                    type="oversized_file",
                    severity="high",
                    file=file_path.name,
                    files=[],
                    description=f"File is very large ({round(size / 1024, 2)}KB)",
                    recommendation="Consider splitting into multiple smaller files",
                )
        except OSError:
            pass
        return None

    return [
        pattern
        for file_path in all_files
        if (pattern := _check_oversized(file_path)) is not None
    ]


def detect_orphaned_files(
    all_files: list[Path], graph: dict[str, dict[str, list[str]]]
) -> list[AntiPatternInfo]:
    """Detect orphaned files (no dependencies or dependents).

    Args:
        all_files: List of file paths to check
        graph: Dependency graph

    Returns:
        List of orphaned file anti-patterns
    """
    patterns: list[AntiPatternInfo] = [
        AntiPatternInfo(
            type="orphaned_file",
            severity="medium",
            file=file_path.name,
            files=[],
            description="File has no dependencies or dependents",
            recommendation="Link to other files or consider if it's still needed",
        )
        for file_path in all_files
        if not (
            file_path.name in graph
            and (
                graph[file_path.name].get("dependencies")
                or graph[file_path.name].get("dependents")
            )
        )
    ]

    return patterns


def detect_excessive_dependencies(
    graph: dict[str, dict[str, list[str]]],
) -> list[AntiPatternInfo]:
    """Detect files with excessive dependencies (>15).

    Args:
        graph: Dependency graph

    Returns:
        List of excessive dependency anti-patterns
    """
    return [
        AntiPatternInfo(
            type="excessive_dependencies",
            severity="medium",
            file=file_name,
            files=[],
            description=f"File depends on {dep_count} other files",
            recommendation="Consider reducing dependencies or splitting file",
        )
        for file_name, file_data in graph.items()
        if (dep_count := len(file_data.get("dependencies", []))) > 15
    ]


def detect_excessive_dependents(
    graph: dict[str, dict[str, list[str]]],
) -> list[AntiPatternInfo]:
    """Detect files with excessive dependents (>15).

    Args:
        graph: Dependency graph

    Returns:
        List of excessive dependent anti-patterns
    """
    return [
        AntiPatternInfo(
            type="excessive_dependents",
            severity="low",
            file=file_name,
            files=[],
            description=f"File is depended upon by {dependent_count} other files",
            recommendation=(
                "This is a central file - ensure it's stable and " "well-maintained"
            ),
        )
        for file_name, file_data in graph.items()
        if (dependent_count := len(file_data.get("dependents", []))) > 15
    ]


def detect_similar_filenames(all_files: list[Path]) -> list[AntiPatternInfo]:
    """Detect files with similar names (potential duplication).

    Args:
        all_files: List of file paths to check

    Returns:
        List of similar filename anti-patterns
    """
    file_names: list[str] = [f.stem for f in all_files]

    # Optimize: Sort names and use sorted order to reduce comparisons
    # Only check adjacent and nearby names in sorted order, as similar
    # names tend to cluster together alphabetically
    sorted_names = sorted(file_names, key=lambda x: x.lower())

    # Check each name against the next few names (window approach)
    # This reduces complexity from O(n²) to O(n*k) where k is window size
    window_size = min(10, len(sorted_names))  # Check next 10 names max

    similar_names: list[tuple[str, str]] = [
        (sorted_names[i], sorted_names[j])
        for i in range(len(sorted_names))
        for j in range(i + 1, min(i + 1 + window_size, len(sorted_names)))
        if sorted_names[j].lower()[0] == sorted_names[i].lower()[0]
        and (
            sorted_names[i].lower() in sorted_names[j].lower()
            or sorted_names[j].lower() in sorted_names[i].lower()
        )
    ]

    return [
        AntiPatternInfo(
            type="similar_filenames",
            severity="low",
            file=None,
            files=[f"{name1}.md", f"{name2}.md"],
            description="Files have similar names",
            recommendation="Check if content is duplicated or could be consolidated",
        )
        for name1, name2 in similar_names
    ]


def sort_patterns_by_severity(
    patterns: list[AntiPatternInfo],
) -> list[AntiPatternInfo]:
    """Sort anti-patterns by severity (high > medium > low).

    Args:
        patterns: List of anti-patterns to sort

    Returns:
        Sorted list of anti-patterns
    """
    severity_order: dict[Literal["high", "medium", "low"], int] = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }

    sorted_patterns = patterns.copy()
    sorted_patterns.sort(key=lambda p: severity_order.get(p.severity, 2))
    return sorted_patterns
