from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from cortex.core.models import ModelDict
from cortex.core.path_resolver import (
    CortexResourceType,
    get_cortex_path,
)
from cortex.structure.structure_migration import StructureMigrationManager


def test_migrate_cursor_default_when_cursorrules_exists_copies_to_rules_dir(
    tmp_path: Path,
) -> None:
    # Arrange
    cursorrules = tmp_path / ".cursorrules"
    _ = cursorrules.write_text("rules", encoding="utf-8")
    manager = StructureMigrationManager(tmp_path)

    report: dict[str, object] = {"files_migrated": 0, "file_mappings": [], "errors": []}

    # Act
    manager._migrate_cursor_default(report)  # type: ignore[attr-defined]  # noqa: SLF001 (unit-testing internal)

    # Assert
    assert report["files_migrated"] == 1
    mappings_raw = report.get("file_mappings")
    assert isinstance(mappings_raw, list)
    mappings: list[dict[str, object]] = cast(list[dict[str, object]], mappings_raw)
    assert len(mappings) == 1
    dest = (
        get_cortex_path(tmp_path, CortexResourceType.RULES)
        / "local"
        / "main.cursorrules"
    )
    assert dest.exists()


def test_create_backup_if_requested_when_mkdir_fails_records_error(
    tmp_path: Path,
) -> None:
    # Arrange
    manager = StructureMigrationManager(tmp_path)
    report: dict[str, object] = {"errors": "not a list"}  # exercise type-guard branch

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("nope")

    # Act
    with patch("pathlib.Path.mkdir", side_effect=_raise):
        manager._create_backup_if_requested(report, backup=True)  # type: ignore[attr-defined]  # noqa: SLF001

    # Assert
    errors_raw = report.get("errors")
    assert isinstance(errors_raw, list)
    errors: list[str] = cast(list[str], errors_raw)
    assert any("Failed to create backup" in str(e) for e in errors)


def test_migrate_memory_bank_files_copies_standard_files(tmp_path: Path) -> None:
    # Arrange
    source = tmp_path / "projectBrief.md"
    _ = source.write_text("# Brief", encoding="utf-8")
    manager = StructureMigrationManager(tmp_path)
    memory_bank_dir = manager.get_path("memory_bank")
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    migration_data: dict[str, object] = {
        "files_migrated": 0,
        "file_mappings": [],
        "errors": [],
    }

    # Act
    manager._migrate_memory_bank_files(  # type: ignore[attr-defined]  # noqa: SLF001
        memory_bank_dir,
        cast(ModelDict, migration_data),
    )

    # Assert
    assert (memory_bank_dir / "projectBrief.md").exists()
    assert migration_data["files_migrated"] == 1


def test_migrate_plans_copies_cursor_plans(tmp_path: Path) -> None:
    # Arrange: use a source dir under tmp_path (sandbox may block .cursor)
    source_plans = tmp_path / "source_plans"
    source_plans.mkdir(parents=True, exist_ok=True)
    _ = (source_plans / "plan.md").write_text("# Plan", encoding="utf-8")
    manager = StructureMigrationManager(tmp_path)
    plans_dir = manager.get_path("plans") / "active"
    plans_dir.mkdir(parents=True, exist_ok=True)
    migration_data: dict[str, object] = {
        "files_migrated": 0,
        "file_mappings": [],
        "errors": [],
    }
    with patch(
        "cortex.structure.migration_strategies.get_cursor_path",
        return_value=source_plans,
    ):
        manager.migrate_plans(plans_dir, cast(ModelDict, migration_data))
    assert (plans_dir / "plan.md").exists()
    assert migration_data["files_migrated"] == 1


def test_migrate_cursorrules_copies_rules_file(tmp_path: Path) -> None:
    # Arrange
    cursorrules = tmp_path / ".cursorrules"
    _ = cursorrules.write_text("rules", encoding="utf-8")
    manager = StructureMigrationManager(tmp_path)
    rules_dir = manager.get_path("rules") / "local"
    migration_data: dict[str, object] = {
        "files_migrated": 0,
        "file_mappings": [],
        "errors": [],
    }

    # Act
    manager.migrate_cursorrules(rules_dir, cast(ModelDict, migration_data))

    # Assert
    assert (rules_dir / "main.cursorrules").exists()
    assert migration_data["files_migrated"] == 1


def test_detect_legacy_structure_when_tradewing_style_detected(tmp_path: Path) -> None:
    # Arrange: .cursor/plans may not be creatable in sandbox, so mock its existence
    _ = (tmp_path / "projectBrief.md").write_text("# Brief", encoding="utf-8")
    manager = StructureMigrationManager(tmp_path)
    with patch(
        "cortex.structure.structure_migration.get_cursor_path",
        return_value=MagicMock(exists=MagicMock(return_value=True)),
    ):
        legacy = manager.detect_legacy_structure()
    assert legacy == "tradewing-style"


def test_detect_legacy_structure_when_doc_mcp_style_detected(tmp_path: Path) -> None:
    # Arrange: docs/memory-bank; .cursor/plans existence mocked (sandbox-safe)
    (tmp_path / "docs" / "memory-bank").mkdir(parents=True, exist_ok=True)
    manager = StructureMigrationManager(tmp_path)
    with patch(
        "cortex.structure.structure_migration.get_cursor_path",
        return_value=MagicMock(exists=MagicMock(return_value=True)),
    ):
        legacy = manager.detect_legacy_structure()
    assert legacy == "doc-mcp-style"


