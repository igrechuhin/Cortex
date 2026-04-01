#!/usr/bin/env python3
"""
Migration management for Memory Bank structure.

Handles detection and migration from legacy structure types to the standardized
.cortex/ structure.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict
from cortex.core.path_resolver import (
    CortexResourceType,
    CursorResourceType,
    get_cortex_path,
    get_cursor_path,
)
from cortex.structure.language_rules_scaffolding import (
    scaffold_language_rules_from_templates,
)
from cortex.structure.language_scripts_scaffolding import (
    build_missing_native_script_warnings,
    scaffold_language_scripts,
)
from cortex.structure.migration_strategies import (
    migrate_cursor_default,
    migrate_cursorrules,
    migrate_doc_mcp_style,
    migrate_plans,
    migrate_scattered_files,
    migrate_tradewing_style,
)
from cortex.structure.models import MigrationReport
from cortex.structure.structure_config import (
    STANDARD_MEMORY_BANK_FILES,
    StructureConfig,
)


class StructureMigrationManager:
    """Manages migration from legacy structures to standardized structure."""

    def __init__(self, project_root: Path):
        """Initialize migration manager.

        Args:
            project_root: Root directory of the project
        """
        self.config = StructureConfig(project_root)

    @property
    def project_root(self) -> Path:
        """Get project root path."""
        return self.config.project_root

    def get_path(self, component: str) -> Path:
        """Get path for a structure component.

        Args:
            component: Component name

        Returns:
            Resolved path
        """
        return self.config.get_path(component)

    def detect_legacy_structure(self) -> str | None:
        """Detect legacy structure type.

        Returns:
            Structure type or None if no legacy structure detected
        """
        # Check for TradeWing-style
        cursor_plans_dir = get_cursor_path(self.project_root, CursorResourceType.PLANS)
        if cursor_plans_dir.exists() and any(
            (self.project_root / f).exists() for f in STANDARD_MEMORY_BANK_FILES
        ):
            return "tradewing-style"

        # Check for doc-mcp-style
        if (
            cursor_plans_dir.exists()
            and (self.project_root / "docs" / "memory-bank").exists()
        ):
            return "doc-mcp-style"

        # Check for scattered files (only when .cursor/plans not present,
        # so tradewing-style and doc-mcp-style take precedence)
        from cortex.core.constants import MemoryBankFile

        scattered_files = list(self.project_root.rglob(MemoryBankFile.PROJECT_BRIEF))
        if (
            scattered_files
            and not get_cortex_path(
                self.project_root, CortexResourceType.CORTEX_DIR
            ).exists()
            and not cursor_plans_dir.exists()
        ):
            return "scattered-files"

        # Check for default Cursor
        if (self.project_root / ".cursorrules").exists() or get_cursor_path(
            self.project_root, CursorResourceType.CURSOR_DIR
        ).exists():
            return "cursor-default"

        return None

    async def migrate_legacy_structure(
        self,
        legacy_type: str | None = None,
        backup: bool = True,
        archive: bool = True,
    ) -> MigrationReport:
        """Migrate from legacy structure to standardized structure.

        Args:
            legacy_type: Type of legacy structure (auto-detected if None)
            backup: Whether to create a backup
            archive: Whether to archive legacy files

        Returns:
            Migration report with file mappings and actions
        """
        legacy_type = self._detect_or_validate_legacy_type(legacy_type)
        if legacy_type is None:
            return MigrationReport(
                success=False,
                legacy_type=None,
                files_migrated=0,
                file_mappings=[],
                backup_location=None,
                archive_location=None,
                structure_creation=None,
                errors=[],
                error="No legacy structure detected",
            )

        report: ModelDict = self._build_initial_report(legacy_type)
        self._create_backup_if_requested(report, backup)
        await self._create_new_structure(report)
        self._detect_languages_and_scaffold_scripts(report)
        self._migrate_files_by_type(legacy_type, report)
        self.archive_legacy_files_if_requested(report, archive)

        return MigrationReport.model_validate(report)

    def _detect_languages_and_scaffold_scripts(self, report: ModelDict) -> None:
        from cortex.setup.migration_language_detection import (
            detect_languages_for_migration,
        )

        detected_languages = detect_languages_for_migration(self.project_root)
        report["detected_languages"] = _to_json_list(detected_languages)

        rules_scaffolded = scaffold_language_rules_from_templates(
            self.project_root, detected_languages
        )
        report["rules_scaffolded"] = _to_json_list(rules_scaffolded)

        scripts_scaffolded = scaffold_language_scripts(
            self.project_root, detected_languages
        )
        report["scripts_scaffolded"] = _to_json_list(scripts_scaffolded)
        report["scaffolding_warnings"] = _to_json_list(
            build_missing_native_script_warnings(self.project_root, detected_languages)
        )

        scaffolded_by_language = _collect_scaffolded_languages(
            detected_languages,
            rules_scaffolded,
            scripts_scaffolded,
        )
        report["scaffolded_languages"] = _to_json_list(scaffolded_by_language)

    def _detect_or_validate_legacy_type(self, legacy_type: str | None) -> str | None:
        """Detect or validate legacy structure type.

        Args:
            legacy_type: Optional legacy type to validate

        Returns:
            Legacy type string or None if not detected
        """
        if legacy_type is None:
            return self.detect_legacy_structure()
        return legacy_type

    def _build_initial_report(self, legacy_type: str) -> ModelDict:
        """Build initial migration report.

        Args:
            legacy_type: Detected legacy type

        Returns:
            Initial report dictionary
        """
        return {
            "success": True,
            "legacy_type": legacy_type,
            "files_migrated": 0,
            "file_mappings": [],
            "backup_location": None,
            "archive_location": None,
            "errors": [],
        }

    def _create_backup_if_requested(self, report: ModelDict, backup: bool) -> None:
        """Create backup if requested.

        Args:
            report: Migration report to update
            backup: Whether to create backup
        """
        if not backup:
            return

        backup_dir = (
            self.project_root
            / f".cortex-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            report["backup_location"] = str(backup_dir)
        except OSError as e:
            errors_val = report.get("errors", [])
            errors_list: list[str] = (
                cast(list[str], errors_val) if isinstance(errors_val, list) else []
            )
            errors_list.append(f"Failed to create backup: {e}")
            report["errors"] = cast(list[JsonValue], errors_list)

    async def _create_new_structure(self, report: ModelDict) -> None:
        """Create new standardized structure.

        Args:
            report: Migration report to update
        """
        from cortex.structure.structure_lifecycle import (
            StructureLifecycleManager,
        )

        lifecycle_manager = StructureLifecycleManager(self.project_root)
        structure_report = await lifecycle_manager.create_structure()
        report["structure_creation"] = structure_report.model_dump()

    def _migrate_files_by_type(self, legacy_type: str, report: ModelDict) -> None:
        """Migrate files based on legacy type.

        Args:
            legacy_type: Type of legacy structure
            report: Migration report to update
        """
        migration_handlers: dict[
            str, Callable[[Path, Callable[[str], Path], ModelDict], None]
        ] = {
            "tradewing-style": migrate_tradewing_style,
            "doc-mcp-style": migrate_doc_mcp_style,
            "scattered-files": migrate_scattered_files,
            "cursor-default": migrate_cursor_default,
        }

        handler = migration_handlers.get(legacy_type)
        if handler:
            handler(self.project_root, self.get_path, report)

    def archive_legacy_files_if_requested(
        self, report: ModelDict, archive: bool
    ) -> None:
        """Archive legacy files if requested.

        Args:
            report: Migration report to update
            archive: Whether to archive files
        """
        if not archive:
            return

        files_migrated = report.get("files_migrated", 0)
        files_migrated_int = (
            int(files_migrated) if isinstance(files_migrated, (int, float)) else 0
        )
        if files_migrated_int > 0:
            archive_dir = (
                self.get_path("archived")
                / f"legacy-{datetime.now().strftime('%Y%m%d')}"
            )
            report["archive_location"] = str(archive_dir)

    # Backwards-compatible delegate methods for internal API

    def _migrate_cursor_default(self, report: ModelDict) -> None:
        """Migrate Cursor default structure (delegate)."""
        migrate_cursor_default(self.project_root, self.get_path, report)

    def _migrate_doc_mcp_style(self, report: ModelDict) -> None:
        """Migrate doc-mcp-style structure (delegate)."""
        migrate_doc_mcp_style(self.project_root, self.get_path, report)

    def _migrate_tradewing_style(self, report: ModelDict) -> None:
        """Migrate TradeWing-style structure (delegate)."""
        migrate_tradewing_style(self.project_root, self.get_path, report)

    def _migrate_scattered_files(self, report: ModelDict) -> None:
        """Migrate scattered files (delegate)."""
        migrate_scattered_files(self.project_root, self.get_path, report)

    def _migrate_memory_bank_files(
        self, memory_bank_dir: Path, migration_data: ModelDict
    ) -> None:
        """Migrate memory bank files from root (delegate)."""
        from cortex.structure.migration_helpers import (
            migrate_memory_bank_files_from_source,
        )

        migrate_memory_bank_files_from_source(
            self.project_root, memory_bank_dir, migration_data
        )

    def migrate_plans(self, plans_dir: Path, migration_data: ModelDict) -> None:
        """Migrate plans from .cursor/plans to plans directory.

        Args:
            plans_dir: Target plans directory
            migration_data: Migration data dictionary
        """
        migrate_plans(self.project_root, plans_dir, migration_data)

    def migrate_cursorrules(self, rules_dir: Path, migration_data: ModelDict) -> None:
        """Migrate .cursorrules to rules directory.

        Args:
            rules_dir: Target rules directory
            migration_data: Migration data dictionary
        """
        migrate_cursorrules(self.project_root, rules_dir, migration_data)


# Export for public API
__all__ = ["StructureMigrationManager", "STANDARD_MEMORY_BANK_FILES"]


def _collect_scaffolded_languages(
    detected_languages: list[str],
    rules_scaffolded: list[str],
    scripts_scaffolded: list[str],
) -> list[str]:
    scaffolded_paths = rules_scaffolded + scripts_scaffolded
    scaffolded_languages: list[str] = []

    for language in detected_languages:
        language_marker = f"/{language}/"
        if any(language_marker in path for path in scaffolded_paths):
            scaffolded_languages.append(language)

    return scaffolded_languages


def _to_json_list(values: list[str]) -> list[JsonValue]:
    json_values: list[JsonValue] = []
    for value in values:
        json_values.append(value)
    return json_values
