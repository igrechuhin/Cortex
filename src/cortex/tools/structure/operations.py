# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Phase 8 structure cleanup operations for check_structure_health."""

from datetime import datetime, timedelta
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonDict
from cortex.core.token_counter import TokenCounter
from cortex.structure.lifecycle.legacy_cursor_cleanup import (
    cleanup_legacy_cursor_artifacts,
)
from cortex.structure.manager import StructureManager
from cortex.tools.structure.structure_models import CleanupActionResult, CleanupReport


def _get_default_cleanup_actions() -> list[str]:
    """Get default list of cleanup actions."""
    return [
        "archive_stale",
        "organize_plans",
        "remove_legacy_cursor_artifacts",
        "update_index",
        "remove_empty",
    ]


async def _execute_cleanup_actions(
    cleanup_actions: list[str],
    structure_mgr: StructureManager,
    stale_days: int,
    dry_run: bool,
    project_root: Path,
    cleanup_report: CleanupReport,
) -> None:
    """Execute cleanup actions."""
    if "archive_stale" in cleanup_actions:
        perform_archive_stale(structure_mgr, stale_days, dry_run, cleanup_report)

    if "remove_legacy_cursor_artifacts" in cleanup_actions:
        perform_remove_legacy_cursor_artifacts(project_root, cleanup_report)

    if "update_index" in cleanup_actions:
        await perform_update_index(project_root, dry_run, cleanup_report)

    if "remove_empty" in cleanup_actions:
        perform_remove_empty(structure_mgr, cleanup_report)


async def perform_cleanup_actions(
    structure_mgr: StructureManager,
    cleanup_actions: list[str] | None,
    stale_days: int,
    dry_run: bool,
    project_root: Path,
) -> CleanupReport:
    """Perform cleanup actions and return report."""
    cleanup_actions = cleanup_actions or _get_default_cleanup_actions()

    cleanup_report = CleanupReport(
        dry_run=dry_run,
        actions_performed=[],
        files_modified=[],
        recommendations=[],
        post_cleanup_health=JsonDict.from_dict({}),
    )

    await _execute_cleanup_actions(
        cleanup_actions,
        structure_mgr,
        stale_days,
        dry_run,
        project_root,
        cleanup_report,
    )

    post_cleanup_health = structure_mgr.check_structure_health()
    cleanup_report.post_cleanup_health = JsonDict.from_dict(post_cleanup_health)

    return cleanup_report


def find_stale_plans(plans_active: Path, stale_threshold: datetime) -> list[Path]:
    """Find stale plan files."""
    stale_plans: list[Path] = []
    for plan_file in plans_active.glob("*.md"):
        if datetime.fromtimestamp(plan_file.stat().st_mtime) < stale_threshold:
            stale_plans.append(plan_file)
    return stale_plans


def record_archive_action(report: CleanupReport, stale_plans: list[Path]) -> None:
    """Record archive action in report."""
    report.actions_performed.append(
        CleanupActionResult(
            action="archive_stale",
            stale_plans_found=len(stale_plans),
            files=[p.name for p in stale_plans],
            legacy_cursor_artifacts_removed=None,
        )
    )


def move_stale_plans(
    plans_archived: Path, stale_plans: list[Path], report: CleanupReport
) -> None:
    """Move stale plans to archived directory."""
    plans_archived.mkdir(parents=True, exist_ok=True)
    for plan in stale_plans:
        dest = plans_archived / plan.name
        _ = plan.rename(dest)
        report.files_modified.append(f"Moved {plan.name} to archived/")


def perform_archive_stale(
    structure_mgr: StructureManager,
    stale_days: int,
    dry_run: bool,
    report: CleanupReport,
) -> None:
    """Archive stale plans older than stale_days."""
    plans_active = structure_mgr.get_path("plans") / "active"
    plans_archived = structure_mgr.get_path("plans") / "archived"
    stale_threshold = datetime.now() - timedelta(days=stale_days)

    if not plans_active.exists():
        return

    stale_plans = find_stale_plans(plans_active, stale_threshold)
    if not stale_plans:
        return

    record_archive_action(report, stale_plans)

    if not dry_run:
        move_stale_plans(plans_archived, stale_plans, report)