def test_migrate_doc_mcp_style_copies_from_docs_memory_bank(tmp_path: Path) -> None:
    """Doc-mcp-style migration copies files from docs/memory-bank to .cortex memory-bank."""
    # Arrange
    docs_mb = tmp_path / "docs" / "memory-bank"
    docs_mb.mkdir(parents=True, exist_ok=True)
    _ = (docs_mb / "projectBrief.md").write_text("# Brief", encoding="utf-8")
    manager = StructureMigrationManager(tmp_path)
    memory_bank_dir = manager.get_path("memory_bank")
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "files_migrated": 0,
        "file_mappings": [],
        "errors": [],
    }

    # Act
    manager._migrate_doc_mcp_style(cast(ModelDict, report))  # type: ignore[attr-defined]  # noqa: SLF001

    # Assert
    assert (memory_bank_dir / "projectBrief.md").exists()
    assert report["files_migrated"] == 1


def test_detect_legacy_structure_when_scattered_files_detected(tmp_path: Path) -> None:
    # Arrange
    scattered_dir = tmp_path / "somewhere"
    scattered_dir.mkdir(parents=True, exist_ok=True)
    _ = (scattered_dir / "projectBrief.md").write_text("# Brief", encoding="utf-8")
    manager = StructureMigrationManager(tmp_path)

    # Act
    legacy = manager.detect_legacy_structure()

    # Assert
    assert legacy == "scattered-files"


def test_detect_legacy_structure_when_cursor_default_detected(tmp_path: Path) -> None:
    # Arrange: .cursor existence mocked (sandbox may block creating .cursor)
    manager = StructureMigrationManager(tmp_path)
    with patch(
        "cortex.structure.structure_migration.get_cursor_path",
        return_value=MagicMock(exists=MagicMock(return_value=True)),
    ):
        legacy = manager.detect_legacy_structure()
    assert legacy == "cursor-default"


def test_detect_legacy_structure_when_none_detected_returns_none(
    tmp_path: Path,
) -> None:
    # Arrange
    get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR).mkdir(
        parents=True, exist_ok=True
    )
    manager = StructureMigrationManager(tmp_path)

    # Act
    legacy = manager.detect_legacy_structure()

    # Assert
    assert legacy is None


def test_archive_legacy_files_if_requested_sets_archive_location(
    tmp_path: Path,
) -> None:
    # Arrange
    manager = StructureMigrationManager(tmp_path)
    report: dict[str, object] = {"files_migrated": 1}

    # Act
    manager.archive_legacy_files_if_requested(cast(ModelDict, report), archive=True)

    # Assert
    archive_location = report.get("archive_location")
    assert isinstance(archive_location, str)
    assert "legacy-" in archive_location


@pytest.mark.asyncio
async def test_migrate_legacy_structure_detects_languages_and_scaffolds_swift_scripts(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "Package.swift").write_text("// swiftpm", encoding="utf-8")
    templates_dir = tmp_path / ".cortex" / "synapse" / "rules" / "_templates" / "swift"
    templates_dir.mkdir(parents=True, exist_ok=True)
    template_rule = templates_dir / "swift-coding-standards.mdc"
    _ = template_rule.write_text("# Swift template", encoding="utf-8")
    scattered_dir = tmp_path / "somewhere"
    scattered_dir.mkdir(parents=True, exist_ok=True)
    _ = (scattered_dir / "projectBrief.md").write_text("# Brief", encoding="utf-8")

    manager = StructureMigrationManager(tmp_path)

    report = await manager.migrate_legacy_structure(
        legacy_type="scattered-files", backup=False, archive=False
    )

    assert report.success is True
    assert report.detected_languages == ["swift"]
    assert report.scaffolded_languages == ["swift"]
    scaffolded_rule = (
        tmp_path
        / ".cortex"
        / "synapse"
        / "rules"
        / "swift"
        / "swift-coding-standards.mdc"
    )
    assert scaffolded_rule.exists()
    assert str(scaffolded_rule) in report.rules_scaffolded

    quality_script = (
        tmp_path / ".cortex" / "synapse" / "scripts" / "swift" / "run_quality_check.sh"
    )
    assert quality_script.exists()
    content = quality_script.read_text(encoding="utf-8")
    assert "swift build" in content
    assert "swift test" in content
    assert str(quality_script) in report.scripts_scaffolded


@pytest.mark.asyncio
async def test_migrate_legacy_structure_marks_typescript_as_scaffolded_from_rules(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    templates_dir = (
        tmp_path / ".cortex" / "synapse" / "rules" / "_templates" / "typescript"
    )
    templates_dir.mkdir(parents=True, exist_ok=True)
    template_rule = templates_dir / "typescript-coding-standards.mdc"
    _ = template_rule.write_text("# TypeScript template", encoding="utf-8")
    scattered_dir = tmp_path / "somewhere"
    scattered_dir.mkdir(parents=True, exist_ok=True)
    _ = (scattered_dir / "projectBrief.md").write_text("# Brief", encoding="utf-8")

    manager = StructureMigrationManager(tmp_path)

    report = await manager.migrate_legacy_structure(
        legacy_type="scattered-files", backup=False, archive=False
    )

    assert report.success is True
    assert report.detected_languages == ["typescript"]
    assert report.scaffolded_languages == ["typescript"]
    scaffolded_rule = (
        tmp_path
        / ".cortex"
        / "synapse"
        / "rules"
        / "typescript"
        / "typescript-coding-standards.mdc"
    )
    assert scaffolded_rule.exists()
    assert str(scaffolded_rule) in report.rules_scaffolded
    assert report.scripts_scaffolded == []
