#!/usr/bin/env python3
"""
Migration strategies for different legacy structure types.

Each function implements migration logic for a specific legacy structure
(tradewing-style, doc-mcp-style, scattered-files, cursor-default).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import cast

from cortex.core.models import ModelDict
from cortex.core.path_resolver import CursorResourceType, get_cursor_path
from cortex.structure.migration_helpers import (
    extract_errors,
    extract_file_mappings,
    extract_files_migrated,
    extract_migration_report_data,
    initialize_migration_containers,
    migrate_memory_bank_files_from_source,
    migrate_single_file,
    update_migration_data,
    update_migration_report,
)
from cortex.structure.structure_config import STANDARD_MEMORY_BANK_FILES


def migrate_plans(
    project_root: Path,
    plans_dir: Path,
    migration_data: ModelDict,
) -> None:
    """Migrate plans from .cursor/plans to plans directory.

    Args:
        project_root: Project root directory
        plans_dir: Target plans directory
        migration_data: Migration data dictionary
    """
    files_migrated_int = cast(int, migration_data["files_migrated"])
    file_mappings_list = extract_file_mappings(migration_data)
    errors_list = extract_errors(migration_data)

    cursor_plans = get_cursor_path(project_root, CursorResourceType.PLANS)
    if cursor_plans.exists():
        plans_dir.mkdir(parents=True, exist_ok=True)
        for plan_file in cursor_plans.glob("*.md"):
            dest = plans_dir / plan_file.name
            try:
                _ = shutil.copy2(plan_file, dest)
                files_migrated_int += 1
                file_mappings_list.append(
                    {"source": str(plan_file), "destination": str(dest)}
                )
            except OSError as e:
                errors_list.append(f"Failed to migrate {plan_file.name}: {e}")

    update_migration_data(
        migration_data, files_migrated_int, file_mappings_list, errors_list
    )


def migrate_cursorrules(
    project_root: Path,
    rules_dir: Path,
    migration_data: ModelDict,
) -> None:
    """Migrate .cursorrules to rules directory.

    Args:
        project_root: Project root directory
        rules_dir: Target rules directory
        migration_data: Migration data dictionary
    """
    files_migrated_int = cast(int, migration_data["files_migrated"])
    file_mappings_list = extract_file_mappings(migration_data)
    errors_list = extract_errors(migration_data)

    cursorrules = project_root / ".cursorrules"
    if cursorrules.exists():
        dest = rules_dir / "main.cursorrules"
        try:
            _ = rules_dir.mkdir(parents=True, exist_ok=True)
            _ = shutil.copy2(cursorrules, dest)
            files_migrated_int += 1
            file_mappings_list.append(
                {"source": str(cursorrules), "destination": str(dest)}
            )
        except OSError as e:
            errors_list.append(f"Failed to migrate .cursorrules: {e}")

    update_migration_data(
        migration_data, files_migrated_int, file_mappings_list, errors_list
    )


def migrate_tradewing_style(
    project_root: Path,
    get_path: Callable[[str], Path],
    report: ModelDict,
) -> None:
    """Migrate TradeWing-style structure.

    Args:
        project_root: Project root directory
        get_path: Callable to resolve structure component paths
        report: Migration report to update
    """
    memory_bank_dir = get_path("memory_bank")
    plans_dir = get_path("plans") / "active"
    rules_dir = get_path("rules") / "local"

    migration_data = extract_migration_report_data(report)
    migrate_memory_bank_files_from_source(project_root, memory_bank_dir, migration_data)
    migrate_plans(project_root, plans_dir, migration_data)
    migrate_cursorrules(project_root, rules_dir, migration_data)
    report["files_migrated"] = migration_data["files_migrated"]
    report["file_mappings"] = migration_data["file_mappings"]
    report["errors"] = migration_data["errors"]


def migrate_doc_mcp_style(
    project_root: Path,
    get_path: Callable[[str], Path],
    report: ModelDict,
) -> None:
    """Migrate doc-mcp-style structure (docs/memory-bank as source).

    Args:
        project_root: Project root directory
        get_path: Callable to resolve structure component paths
        report: Migration report to update
    """
    memory_bank_dir = get_path("memory_bank")
    plans_dir = get_path("plans") / "active"
    rules_dir = get_path("rules") / "local"
    source_memory_bank = project_root / "docs" / "memory-bank"

    migration_data = extract_migration_report_data(report)
    migrate_memory_bank_files_from_source(
        source_memory_bank, memory_bank_dir, migration_data
    )
    migrate_plans(project_root, plans_dir, migration_data)
    migrate_cursorrules(project_root, rules_dir, migration_data)
    report["files_migrated"] = migration_data["files_migrated"]
    report["file_mappings"] = migration_data["file_mappings"]
    report["errors"] = migration_data["errors"]


def migrate_scattered_files(
    project_root: Path,
    get_path: Callable[[str], Path],
    report: ModelDict,
) -> None:
    """Migrate scattered files.

    Args:
        project_root: Project root directory
        get_path: Callable to resolve structure component paths
        report: Migration report to update
    """
    memory_bank_dir = get_path("memory_bank")
    files_migrated_int, file_mappings_list, errors_list = (
        initialize_migration_containers(report)
    )

    for filename in STANDARD_MEMORY_BANK_FILES:
        files_migrated_int = migrate_single_file(
            project_root,
            filename,
            memory_bank_dir,
            files_migrated_int,
            file_mappings_list,
            errors_list,
        )

    update_migration_report(report, files_migrated_int, file_mappings_list, errors_list)


def migrate_cursor_default(
    project_root: Path,
    get_path: Callable[[str], Path],
    report: ModelDict,
) -> None:
    """Migrate Cursor default structure.

    Args:
        project_root: Project root directory
        get_path: Callable to resolve structure component paths
        report: Migration report to update
    """
    rules_dir = get_path("rules") / "local"
    files_migrated_int = extract_files_migrated(report)
    file_mappings_list = extract_file_mappings(report)
    errors_list = extract_errors(report)

    cursorrules = project_root / ".cursorrules"
    if cursorrules.exists():
        dest = rules_dir / "main.cursorrules"
        try:
            _ = rules_dir.mkdir(parents=True, exist_ok=True)
            _ = shutil.copy2(cursorrules, dest)
            files_migrated_int += 1
            file_mappings_list.append(
                {"source": str(cursorrules), "destination": str(dest)}
            )
        except OSError as e:
            errors_list.append(f"Failed to migrate .cursorrules: {e}")

    update_migration_report(report, files_migrated_int, file_mappings_list, errors_list)


__all__ = [
    "migrate_cursorrules",
    "migrate_cursor_default",
    "migrate_doc_mcp_style",
    "migrate_plans",
    "migrate_scattered_files",
    "migrate_tradewing_style",
]
