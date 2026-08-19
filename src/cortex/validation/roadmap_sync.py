"""Roadmap synchronization validation utilities.

This module provides tools for validating that roadmap.md stays synchronized
with the codebase, ensuring all production TODOs are tracked and all roadmap
references remain valid.
"""

import logging
import re
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.pydantic_extra import EXTRA_FORBID


class TodoCategory(str, Enum):
    """Category of roadmap sync TODO findings."""

    TODO = "todo"


class TodoItem(BaseModel):
    """Represents a TODO item found in the codebase."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file_path: str = Field(description="Path to file containing TODO")
    line: int = Field(ge=1, description="Line number of TODO")
    snippet: str = Field(description="Code snippet containing TODO")
    category: TodoCategory = Field(description="Category of TODO")


class RoadmapReference(BaseModel):
    """Represents a file reference found in the roadmap."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file_path: str = Field(description="Path to referenced file")
    line: int | None = Field(default=None, ge=1, description="Line number if specified")
    context: str = Field(description="Context of reference")
    phase: str | None = Field(default=None, description="Phase if specified")


class CompletedEntryInRoadmap(BaseModel):
    """A roadmap bullet that looks like completed work (violates future-only rule)."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    line: int = Field(ge=1, description="1-based line number in roadmap.md")
    snippet: str = Field(description="Bullet line content (trimmed)")


def _default_completed_entries_in_roadmap() -> list[CompletedEntryInRoadmap]:
    """Return empty list for SyncValidationResult.default_factory (typed)."""
    return []


class SyncValidationResult(BaseModel):
    """Result of roadmap synchronization validation."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    valid: bool = Field(description="Whether validation passed")
    total_todos_found: int = Field(
        ge=0,
        description="Total TODOs found in production code",
    )
    missing_roadmap_entries: list[TodoItem] = Field(
        default_factory=lambda: list[TodoItem](),
        description="TODOs not tracked in roadmap",
    )
    invalid_references: list[RoadmapReference] = Field(
        default_factory=lambda: list[RoadmapReference](),
        description="Invalid file references in roadmap",
    )
    unlinked_plans: list[str] = Field(
        default_factory=list,
        description=(
            "Plan files under .cortex/plans (excluding .cortex/plans/archive/) "
            "that are not referenced in roadmap.md; archived plans are excluded."
        ),
    )
    completed_entries_in_roadmap: list[CompletedEntryInRoadmap] = Field(
        default_factory=_default_completed_entries_in_roadmap,
        description=(
            "Roadmap bullet lines that look like completed work; "
            "roadmap must record future/upcoming work only."
        ),
    )
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


# Production directories to scan for TODOs
_PRODUCTION_DIRS = ["src", "scripts"]

# Marker patterns for detecting TODO comments (language-agnostic)
_TODO_PATTERNS = [
    re.compile(r"#\s*TODO[:\s]", re.IGNORECASE),
    re.compile(r"//\s*TODO[:\s]", re.IGNORECASE),
    re.compile(r"<!--\s*TODO[:\s]", re.IGNORECASE),
    re.compile(r"\*\s*TODO[:\s]", re.IGNORECASE),
]

