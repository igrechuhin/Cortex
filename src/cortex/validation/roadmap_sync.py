"""Roadmap synchronization validation utilities.

This module provides tools for validating that roadmap.md stays synchronized
with the codebase, ensuring all production TODOs are tracked and all roadmap
references remain valid.
"""

import re
from pathlib import Path
from typing import TypedDict


class TodoItem(TypedDict):
    """Represents a TODO item found in the codebase."""

    file_path: str
    line: int
    snippet: str
    category: str


class RoadmapReference(TypedDict):
    """Represents a file reference found in the roadmap."""

    file_path: str
    line: int | None
    context: str
    phase: str | None


class SyncValidationResult(TypedDict):
    """Result of roadmap synchronization validation."""

    valid: bool
    missing_roadmap_entries: list[TodoItem]
    invalid_references: list[RoadmapReference]
    warnings: list[str]


# Production directories to scan for TODOs
_PRODUCTION_DIRS = ["src", "scripts"]

# Marker patterns for detecting TODO comments (language-agnostic)
_TODO_PATTERNS = [
    re.compile(r"#\s*TODO[:\s]", re.IGNORECASE),
    re.compile(r"//\s*TODO[:\s]", re.IGNORECASE),
    re.compile(r"<!--\s*TODO[:\s]", re.IGNORECASE),
    re.compile(r"\*\s*TODO[:\s]", re.IGNORECASE),
]

# Patterns to exclude (test/example files)
_EXCLUDE_PATTERNS = [
    re.compile(r"test", re.IGNORECASE),
    re.compile(r"example", re.IGNORECASE),
    re.compile(r"sample", re.IGNORECASE),
    re.compile(r"demo", re.IGNORECASE),
]


def _is_production_file(file_path: Path) -> bool:
    """Check if file should be scanned for production TODOs.

    Args:
        file_path: Path to the file

    Returns:
        True if file should be scanned, False otherwise
    """
    path_str = str(file_path)
    return not any(pattern.search(path_str) for pattern in _EXCLUDE_PATTERNS)


def scan_codebase_todos(project_root: Path) -> list[TodoItem]:
    """Scan codebase for production TODO markers.

    Args:
        project_root: Root directory of the project

    Returns:
        List of TODO items found in production code
    """
    todos: list[TodoItem] = []

    for prod_dir in _PRODUCTION_DIRS:
        dir_path = project_root / prod_dir
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue

            if not _is_production_file(file_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            relative_path = file_path.relative_to(project_root)
            for line_num, line in enumerate(content.splitlines(), start=1):
                for pattern in _TODO_PATTERNS:
                    if pattern.search(line):
                        snippet = line.strip()[:100]
                        todos.append(
                            TodoItem(
                                file_path=str(relative_path),
                                line=line_num,
                                snippet=snippet,
                                category="todo",
                            )
                        )
                        break

    return todos


def parse_roadmap_references(roadmap_content: str) -> list[RoadmapReference]:
    """Parse roadmap.md for file references.

    Args:
        roadmap_content: Content of roadmap.md

    Returns:
        List of file references found in roadmap
    """
    references: list[RoadmapReference] = []

    # Pattern for file references: `path/to/file.py` or `path/to/file.py:123`
    file_ref_pattern = re.compile(
        r"`?([a-zA-Z0-9_./-]+\.(py|md|ts|js|tsx|jsx|go|rs|java|kt))(?::(\d+))?`?"
    )

    lines = roadmap_content.splitlines()
    current_phase: str | None = None

    for _line_num, line in enumerate(lines, start=1):
        # Track current phase/milestone
        if line.startswith("##"):
            phase_match = re.match(r"^##+\s*(.+)$", line)
            if phase_match:
                current_phase = phase_match.group(1).strip()

        # Find file references
        for match in file_ref_pattern.finditer(line):
            file_path = match.group(1)
            line_ref = match.group(3)
            line_number = int(line_ref) if line_ref else None

            # Normalize paths (remove leading dots/slashes)
            normalized_path = file_path.lstrip("./")

            references.append(
                RoadmapReference(
                    file_path=normalized_path,
                    line=line_number,
                    context=line.strip()[:100],
                    phase=current_phase,
                )
            )

    return references


def _check_todos_in_roadmap(
    todos: list[TodoItem], roadmap_content: str
) -> list[TodoItem]:
    """Check if all TODOs are mentioned in roadmap.

    Args:
        todos: List of TODOs found in codebase
        roadmap_content: Content of roadmap.md

    Returns:
        List of TODOs missing from roadmap
    """
    missing_entries: list[TodoItem] = []
    roadmap_lower = roadmap_content.lower()
    for todo in todos:
        todo_file = todo["file_path"].lower()
        if todo_file not in roadmap_lower:
            missing_entries.append(todo)
    return missing_entries


def _validate_roadmap_references(
    references: list[RoadmapReference], project_root: Path
) -> tuple[list[RoadmapReference], list[str]]:
    """Validate roadmap references exist and are valid.

    Args:
        references: List of roadmap references
        project_root: Root directory of the project

    Returns:
        Tuple of (invalid_references, warnings)
    """
    invalid_refs: list[RoadmapReference] = []
    warnings: list[str] = []

    for ref in references:
        file_path = project_root / ref["file_path"]
        if not file_path.exists():
            invalid_refs.append(ref)
            continue

        if ref["line"] is not None:
            try:
                content = file_path.read_text(encoding="utf-8")
                total_lines = len(content.splitlines())
                if ref["line"] > total_lines:
                    warning_msg = (
                        f"Reference to {ref['file_path']}:{ref['line']} "
                        f"exceeds file length ({total_lines} lines)"
                    )
                    warnings.append(warning_msg)
            except (UnicodeDecodeError, PermissionError):
                warnings.append(f"Cannot verify line reference in {ref['file_path']}")

    return invalid_refs, warnings


def validate_roadmap_sync(
    project_root: Path, roadmap_content: str
) -> SyncValidationResult:
    """Validate roadmap synchronization with codebase.

    Args:
        project_root: Root directory of the project
        roadmap_content: Content of roadmap.md

    Returns:
        Validation result with missing entries and invalid references
    """
    todos = scan_codebase_todos(project_root)
    references = parse_roadmap_references(roadmap_content)

    missing_entries = _check_todos_in_roadmap(todos, roadmap_content)
    invalid_refs, warnings = _validate_roadmap_references(references, project_root)

    valid = len(missing_entries) == 0 and len(invalid_refs) == 0

    return SyncValidationResult(
        valid=valid,
        missing_roadmap_entries=missing_entries,
        invalid_references=invalid_refs,
        warnings=warnings,
    )
