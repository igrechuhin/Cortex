#!/usr/bin/env python3
"""
Helper functions for migration report data extraction and file operations.

Provides reusable utilities for extracting typed data from migration report
dictionaries and performing file copy operations during migrations.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict
from cortex.structure.structure_config import STANDARD_MEMORY_BANK_FILES


def extract_files_migrated(report: ModelDict) -> int:
    """Extract files_migrated count from report as int.

    Args:
        report: Migration report dictionary

    Returns:
        Number of files migrated
    """
    files_migrated = report.get("files_migrated", 0)
    return int(files_migrated) if isinstance(files_migrated, (int, float)) else 0


def extract_file_mappings(data: ModelDict) -> list[ModelDict]:
    """Extract file mappings list from migration data.

    Args:
        data: Migration data dictionary

    Returns:
        List of file mapping dictionaries
    """
    file_mappings_list: list[ModelDict] = []
    file_mappings_raw = data.get("file_mappings", [])
    if isinstance(file_mappings_raw, list):
        for mapping in cast(list[JsonValue], file_mappings_raw):
            if isinstance(mapping, dict):
                file_mappings_list.append(cast(ModelDict, mapping))
    return file_mappings_list


def extract_errors(data: ModelDict) -> list[str]:
    """Extract errors list from migration data.

    Args:
        data: Migration data dictionary

    Returns:
        List of error strings
    """
    errors_list: list[str] = []
    errors_raw = data.get("errors", [])
    if isinstance(errors_raw, list):
        for err in cast(list[JsonValue], errors_raw):
            if isinstance(err, str):
                errors_list.append(err)
    return errors_list


def extract_migration_report_data(report: ModelDict) -> ModelDict:
    """Extract typed migration data from report.

    Args:
        report: Migration report dictionary

    Returns:
        Dictionary with typed migration data
    """
    files_migrated_int = extract_files_migrated(report)
    file_mappings_list = extract_file_mappings(report)
    errors_list = extract_errors(report)

    file_mappings_json: list[JsonValue] = [
        cast(JsonValue, m) for m in file_mappings_list
    ]
    errors_json = cast(list[JsonValue], errors_list)
    return {
        "files_migrated": files_migrated_int,
        "file_mappings": file_mappings_json,
        "errors": errors_json,
    }


def initialize_migration_containers(
    report: ModelDict,
) -> tuple[int, list[ModelDict], list[str]]:
    """Initialize migration containers from report.

    Args:
        report: Migration report dictionary

    Returns:
        Tuple of (files_migrated count, file_mappings list, errors list)
    """
    return (
        extract_files_migrated(report),
        extract_file_mappings(report),
        extract_errors(report),
    )


def update_migration_report(
    report: ModelDict,
    files_migrated_int: int,
    file_mappings_list: list[ModelDict],
    errors_list: list[str],
) -> None:
    """Update migration report with typed data.

    Args:
        report: Migration report dictionary to update
        files_migrated_int: Number of files migrated
        file_mappings_list: List of file mapping dictionaries
        errors_list: List of error strings
    """
    report["files_migrated"] = files_migrated_int
    report["file_mappings"] = [cast(JsonValue, m) for m in file_mappings_list]
    report["errors"] = cast(list[JsonValue], errors_list)


def update_migration_data(
    migration_data: ModelDict,
    files_migrated_int: int,
    file_mappings_list: list[ModelDict],
    errors_list: list[str],
) -> None:
    """Update migration data dictionary with typed values.

    Args:
        migration_data: Migration data dictionary to update
        files_migrated_int: Number of files migrated
        file_mappings_list: List of file mapping dictionaries
        errors_list: List of error strings
    """
    migration_data["files_migrated"] = files_migrated_int
    migration_data["file_mappings"] = [cast(JsonValue, m) for m in file_mappings_list]
    migration_data["errors"] = cast(list[JsonValue], errors_list)


def migrate_memory_bank_files_from_source(
    source_dir: Path,
    memory_bank_dir: Path,
    migration_data: ModelDict,
) -> None:
    """Migrate memory bank files from a source directory.

    Args:
        source_dir: Source directory containing memory bank files
        memory_bank_dir: Target memory-bank directory
        migration_data: Migration data dictionary to update
    """
    files_migrated_int = cast(int, migration_data["files_migrated"])
    file_mappings_list = extract_file_mappings(migration_data)
    errors_list = extract_errors(migration_data)

    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    for filename in STANDARD_MEMORY_BANK_FILES:
        source = source_dir / filename
        if source.exists():
            dest = memory_bank_dir / filename
            try:
                _ = shutil.copy2(source, dest)
                files_migrated_int += 1
                file_mappings_list.append(
                    {"source": str(source), "destination": str(dest)}
                )
            except OSError as e:
                errors_list.append(f"Failed to migrate {filename}: {e}")

    update_migration_data(
        migration_data, files_migrated_int, file_mappings_list, errors_list
    )


def migrate_single_file(
    project_root: Path,
    filename: str,
    memory_bank_dir: Path,
    files_migrated_int: int,
    file_mappings_list: list[ModelDict],
    errors_list: list[str],
) -> int:
    """Migrate a single file by searching project root.

    Args:
        project_root: Project root directory
        filename: Name of file to find and migrate
        memory_bank_dir: Target memory-bank directory
        files_migrated_int: Current count of migrated files
        file_mappings_list: List of file mappings to update
        errors_list: List of errors to update

    Returns:
        Updated files_migrated count
    """
    files = list(project_root.rglob(filename))
    if not files:
        return files_migrated_int

    source = files[0]
    dest = memory_bank_dir / filename
    try:
        memory_bank_dir.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(source, dest)
        files_migrated_int += 1
        file_mappings_list.append({"source": str(source), "destination": str(dest)})
    except OSError as e:
        errors_list.append(f"Failed to migrate {filename}: {e}")

    return files_migrated_int


__all__ = [
    "extract_errors",
    "extract_file_mappings",
    "extract_files_migrated",
    "extract_migration_report_data",
    "initialize_migration_containers",
    "migrate_memory_bank_files_from_source",
    "migrate_single_file",
    "update_migration_data",
    "update_migration_report",
]
