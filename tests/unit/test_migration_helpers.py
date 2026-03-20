"""Unit tests for migration_helpers (extract_*, update_*, migrate_* functions)."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import patch

from cortex.core.models import ModelDict
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


class TestExtractFilesMigrated:
    """Tests for extract_files_migrated."""

    def test_returns_int_when_present(self) -> None:
        report: ModelDict = {"files_migrated": 3, "file_mappings": [], "errors": []}
        assert extract_files_migrated(report) == 3

    def test_returns_zero_when_missing(self) -> None:
        report: ModelDict = {}
        assert extract_files_migrated(report) == 0

    def test_coerces_float_to_int(self) -> None:
        report: ModelDict = {"files_migrated": 2.0}
        assert extract_files_migrated(report) == 2

    def test_invalid_type_returns_zero(self) -> None:
        report: ModelDict = {"files_migrated": "two"}
        assert extract_files_migrated(report) == 0


class TestExtractFileMappings:
    """Tests for extract_file_mappings."""

    def test_returns_list_of_dicts(self) -> None:
        data: ModelDict = {
            "file_mappings": [
                {"source": "/a", "destination": "/b"},
                {"source": "/c", "destination": "/d"},
            ]
        }
        result = extract_file_mappings(data)
        assert len(result) == 2
        assert result[0]["source"] == "/a"
        assert result[1]["destination"] == "/d"

    def test_returns_empty_list_when_missing(self) -> None:
        data: ModelDict = {}
        assert extract_file_mappings(data) == []

    def test_skips_non_dict_items(self) -> None:
        data: ModelDict = {"file_mappings": [{"s": "a"}, "not a dict", 1]}
        result = extract_file_mappings(data)
        assert len(result) == 1
        assert result[0]["s"] == "a"


class TestExtractErrors:
    """Tests for extract_errors."""

    def test_returns_list_of_strings(self) -> None:
        data: ModelDict = {"errors": ["e1", "e2"]}
        assert extract_errors(data) == ["e1", "e2"]

    def test_returns_empty_list_when_missing(self) -> None:
        data: ModelDict = {}
        assert extract_errors(data) == []

    def test_skips_non_string_items(self) -> None:
        data: ModelDict = {"errors": ["ok", 42, "also_ok"]}
        result = extract_errors(data)
        assert result == ["ok", "also_ok"]


class TestExtractMigrationReportData:
    """Tests for extract_migration_report_data."""

    def test_returns_typed_dict_with_all_keys(self) -> None:
        report: ModelDict = {
            "files_migrated": 1,
            "file_mappings": [{"source": "a", "destination": "b"}],
            "errors": ["err"],
        }
        result = extract_migration_report_data(report)
        assert result["files_migrated"] == 1
        assert len(cast(list[ModelDict], result["file_mappings"])) == 1
        assert cast(list[str], result["errors"]) == ["err"]


class TestInitializeMigrationContainers:
    """Tests for initialize_migration_containers."""

    def test_returns_tuple_matching_extractors(self) -> None:
        report: ModelDict = {
            "files_migrated": 2,
            "file_mappings": [{"source": "x", "destination": "y"}],
            "errors": ["e"],
        }
        files_migrated, file_mappings, errors = initialize_migration_containers(report)
        assert files_migrated == 2
        assert len(file_mappings) == 1
        assert errors == ["e"]


class TestUpdateMigrationReport:
    """Tests for update_migration_report."""

    def test_updates_report_in_place(self) -> None:
        report: ModelDict = {"files_migrated": 0, "file_mappings": [], "errors": []}
        update_migration_report(
            report,
            files_migrated_int=2,
            file_mappings_list=[{"source": "a", "destination": "b"}],
            errors_list=["err"],
        )
        assert report["files_migrated"] == 2
        mappings: list[ModelDict] = cast(list[ModelDict], report["file_mappings"])
        assert len(mappings) == 1
        assert mappings[0]["source"] == "a"
        assert cast(list[str], report["errors"]) == ["err"]


class TestUpdateMigrationData:
    """Tests for update_migration_data."""

    def test_updates_data_in_place(self) -> None:
        migration_data: ModelDict = {
            "files_migrated": 0,
            "file_mappings": [],
            "errors": [],
        }
        update_migration_data(
            migration_data,
            files_migrated_int=1,
            file_mappings_list=[{"source": "s", "destination": "d"}],
            errors_list=[],
        )
        assert migration_data["files_migrated"] == 1
        mappings: list[ModelDict] = cast(
            list[ModelDict], migration_data["file_mappings"]
        )
        assert len(mappings) == 1
        assert mappings[0]["destination"] == "d"


class TestMigrateSingleFile:
    """Tests for migrate_single_file edge cases."""

    def test_no_files_found_returns_unchanged_count(self, tmp_path: Path) -> None:
        """When rglob finds no files, count is unchanged."""
        memory_bank_dir = tmp_path / "memory-bank"
        file_mappings: list[ModelDict] = []
        errors: list[str] = []

        result = migrate_single_file(
            tmp_path, "nonexistent.md", memory_bank_dir, 0, file_mappings, errors
        )

        assert result == 0
        assert file_mappings == []
        assert errors == []

    def test_successful_migration_increments_count(self, tmp_path: Path) -> None:
        """When file exists, it is copied and count increments."""
        source = tmp_path / "sub" / "target.md"
        source.parent.mkdir(parents=True)
        _ = source.write_text("content", encoding="utf-8")
        memory_bank_dir = tmp_path / "memory-bank"
        file_mappings: list[ModelDict] = []
        errors: list[str] = []

        result = migrate_single_file(
            tmp_path, "target.md", memory_bank_dir, 0, file_mappings, errors
        )

        assert result == 1
        assert len(file_mappings) == 1
        assert (memory_bank_dir / "target.md").exists()
        assert errors == []

    def test_permission_error_records_error(self, tmp_path: Path) -> None:
        """OSError during copy is caught and recorded in errors list."""
        source = tmp_path / "file.md"
        _ = source.write_text("content", encoding="utf-8")
        memory_bank_dir = tmp_path / "memory-bank"
        file_mappings: list[ModelDict] = []
        errors: list[str] = []

        with patch("cortex.structure.migration_helpers.shutil.copy2") as mock_copy:
            mock_copy.side_effect = PermissionError("Permission denied")
            result = migrate_single_file(
                tmp_path, "file.md", memory_bank_dir, 0, file_mappings, errors
            )

        assert result == 0
        assert len(errors) == 1
        assert "Permission denied" in errors[0]
        assert file_mappings == []


class TestMigrateMemoryBankFilesFromSource:
    """Tests for migrate_memory_bank_files_from_source edge cases."""

    def test_no_standard_files_in_source_leaves_data_unchanged(
        self, tmp_path: Path
    ) -> None:
        """When source dir has no standard files, nothing is migrated."""
        source_dir = tmp_path / "empty-source"
        source_dir.mkdir()
        memory_bank_dir = tmp_path / "memory-bank"
        migration_data: ModelDict = {
            "files_migrated": 0,
            "file_mappings": [],
            "errors": [],
        }

        migrate_memory_bank_files_from_source(
            source_dir, memory_bank_dir, migration_data
        )

        assert migration_data["files_migrated"] == 0
        assert cast(list[ModelDict], migration_data["file_mappings"]) == []

    def test_permission_error_records_error(self, tmp_path: Path) -> None:
        """OSError during copy is caught and recorded."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        _ = (source_dir / "projectBrief.md").write_text("brief", encoding="utf-8")
        memory_bank_dir = tmp_path / "memory-bank"
        migration_data: ModelDict = {
            "files_migrated": 0,
            "file_mappings": [],
            "errors": [],
        }

        with patch("cortex.structure.migration_helpers.shutil.copy2") as mock_copy:
            mock_copy.side_effect = PermissionError("read-only filesystem")
            migrate_memory_bank_files_from_source(
                source_dir, memory_bank_dir, migration_data
            )

        assert migration_data["files_migrated"] == 0
        errors = cast(list[str], migration_data["errors"])
        assert len(errors) == 1
        assert "read-only filesystem" in errors[0]


class TestExtractMigrationReportDataEdgeCases:
    """Edge case tests for extract_migration_report_data."""

    def test_empty_report_returns_defaults(self) -> None:
        """Empty report produces zero/empty defaults."""
        report: ModelDict = {}
        result = extract_migration_report_data(report)
        assert result["files_migrated"] == 0
        assert cast(list[ModelDict], result["file_mappings"]) == []
        assert cast(list[str], result["errors"]) == []

    def test_corrupted_report_with_wrong_types(self) -> None:
        """Non-list file_mappings and errors are safely handled."""
        report: ModelDict = {
            "files_migrated": "not_a_number",
            "file_mappings": "not_a_list",
            "errors": 42,
        }
        result = extract_migration_report_data(report)
        assert result["files_migrated"] == 0
        assert cast(list[ModelDict], result["file_mappings"]) == []
        assert cast(list[str], result["errors"]) == []
