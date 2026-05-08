"""Roadmap sync validation operations for Memory Bank files."""

import json
import logging
from pathlib import Path
from typing import cast

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.core.models import JsonValue
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.response_builder import error_response, success_response
from cortex.validation.roadmap_sync import (
    SyncValidationResult,
    validate_roadmap_sync,
)

logger = logging.getLogger(__name__)


def _append_candidate_root(candidate_roots: list[Path], candidate: Path) -> None:
    """Append resolved candidate root if not already present."""
    resolved = candidate.resolve()
    if resolved not in candidate_roots:
        candidate_roots.append(resolved)


def _is_cwd_related_to_root(cwd_root: Path, root: Path) -> bool:
    """Return True when cwd and root are identical or nested."""
    resolved_root = root.resolve()
    try:
        return (
            cwd_root == resolved_root
            or cwd_root.is_relative_to(resolved_root)
            or resolved_root.is_relative_to(cwd_root)
        )
    except ValueError:
        return False


def _collect_roadmap_candidate_roots(
    root: Path, fs_manager: FileSystemManager | None
) -> list[Path]:
    """Collect ordered candidate roots used for roadmap path resolution."""
    from cortex.core.usage_context import get_current_project_root

    candidate_roots: list[Path] = [root.resolve()]
    usage_root = get_current_project_root()
    if usage_root is not None:
        _append_candidate_root(candidate_roots, usage_root)
    if fs_manager is not None:
        manager_root_raw = getattr(fs_manager, "project_root", None)
        if isinstance(manager_root_raw, Path):
            _append_candidate_root(candidate_roots, manager_root_raw)
        manager_mb_raw = getattr(fs_manager, "memory_bank_dir", None)
        if isinstance(manager_mb_raw, Path):
            _append_candidate_root(candidate_roots, manager_mb_raw.parent.parent)
    cwd_root = Path.cwd().resolve()
    if _is_cwd_related_to_root(cwd_root, root):
        _append_candidate_root(candidate_roots, cwd_root)
    return candidate_roots


def _resolve_existing_roadmap_path(
    root: Path, fs_manager: FileSystemManager | None = None
) -> Path | None:
    """Find a roadmap path under root or one of its ancestors.

    This guards docs validation when a nested project path is passed as root.
    """
    candidate_roots = _collect_roadmap_candidate_roots(root, fs_manager)
    searched: set[Path] = set()
    for base_root in candidate_roots:
        for candidate_root in (base_root, *base_root.parents):
            if candidate_root in searched:
                continue
            searched.add(candidate_root)
            candidate = (
                get_cortex_path(candidate_root, CortexResourceType.MEMORY_BANK)
                / MemoryBankFile.ROADMAP
            )
            if candidate.exists():
                return candidate
    return None


def _build_roadmap_sync_error_response(
    root: Path, fs_manager: FileSystemManager | None
) -> str:
    """Build error response for missing roadmap.md.

    Returns:
        JSON string with error response
    """
    candidate_roots = _collect_roadmap_candidate_roots(root, fs_manager)
    candidate_paths = [
        str(
            get_cortex_path(candidate_root, CortexResourceType.MEMORY_BANK)
            / MemoryBankFile.ROADMAP
        )
        for candidate_root in candidate_roots
    ]
    memory_bank_root = None
    if fs_manager is not None:
        manager_mb_raw = getattr(fs_manager, "memory_bank_dir", None)
        if isinstance(manager_mb_raw, Path):
            memory_bank_root = str(manager_mb_raw.resolve())

    return json.dumps(
        error_response(
            error="roadmap.md does not exist in memory bank",
            docs_gate_memory_bank_root=memory_bank_root,
            roadmap_lookup_path=str(
                get_cortex_path(root, CortexResourceType.MEMORY_BANK)
                / MemoryBankFile.ROADMAP
            ),
            resolved_core_files=cast(JsonValue, {"roadmap": candidate_paths}),
        ),
        indent=2,
    )


def _resolve_roadmap_from_fs_manager(
    fs_manager: FileSystemManager | None,
) -> Path | None:
    """Resolve roadmap path directly from fs_manager memory_bank_dir when available."""
    if fs_manager is None:
        return None
    manager_mb_raw = getattr(fs_manager, "memory_bank_dir", None)
    if not isinstance(manager_mb_raw, Path):
        return None
    candidate = manager_mb_raw.resolve() / MemoryBankFile.ROADMAP
    if candidate.exists():
        return candidate
    return None


