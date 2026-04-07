"""Tests for operations-log formatting helpers."""

from datetime import datetime
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.tools.plans.operations_log import (
    OperationsLogType,
    append_operations_log_entry,
    format_operations_log_entry,
)


def test_memory_bank_file_enum_includes_log_md() -> None:
    """MemoryBankFile includes log.md for manage/read tooling."""
    assert MemoryBankFile.LOG == "log.md"


def test_format_operations_log_entry_with_summary() -> None:
    """Formatter builds parseable heading plus summary line."""
    entry = format_operations_log_entry(
        operation_type=OperationsLogType.PLAN,
        title="Create roadmap plan",
        summary="Added plan with implementation steps.",
        timestamp=datetime(2026, 4, 7, 12, 34),
    )
    expected_entry = (
        "## [2026-04-07T12:34] plan | Create roadmap plan\n"
        + "\nAdded plan with implementation steps.\n\n"
    )
    assert entry == expected_entry


def test_format_operations_log_entry_trims_optional_summary() -> None:
    """Formatter emits heading-only entry when summary is blank."""
    entry = format_operations_log_entry(
        operation_type=OperationsLogType.ANALYZE,
        title="  Session analysis  ",
        summary="   ",
        timestamp=datetime(2026, 4, 7, 6, 5),
    )
    assert entry == "## [2026-04-07T06:05] analyze | Session analysis\n\n"


def test_append_operations_log_entry_creates_file_with_header(tmp_path: Path) -> None:
    """Append helper creates canonical log file and returns heading line."""
    log_path = tmp_path / "log.md"
    inserted_line = append_operations_log_entry(
        log_path=log_path,
        operation_type=OperationsLogType.FIX,
        title="Repair docs gate",
        summary="Resolved timestamp mismatch.",
        timestamp=datetime(2026, 4, 7, 14, 1),
    )
    assert inserted_line == 3
    expected = (
        "# Cortex Operations Log\n\n"
        + "## [2026-04-07T14:01] fix | Repair docs gate\n"
        + "\nResolved timestamp mismatch.\n"
    )
    assert log_path.read_text(encoding="utf-8") == expected


def test_append_operations_log_entry_appends_without_overwrite(tmp_path: Path) -> None:
    """Second append keeps existing entries and advances line numbers."""
    log_path = tmp_path / "log.md"
    _ = append_operations_log_entry(
        log_path=log_path,
        operation_type=OperationsLogType.PLAN,
        title="Create plan",
        timestamp=datetime(2026, 4, 7, 10, 0),
    )
    second_line = append_operations_log_entry(
        log_path=log_path,
        operation_type=OperationsLogType.COMMIT,
        title="Finalize changes",
        timestamp=datetime(2026, 4, 7, 10, 5),
    )
    contents = log_path.read_text(encoding="utf-8")
    assert second_line == 5
    assert "## [2026-04-07T10:00] plan | Create plan\n\n" in contents
    assert "## [2026-04-07T10:05] commit | Finalize changes\n" in contents
