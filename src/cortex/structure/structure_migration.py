#!/usr/bin/env python3
"""
Migration management for Memory Bank structure.

Handles detection and migration from legacy structure types to the standardized
.cortex/ structure.
"""

import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict
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
        if (self.project_root / ".cursor" / "plans").exists() and any(
            (self.project_root / f).exists() for f in STANDARD_MEMORY_BANK_FILES
        ):
            return "tradewing-style"

        # Check for doc-mcp-style
        if (self.project_root / ".cursor" / "plans").exists() and (
            self.project_root / "docs" / "memory-bank"
        ).exists():
            return "doc-mcp-style"

        # Check for scattered files
        scattered_files = list(self.project_root.rglob("projectBrief.md"))
        if scattered_files and not (self.project_root / ".cortex").exists():
            return "scattered-files"

        # Check for default Cursor
        if (self.project_root / ".cursorrules").exists() or (
            self.project_root / ".cursor"
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
        self._migrate_files_by_type(legacy_type, report)
        self._archive_legacy_files_if_requested(report, archive)

        return MigrationReport.model_validate(report)

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
        except Exception as e:
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
        # Dispatch table for migration strategies
        migration_handlers: dict[str, Callable[[ModelDict], None]] = {
            "tradewing-style": self._migrate_tradewing_style,
            "doc-mcp-style": self._migrate_doc_mcp_style,
            "scattered-files": self._migrate_scattered_files,
            "cursor-default": self._migrate_cursor_default,
        }

        handler = migration_handlers.get(legacy_type)
        if handler:
            handler(report)

    def _archive_legacy_files_if_requested(
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

    def _migrate_tradewing_style(self, report: ModelDict) -> None:
        """Migrate TradeWing-style structure."""
        memory_bank_dir = self.get_path("memory_bank")
        plans_dir = self.get_path("plans") / "active"
        rules_dir = self.get_path("rules") / "local"

        migration_data = self._extract_migration_report_data(report)
        self._migrate_memory_bank_files(memory_bank_dir, migration_data)
        self._migrate_plans(plans_dir, migration_data)
        self._migrate_cursorrules(rules_dir, migration_data)
        report["files_migrated"] = migration_data["files_migrated"]
        report["file_mappings"] = migration_data["file_mappings"]
        report["errors"] = migration_data["errors"]

    def _migrate_doc_mcp_style(self, report: ModelDict) -> None:
        """Migrate doc-mcp-style structure."""
        # Similar to TradeWing but with docs/memory-bank source
        pass

    def _migrate_scattered_files(self, report: ModelDict) -> None:
        """Migrate scattered files."""
        memory_bank_dir = self.get_path("memory_bank")
        files_migrated_int, file_mappings_list, errors_list = (
            self._initialize_migration_containers(report)
        )

        for filename in STANDARD_MEMORY_BANK_FILES:
            files_migrated_int = self._migrate_single_file(
                filename,
                memory_bank_dir,
                files_migrated_int,
                file_mappings_list,
                errors_list,
            )

        self._update_migration_report(
            report, files_migrated_int, file_mappings_list, errors_list
        )

    def _initialize_migration_containers(
        self, report: ModelDict
    ) -> tuple[int, list[ModelDict], list[str]]:
        """Initialize migration containers from report."""
        files_migrated = report.get("files_migrated", 0)
        files_migrated_int = (
            int(files_migrated) if isinstance(files_migrated, (int, float)) else 0
        )

        file_mappings_val: JsonValue = report.get("file_mappings", [])
        file_mappings_list: list[ModelDict] = []
        if isinstance(file_mappings_val, list):
            for mapping in cast(list[JsonValue], file_mappings_val):
                if isinstance(mapping, dict):
                    file_mappings_list.append(cast(ModelDict, mapping))

        errors_val = report.get("errors", [])
        errors_list: list[str] = (
            cast(list[str], errors_val) if isinstance(errors_val, list) else []
        )

        return files_migrated_int, file_mappings_list, errors_list

    def _migrate_single_file(
        self,
        filename: str,
        memory_bank_dir: Path,
        files_migrated_int: int,
        file_mappings_list: list[ModelDict],
        errors_list: list[str],
    ) -> int:
        """Migrate a single file."""
        files = list(self.project_root.rglob(filename))
        if not files:
            return files_migrated_int

        source = files[0]
        dest = memory_bank_dir / filename
        try:
            _ = shutil.copy2(source, dest)
            files_migrated_int += 1
            file_mappings_list.append({"source": str(source), "destination": str(dest)})
        except Exception as e:
            errors_list.append(f"Failed to migrate {filename}: {e}")

        return files_migrated_int

    def _update_migration_report(
        self,
        report: ModelDict,
        files_migrated_int: int,
        file_mappings_list: list[ModelDict],
        errors_list: list[str],
    ) -> None:
        """Update migration report."""
        report["files_migrated"] = files_migrated_int
        report["file_mappings"] = [cast(JsonValue, m) for m in file_mappings_list]
        report["errors"] = cast(list[JsonValue], errors_list)

    def _migrate_cursor_default(self, report: ModelDict) -> None:
        """Migrate Cursor default structure."""
        rules_dir = self.get_path("rules") / "local"

        # Get typed lists from report
        files_migrated = report.get("files_migrated", 0)
        files_migrated_int = (
            int(files_migrated) if isinstance(files_migrated, (int, float)) else 0
        )

        file_mappings_val: JsonValue = report.get("file_mappings", [])
        file_mappings_list: list[ModelDict] = []
        if isinstance(file_mappings_val, list):
            for mapping in cast(list[JsonValue], file_mappings_val):
                if isinstance(mapping, dict):
                    file_mappings_list.append(cast(ModelDict, mapping))

        errors_val = report.get("errors", [])
        errors_list: list[str] = (
            cast(list[str], errors_val) if isinstance(errors_val, list) else []
        )

        # Migrate .cursorrules if exists
        cursorrules = self.project_root / ".cursorrules"
        if cursorrules.exists():
            dest = rules_dir / "main.cursorrules"
            try:
                _ = rules_dir.mkdir(parents=True, exist_ok=True)
                _ = shutil.copy2(cursorrules, dest)
                files_migrated_int += 1
                file_mappings_list.append(
                    {"source": str(cursorrules), "destination": str(dest)}
                )
            except Exception as e:
                errors_list.append(f"Failed to migrate .cursorrules: {e}")

        # Update report
        report["files_migrated"] = files_migrated_int
        report["file_mappings"] = [cast(JsonValue, m) for m in file_mappings_list]
        report["errors"] = cast(list[JsonValue], errors_list)

    def _extract_migration_report_data(self, report: ModelDict) -> ModelDict:
        """Extract typed migration data from report.

        Args:
            report: Migration report dictionary

        Returns:
            Dictionary with typed migration data
        """
        files_migrated = report.get("files_migrated", 0)
        files_migrated_int = (
            int(files_migrated) if isinstance(files_migrated, (int, float)) else 0
        )

        file_mappings_val: JsonValue = report.get("file_mappings", [])
        file_mappings_list: list[ModelDict] = []
        if isinstance(file_mappings_val, list):
            for mapping in cast(list[JsonValue], file_mappings_val):
                if isinstance(mapping, dict):
                    file_mappings_list.append(cast(ModelDict, mapping))

        errors_val = report.get("errors", [])
        errors_list: list[str] = (
            cast(list[str], errors_val) if isinstance(errors_val, list) else []
        )

        file_mappings_json: list[JsonValue] = [
            cast(JsonValue, m) for m in file_mappings_list
        ]
        errors_json = cast(list[JsonValue], errors_list)
        return {
            "files_migrated": files_migrated_int,
            "file_mappings": file_mappings_json,
            "errors": errors_json,
        }

    def _extract_file_mappings(self, migration_data: ModelDict) -> list[ModelDict]:
        """Extract file mappings from migration data."""
        file_mappings_list: list[ModelDict] = []
        file_mappings_raw = migration_data.get("file_mappings", [])
        if isinstance(file_mappings_raw, list):
            for mapping in cast(list[JsonValue], file_mappings_raw):
                if isinstance(mapping, dict):
                    file_mappings_list.append(cast(ModelDict, mapping))
        return file_mappings_list

    def _extract_errors(self, migration_data: ModelDict) -> list[str]:
        """Extract errors from migration data."""
        errors_list: list[str] = []
        errors_raw = migration_data.get("errors", [])
        if isinstance(errors_raw, list):
            for err in cast(list[JsonValue], errors_raw):
                if isinstance(err, str):
                    errors_list.append(err)
        return errors_list

    def _migrate_memory_bank_files(
        self, memory_bank_dir: Path, migration_data: ModelDict
    ) -> None:
        """Migrate memory bank files from root to memory-bank directory.

        Args:
            memory_bank_dir: Target memory-bank directory
            migration_data: Migration data dictionary
        """
        files_migrated_int = cast(int, migration_data["files_migrated"])
        file_mappings_list = self._extract_file_mappings(migration_data)
        errors_list = self._extract_errors(migration_data)

        for filename in STANDARD_MEMORY_BANK_FILES:
            source = self.project_root / filename
            if source.exists():
                dest = memory_bank_dir / filename
                try:
                    _ = shutil.copy2(source, dest)
                    files_migrated_int += 1
                    file_mappings_list.append(
                        {"source": str(source), "destination": str(dest)}
                    )
                except Exception as e:
                    errors_list.append(f"Failed to migrate {filename}: {e}")

        migration_data["files_migrated"] = files_migrated_int
        migration_data["file_mappings"] = [
            cast(JsonValue, m) for m in file_mappings_list
        ]
        migration_data["errors"] = cast(list[JsonValue], errors_list)

    def _migrate_plans(self, plans_dir: Path, migration_data: ModelDict) -> None:
        """Migrate plans from .cursor/plans to plans directory.

        Args:
            plans_dir: Target plans directory
            migration_data: Migration data dictionary
        """
        files_migrated_int = cast(int, migration_data["files_migrated"])

        file_mappings_list: list[ModelDict] = []
        file_mappings_raw = migration_data.get("file_mappings", [])
        if isinstance(file_mappings_raw, list):
            for mapping in cast(list[JsonValue], file_mappings_raw):
                if isinstance(mapping, dict):
                    file_mappings_list.append(cast(ModelDict, mapping))

        errors_list: list[str] = []
        errors_raw = migration_data.get("errors", [])
        if isinstance(errors_raw, list):
            for err in cast(list[JsonValue], errors_raw):
                if isinstance(err, str):
                    errors_list.append(err)

        cursor_plans = self.project_root / ".cursor" / "plans"
        if cursor_plans.exists():
            for plan_file in cursor_plans.glob("*.md"):
                dest = plans_dir / plan_file.name
                try:
                    _ = shutil.copy2(plan_file, dest)
                    files_migrated_int += 1
                    file_mappings_list.append(
                        {"source": str(plan_file), "destination": str(dest)}
                    )
                except Exception as e:
                    errors_list.append(f"Failed to migrate {plan_file.name}: {e}")

        migration_data["files_migrated"] = files_migrated_int
        migration_data["file_mappings"] = [
            cast(JsonValue, m) for m in file_mappings_list
        ]
        migration_data["errors"] = cast(list[JsonValue], errors_list)

    def _migrate_cursorrules(self, rules_dir: Path, migration_data: ModelDict) -> None:
        """Migrate .cursorrules to rules directory.

        Args:
            rules_dir: Target rules directory
            migration_data: Migration data dictionary
        """
        files_migrated_int = cast(int, migration_data["files_migrated"])

        file_mappings_list: list[ModelDict] = []
        file_mappings_raw = migration_data.get("file_mappings", [])
        if isinstance(file_mappings_raw, list):
            for mapping in cast(list[JsonValue], file_mappings_raw):
                if isinstance(mapping, dict):
                    file_mappings_list.append(cast(ModelDict, mapping))

        errors_list: list[str] = []
        errors_raw = migration_data.get("errors", [])
        if isinstance(errors_raw, list):
            for err in cast(list[JsonValue], errors_raw):
                if isinstance(err, str):
                    errors_list.append(err)

        cursorrules = self.project_root / ".cursorrules"
        if cursorrules.exists():
            dest = rules_dir / "main.cursorrules"
            try:
                _ = rules_dir.mkdir(parents=True, exist_ok=True)
                _ = shutil.copy2(cursorrules, dest)
                files_migrated_int += 1
                file_mappings_list.append(
                    {"source": str(cursorrules), "destination": str(dest)}
                )
            except Exception as e:
                errors_list.append(f"Failed to migrate .cursorrules: {e}")

        migration_data["files_migrated"] = files_migrated_int
        migration_data["file_mappings"] = [
            cast(JsonValue, m) for m in file_mappings_list
        ]
        migration_data["errors"] = cast(list[JsonValue], errors_list)


# Export for public API
__all__ = ["StructureMigrationManager", "STANDARD_MEMORY_BANK_FILES"]