def perform_remove_legacy_cursor_artifacts(
    project_root: Path, report: CleanupReport
) -> None:
    """Remove leftover .cursor/ artifacts from a pre-removal Cortex version."""
    cleanup_result = cleanup_legacy_cursor_artifacts(project_root)
    removed_count = (
        len(cleanup_result.removed_symlinks)
        + len(cleanup_result.removed_agent_files)
        + len(cleanup_result.removed_mcp_configs)
    )
    report.actions_performed.append(
        CleanupActionResult(
            action="remove_legacy_cursor_artifacts",
            stale_plans_found=None,
            files=[],
            legacy_cursor_artifacts_removed=removed_count,
        )
    )


async def _process_memory_bank_file(
    file_path: Path,
    file_name: str,
    dry_run: bool,
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
) -> None:
    """Process a single memory bank file and update its metadata."""
    if dry_run:
        return

    content, content_hash = await fs_manager.read_file(file_path)
    sections_raw = fs_manager.parse_sections(content)
    sections = [section.model_dump(mode="json") for section in sections_raw]
    token_count = token_counter.count_tokens(content)

    await metadata_index.update_file_metadata(
        file_name=file_name,
        path=file_path,
        exists=True,
        size_bytes=len(content.encode("utf-8")),
        token_count=token_count,
        content_hash=content_hash,
        sections=sections,
        change_source="external",
    )


async def _collect_memory_bank_files(
    memory_bank_dir: Path,
    project_root: Path,
    dry_run: bool,
) -> list[str]:
    """Collect and process memory bank files."""
    from cortex.managers.initialization import get_managers

    if not memory_bank_dir.exists():
        return []

    mgrs = await get_managers(project_root)
    metadata_index = mgrs.index
    fs_manager = mgrs.fs
    token_counter = mgrs.tokens

    updated_files: list[str] = []
    for file_path in memory_bank_dir.glob("*.md"):
        if not file_path.is_file():
            continue

        file_name = file_path.name
        updated_files.append(file_name)

        if not dry_run:
            await _process_memory_bank_file(
                file_path, file_name, dry_run, metadata_index, fs_manager, token_counter
            )

    return updated_files


async def perform_update_index(
    project_root: Path, dry_run: bool, report: CleanupReport
) -> None:
    """Refresh metadata index for all memory bank files."""
    from cortex.core.path_resolver import CortexResourceType, get_cortex_path

    memory_bank_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    updated_files = await _collect_memory_bank_files(
        memory_bank_dir, project_root, dry_run
    )

    if updated_files:
        report.actions_performed.append(
            CleanupActionResult(
                action="update_index",
                stale_plans_found=None,
                files=updated_files,
                legacy_cursor_artifacts_removed=None,
            )
        )
        if not dry_run:
            report.files_modified.append(
                f"Refreshed metadata for {len(updated_files)} memory bank file(s)"
            )
        else:
            report.files_modified.append(
                f"Would refresh metadata for {len(updated_files)} memory bank file(s)"
            )


def perform_remove_empty(
    structure_mgr: StructureManager, report: CleanupReport
) -> None:
    """Remove empty plan directories."""
    empty_dirs: list[Path] = []
    for directory in [
        structure_mgr.get_path("plans") / "active",
        structure_mgr.get_path("plans") / "completed",
        structure_mgr.get_path("plans") / "archived",
    ]:
        if directory.exists() and not any(directory.iterdir()):
            empty_dirs.append(directory)

    if empty_dirs:
        report.actions_performed.append(
            CleanupActionResult(
                action="remove_empty",
                files=[str(d) for d in empty_dirs],
                stale_plans_found=None,
                legacy_cursor_artifacts_removed=None,
            )
        )