def _build_roadmap_sync_success_response(
    result: SyncValidationResult,
    project_root: Path,
) -> str:
    """Build success response for roadmap sync validation.

    When valid is false, the response includes missing_roadmap_entries,
    invalid_references, and unlinked_plans so callers can fix issues.

    Args:
        result: Validation result

    Returns:
        JSON string with success response
    """
    missing_entries = [item.model_dump() for item in result.missing_roadmap_entries]
    invalid_refs = [ref.model_dump() for ref in result.invalid_references]
    completed_entries = [e.model_dump() for e in result.completed_entries_in_roadmap]
    warnings = list(result.warnings)

    existing_unlinked_plans = _filter_existing_unlinked_plans(result, project_root)

    return json.dumps(
        success_response(
            check_type="roadmap_sync",
            valid=result.valid,
            missing_roadmap_entries=cast(JsonValue, missing_entries),
            invalid_references=cast(JsonValue, invalid_refs),
            # Expose unlinked_plans so callers can see which non-archived plans
            # are not referenced in roadmap.md (helps prevent partial updates
            # where plans are completed or removed from roadmap without proper
            # archiving or memory bank updates). Only include plans that still
            # exist on disk to avoid stale warnings from removed/archived plans.
            unlinked_plans=cast(JsonValue, existing_unlinked_plans),
            completed_entries_in_roadmap=cast(JsonValue, completed_entries),
            warnings=cast(JsonValue, warnings),
            summary=cast(
                JsonValue,
                {
                    "total_todos_found": result.total_todos_found,
                    "missing_entries_count": len(missing_entries),
                    "invalid_references_count": len(invalid_refs),
                    "completed_entries_count": len(completed_entries),
                    "warnings_count": len(warnings),
                },
            ),
        ),
        indent=2,
    )


def _filter_existing_unlinked_plans(
    result: SyncValidationResult,
    project_root: Path,
) -> list[str]:
    """Return only unlinked plans that still exist on disk.

    This protects against stale index/history data where a plan has been
    archived or removed but an old path still appears in SyncValidationResult.
    """
    existing_unlinked_plans: list[str] = []
    for path_str in result.unlinked_plans:
        candidate = project_root / path_str
        try:
            if candidate.is_file():
                existing_unlinked_plans.append(path_str)
        except OSError:
            # If path resolution fails for any reason, treat it as non-existent.
            continue
    return existing_unlinked_plans


def _log_roadmap_ghost_sections(roadmap_content: str, roadmap_path: Path) -> None:
    """Log if roadmap content contains ghost sections (debugging)."""
    logger.info(
        "Roadmap sync validation: reading from %s (absolute: %s, size: %d chars, exists: %s)",
        roadmap_path,
        roadmap_path.resolve(),
        len(roadmap_content),
        roadmap_path.exists(),
    )
    ghost_sections = [
        "## Recent Findings",
        "## Completed Milestones",
        "### Planned Phases",
    ]
    found_ghost_sections = [s for s in ghost_sections if s in roadmap_content]
    if found_ghost_sections:
        logger.error(
            (
                "CRITICAL: Roadmap content contains ghost sections that should not exist: %s. "
                + "This indicates the validator is reading from the wrong file or stale content."
            ),
            found_ghost_sections,
        )
        logger.error(
            "Roadmap content preview (first 1000 chars): %s", roadmap_content[:1000]
        )
        logger.error(
            "Roadmap content preview (last 500 chars): %s", roadmap_content[-500:]
        )


async def handle_roadmap_sync_validation(
    fs_manager: FileSystemManager,
    root: Path,
    file_name: str | None,
) -> str:
    """Handle roadmap synchronization validation.

    Args:
        fs_manager: File system manager
        root: Project root path
        file_name: Ignored (roadmap sync always validates entire roadmap)

    Returns:
        JSON string with roadmap sync validation results
    """
    roadmap_path = _resolve_existing_roadmap_path(root, fs_manager)
    if roadmap_path is None:
        roadmap_path = _resolve_roadmap_from_fs_manager(fs_manager)
    if roadmap_path is None:
        return _build_roadmap_sync_error_response(root, fs_manager)

    roadmap_content, _ = await fs_manager.read_file(roadmap_path)
    _log_roadmap_ghost_sections(roadmap_content, roadmap_path)
    result = validate_roadmap_sync(root, roadmap_content)
    return _build_roadmap_sync_success_response(result, root)
