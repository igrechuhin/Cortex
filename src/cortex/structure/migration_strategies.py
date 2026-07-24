#!/usr/bin/env python3
"""
Migration strategies for different legacy structure types.

Each function implements migration logic for a specific legacy structure
(doc-mcp-style, scattered-files).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cortex.core.models import ModelDict
from cortex.structure.migration_helpers import (
    extract_migration_report_data,
    initialize_migration_containers,
    migrate_memory_bank_files_from_source,
    migrate_single_file,
    update_migration_report,
)
from cortex.structure.structure_config import STANDARD_MEMORY_BANK_FILES


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
    source_memory_bank = project_root / "docs" / "memory-bank"

    migration_data = extract_migration_report_data(report)
    migrate_memory_bank_files_from_source(
        source_memory_bank, memory_bank_dir, migration_data
    )
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


__all__ = [
    "migrate_doc_mcp_style",
    "migrate_scattered_files",
]
