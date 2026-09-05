"""Tests for session_access_source.py - session-log projection."""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from cortex.analysis.session_access_source import build_access_records
from tests.helpers.session_log_fixtures import recent_stamp, write_session_log


class TestBuildAccessRecords:
    """Tests for build_access_records."""

    def test_returns_empty_when_no_session_directory(self, tmp_path: Path):
        """Test a project with no session directory yields no records."""
        # Arrange / Act
        records = build_access_records(tmp_path, window_days=30)

        # Assert
        assert records == []

    def test_expands_call_into_one_record_per_selected_file(self, tmp_path: Path):
        """Test each selected file becomes a record with sibling context."""
        # Arrange
        _ = write_session_log(
            tmp_path, "s1", [(recent_stamp(5), "fix auth", ["a.md", "b.md", "c.md"])]
        )

        # Act
        records = build_access_records(tmp_path, window_days=30)

        # Assert
        assert [record.file for record in records] == ["a.md", "b.md", "c.md"]
        assert records[0].context_files == ["b.md", "c.md"]
        assert records[0].task_description == "fix auth"
        assert records[0].task_id == "s1:0"

    def test_assigns_distinct_task_id_per_call(self, tmp_path: Path):
        """Test separate load_context calls get separate task ids."""
        # Arrange
        _ = write_session_log(
            tmp_path,
            "s2",
            [(recent_stamp(9), "one", ["a.md"]), (recent_stamp(3), "two", ["b.md"])],
        )

        # Act
        records = build_access_records(tmp_path, window_days=30)

        # Assert
        assert [record.task_id for record in records] == ["s2:0", "s2:1"]

    def test_excludes_calls_older_than_window(self, tmp_path: Path):
        """Test in-file calls outside the window are dropped."""
        # Arrange
        old = (datetime.now() - timedelta(days=10)).isoformat(timespec="minutes")
        _ = write_session_log(
            tmp_path,
            "s3",
            [(old, "old", ["old.md"]), (recent_stamp(1), "new", ["n.md"])],
        )

        # Act
        records = build_access_records(tmp_path, window_days=2)

        # Assert
        assert [record.file for record in records] == ["n.md"]

    def test_skips_log_whose_mtime_precedes_window(self, tmp_path: Path):
        """Test a stale log file is skipped without being parsed."""
        # Arrange
        log_path = write_session_log(
            tmp_path, "s4", [(recent_stamp(1), "recent", ["a.md"])]
        )
        stale = time.time() - timedelta(days=10).total_seconds()
        os.utime(log_path, (stale, stale))

        # Act
        records = build_access_records(tmp_path, window_days=2)

        # Assert
        assert records == []

    def test_skips_corrupt_json_without_raising(self, tmp_path: Path):
        """Test a corrupt log file is skipped."""
        # Arrange
        log_path = write_session_log(
            tmp_path, "s5", [(recent_stamp(1), "task", ["a.md"])]
        )
        _ = log_path.write_text("{not json", encoding="utf-8")

        # Act
        records = build_access_records(tmp_path, window_days=30)

        # Assert
        assert records == []

    def test_skips_schema_invalid_log_without_raising(self, tmp_path: Path):
        """Test a schema-invalid log file is skipped."""
        # Arrange
        log_path = write_session_log(
            tmp_path, "s6", [(recent_stamp(1), "task", ["a.md"])]
        )
        _ = log_path.write_text('{"unexpected": true}', encoding="utf-8")

        # Act
        records = build_access_records(tmp_path, window_days=30)

        # Assert
        assert records == []

    def test_call_with_no_selected_files_yields_no_records(self, tmp_path: Path):
        """Test an empty selection contributes nothing."""
        # Arrange
        _ = write_session_log(tmp_path, "s7", [(recent_stamp(1), "empty", [])])

        # Act
        records = build_access_records(tmp_path, window_days=30)

        # Assert
        assert records == []

    def test_zero_day_window_yields_no_records(self, tmp_path: Path):
        """Test a zero-day window excludes even recent calls."""
        # Arrange
        _ = write_session_log(tmp_path, "s8", [(recent_stamp(30), "task", ["a.md"])])

        # Act
        records = build_access_records(tmp_path, window_days=0)

        # Assert
        assert records == []