# Path-segment-aware patterns to exclude (test/example dirs and files only)
_EXCLUDE_PATTERNS = [
    re.compile(r"(^|/)tests?/", re.IGNORECASE),  # test/ or tests/ directory
    re.compile(r"(^|/)test_[^/]+\.py$", re.IGNORECASE),  # test_*.py files
    re.compile(r"(^|/)conftest\.py$", re.IGNORECASE),  # conftest.py
    re.compile(r"(^|/)examples?/", re.IGNORECASE),  # example/ or examples/
    re.compile(r"(^|/)samples?/", re.IGNORECASE),  # sample/ or samples/
    re.compile(r"(^|/)demos?/", re.IGNORECASE),  # demo/ or demos/
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
                                category=TodoCategory.TODO,
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
    # AI: extensions are ordered longest-first (json before js, tsx/jsx before
    # ts/js) and guarded by a negative lookahead so an extension never matches
    # a prefix of a longer token (e.g. `.json` parsed as a phantom `.js`).
    file_ref_pattern = re.compile(
        r"`?([a-zA-Z0-9_./-]+\.(json|jsx|tsx|java|py|md|ts|js|go|rs|kt))"
        + r"(?![a-zA-Z0-9_])(?::(\d+))?`?"
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

            # Normalize paths: drop a leading `./` or `/`, never leading dots.
            # AI: `lstrip("./")` strips a character SET, so it ate the dot of every
            # dotfile path -- `.github/scripts/select-xcode.py` became
            # `github/scripts/select-xcode.py`, which resolves nowhere and was
            # reported invalid even though the file exists and the roadmap was right.
            normalized_path = re.sub(r"^(?:\.{1,2}/|/)+", "", file_path)

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
        todo_file = todo.file_path.lower()
        if todo_file not in roadmap_lower:
            missing_entries.append(todo)
    return missing_entries


def _plans_suffix(file_path: str, prefix: str) -> Path:
    """Return Path for the part of file_path after prefix (e.g. archive/Phase62/foo)."""
    suffix = file_path[len(prefix) :].lstrip("/")
    return Path(suffix) if suffix else Path()


def _find_plan_in_plans_or_archive(plans_root: Path, relative_path: str) -> Path:
    """Resolve plan path: plans root first, then under archive by basename.

    Roadmap entries often reference plans as .cortex/plans/foo.md. When a plan
    is archived it moves to .cortex/plans/archive/SessionOptimization/foo.md.
    This helper returns the path that exists (root or archive), or the root path
    so callers get consistent "does not exist" behavior.
    """
    candidate = plans_root / relative_path
    if candidate.exists():
        return candidate
    name = Path(relative_path).name
    archive_dir = plans_root / "archive"
    if archive_dir.is_dir():
        for path in archive_dir.rglob(name):
            if path.is_file():
                return path
    return candidate


def _resolve_reference_path(project_root: Path, ref: RoadmapReference) -> Path:
    """Resolve roadmap reference path using Cortex structure.

    Plans references are resolved against .cortex/plans regardless of path style:
    - plans/..., cortex/plans/... (normalized from .cortex/plans/), .cortex/plans/...
    all map to project_root/.cortex/plans/...
    Other cortex/ paths (normalized from .cortex/) map to project_root/.cortex/...
    """
    plans_root = get_cortex_path(project_root, CortexResourceType.PLANS)
    if ref.file_path.startswith("plans/"):
        suffix = _plans_suffix(ref.file_path, "plans/")
        return _find_plan_in_plans_or_archive(plans_root, str(suffix))
    if ref.file_path.startswith("cortex/plans/"):
        suffix = _plans_suffix(ref.file_path, "cortex/plans/")
        return _find_plan_in_plans_or_archive(plans_root, str(suffix))
    if ref.file_path.startswith(".cortex/plans/"):
        suffix = _plans_suffix(ref.file_path, ".cortex/plans/")
        return _find_plan_in_plans_or_archive(plans_root, str(suffix))
    if ref.file_path.startswith("cortex/"):
        cortex_root = get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
        return cortex_root / ref.file_path[len("cortex/") :]
    # Bare .md filenames (e.g. activeContext.md) resolve to memory-bank when present
    if "/" not in ref.file_path and ref.file_path.endswith(".md"):
        memory_bank_root = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
        candidate = memory_bank_root / ref.file_path
        if candidate.exists():
            return candidate
    return project_root / ref.file_path


def _format_missing_reference_warning(
    ref: RoadmapReference, resolved_path: Path, project_root: Path
) -> str:
    """Create a human-readable warning for a missing reference target."""
    try:
        display_path = resolved_path.relative_to(project_root)
    except ValueError:
        display_path = resolved_path

    phase_text = f" in phase '{ref.phase}'" if ref.phase else ""
    return (
        f"Invalid reference `{ref.file_path}`{phase_text} "
        f"(resolved to `{display_path}` but file does not exist)"
    )


def _is_legacy_pre_commit_reference(ref: RoadmapReference) -> bool:
    """Check if reference is a legacy pre-commit reference."""
    return ref.file_path in {
        "pre_commit_tools.py",
        "src/cortex/tools/pre_commit_tools.py",
    }


def _plan_exists_in_archive(project_root: Path, ref: RoadmapReference) -> bool:
    """Return True if this plan reference exists under plans/archive (e.g. archived).

    When roadmap entries reference Plan: .cortex/plans/X.md and X was moved to
    archive, the reference should still be considered valid.
    """
    plans_root = get_cortex_path(project_root, CortexResourceType.PLANS)
    try:
        _ = _resolve_reference_path(project_root, ref).relative_to(plans_root)
    except ValueError:
        return False
    archive_root = get_cortex_path(project_root, CortexResourceType.PLANS_ARCHIVE)
    if not archive_root.exists():
        return False
    name = Path(ref.file_path).name
    for candidate in archive_root.rglob(name):
        if candidate.is_file():
            return True
    return False


def _validate_line_reference(ref: RoadmapReference, resolved_path: Path) -> str | None:
    """Validate line reference exists in file. Returns warning message or None."""
    if ref.line is None:
        return None
    try:
        content = resolved_path.read_text(encoding="utf-8")
        total_lines = len(content.splitlines())
        if ref.line > total_lines:
            return (
                f"Reference to {ref.file_path}:{ref.line} "
                f"exceeds file length ({total_lines} lines)"
            )
    except (UnicodeDecodeError, PermissionError):
        return f"Cannot verify line reference in {ref.file_path}"
    return None


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
        if _is_legacy_pre_commit_reference(ref):
            warnings.append(
                f"Ignoring legacy pre-commit reference to {ref.file_path} in phase '{ref.phase or 'unknown'}'"
            )
            continue

        resolved_path = _resolve_reference_path(project_root, ref)
        if not resolved_path.exists():
            if _plan_exists_in_archive(project_root, ref):
                continue
            invalid_refs.append(ref)
            warnings.append(
                _format_missing_reference_warning(ref, resolved_path, project_root)
            )
            continue

        line_warning = _validate_line_reference(ref, resolved_path)
        if line_warning:
            warnings.append(line_warning)

    return invalid_refs, warnings


_GHOST_SECTION_MARKERS = [
    "## Recent Findings",
    "## Completed Milestones",
    "### Planned Phases",
]


def _has_ghost_sections(roadmap_content: str) -> bool:
    """Return True if roadmap content contains legacy ghost sections.

    These sections only exist in historical roadmap snapshots and should not
    affect validation for the current roadmap.md file.
    """
    return any(marker in roadmap_content for marker in _GHOST_SECTION_MARKERS)


def _filter_references_from_ghost_phases(
    references: list[RoadmapReference], roadmap_content: str
) -> list[RoadmapReference]:
    """Filter out references from ghost phases and log if any were removed."""
    has_ghost = _has_ghost_sections(roadmap_content)
    if not has_ghost:
        return references
    ghost_phases = ["Recent Findings", "Completed Milestones", "Planned Phases"]
    valid = [ref for ref in references if ref.phase not in ghost_phases]
    filtered_count = len(references) - len(valid)
    if filtered_count > 0:
        logging.getLogger(__name__).warning(
            (
                "Filtered %d references from ghost phases (Recent Findings, "
                + "Completed Milestones, Planned Phases) - these sections don't exist "
                + "in current roadmap.md structure"
            ),
            filtered_count,
        )
    return valid


def _list_non_archived_plan_paths(plans_root: Path) -> list[Path]:
    """Return list of non-archived .md plan paths under plans_root."""
    out: list[Path] = []
    for plan_path in plans_root.rglob("*.md"):
        try:
            relative_to_plans = plan_path.relative_to(plans_root)
        except ValueError:
            continue
        if Path(CortexResourceType.PLANS_ARCHIVE.value).name in relative_to_plans.parts:
            continue
        out.append(plan_path)
    return out


def _find_unlinked_plans(
    project_root: Path, references: list[RoadmapReference]
) -> list[str]:
    """Find plan files that are not referenced in roadmap.md.

    Only non-archived plans under .cortex/plans are required to be linked;
    archived plans are treated as historical and are excluded.
    """
    plans_root = get_cortex_path(project_root, CortexResourceType.PLANS)
    if not plans_root.exists():
        return []

    all_plans = _list_non_archived_plan_paths(plans_root)
    if not all_plans:
        return []

    referenced_plan_paths: set[Path] = set()
    for ref in references:
        resolved = _resolve_reference_path(project_root, ref)
        try:
            _ = resolved.relative_to(plans_root)
        except ValueError:
            continue
        if resolved.is_file():
            referenced_plan_paths.add(resolved)

    orphan_paths: list[str] = []
    for plan_path in all_plans:
        if not plan_path.is_file():
            continue
        if plan_path in referenced_plan_paths:
            continue
        try:
            display_path = plan_path.relative_to(project_root)
        except ValueError:
            display_path = plan_path
        orphan_paths.append(str(display_path))

    orphan_paths.sort()
    return orphan_paths


def _find_completed_entries_in_roadmap(
    roadmap_content: str,
) -> list[CompletedEntryInRoadmap]:
    """Find roadmap bullet lines that look like completed work.

    Roadmap must record future/upcoming work only; completed work belongs
    in activeContext.md. Detects bullets containing " - COMPLETED",
    " - COMPLETE", or " - DONE" (case-insensitive).

    Args:
        roadmap_content: Full content of roadmap.md.

    Returns:
        List of (line number, snippet) for violating lines.
    """
    out: list[CompletedEntryInRoadmap] = []
    upper_markers = (" - COMPLETED", " - COMPLETE", " - DONE")
    for one_indexed, line in enumerate(roadmap_content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        upper = stripped.upper()
        if any(m in upper for m in upper_markers):
            out.append(
                CompletedEntryInRoadmap(line=one_indexed, snippet=stripped[:200])
            )
    return out


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
    references = _filter_references_from_ghost_phases(references, roadmap_content)

    missing_entries = _check_todos_in_roadmap(todos, roadmap_content)
    invalid_refs, warnings = _validate_roadmap_references(references, project_root)
    unlinked_plans = _find_unlinked_plans(project_root, references)
    completed_entries = _find_completed_entries_in_roadmap(roadmap_content)

    # If the content we validated contains legacy "ghost" sections that are only
    # present in historical roadmap snapshots, do not let those completed
    # entries mark the current validation as failed. They are still returned
    # for visibility but treated as historical noise for validity.
    has_ghost = _has_ghost_sections(roadmap_content)

    valid = (
        len(missing_entries) == 0
        and len(invalid_refs) == 0
        and len(unlinked_plans) == 0
        and (len(completed_entries) == 0 or has_ghost)
    )

    return SyncValidationResult(
        valid=valid,
        total_todos_found=len(todos),
        missing_roadmap_entries=missing_entries,
        invalid_references=invalid_refs,
        unlinked_plans=unlinked_plans,
        completed_entries_in_roadmap=completed_entries,
        warnings=warnings,
    )
