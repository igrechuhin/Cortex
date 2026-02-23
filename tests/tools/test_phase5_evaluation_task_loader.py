"""Tests for phase5_evaluation_task_loader (load_eval_task_dicts, build_eval_tasks)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cortex.tools.phase5_evaluation_task_loader import (
    build_eval_tasks,
    load_eval_task_dicts,
)


class TestLoadEvalTaskDicts:
    """Tests for load_eval_task_dicts."""

    def test_loads_array_json(self, tmp_path: Path) -> None:
        """Loads list of objects from JSON array file."""
        _ = (tmp_path / "a.json").write_text('[{"id": "1"}, {"id": "2"}]')
        result = load_eval_task_dicts(tmp_path)
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"

    def test_loads_single_object_json(self, tmp_path: Path) -> None:
        """Loads single object from JSON object file."""
        _ = (tmp_path / "single.json").write_text('{"id": "only"}')
        result = load_eval_task_dicts(tmp_path)
        assert len(result) == 1
        assert result[0]["id"] == "only"

    def test_skips_empty_file(self, tmp_path: Path) -> None:
        """Skips empty or whitespace-only files."""
        _ = (tmp_path / "empty.json").write_text("")
        _ = (tmp_path / "blank.json").write_text("   \n  ")
        result = load_eval_task_dicts(tmp_path)
        assert result == []

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        """Skips files that are not valid JSON."""
        _ = (tmp_path / "bad.json").write_text("not json")
        _ = (tmp_path / "good.json").write_text('[{"id": "1"}]')
        result = load_eval_task_dicts(tmp_path)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_skips_non_dict_items_in_array(self, tmp_path: Path) -> None:
        """Only dict items in array are included; non-dicts skipped."""
        _ = (tmp_path / "mixed.json").write_text(
            '[{"id": "a"}, 42, "x", null, {"id": "b"}]'
        )
        result = load_eval_task_dicts(tmp_path)
        assert len(result) == 2
        assert result[0]["id"] == "a"
        assert result[1]["id"] == "b"

    def test_returns_empty_when_no_json_files(self, tmp_path: Path) -> None:
        """Returns empty list when directory has no .json files."""
        _ = (tmp_path / "readme.txt").write_text("hello")
        result = load_eval_task_dicts(tmp_path)
        assert result == []

    def test_skips_file_on_read_error(self, tmp_path: Path) -> None:
        """Skips file when read_text raises OSError; other files still loaded."""
        good_path = tmp_path / "good.json"
        _ = good_path.write_text('[{"id": "1"}]')
        bad_path = tmp_path / "bad.json"
        _ = bad_path.write_text("{}")
        orig = Path.read_text

        def patched_read(self: Path, encoding: str = "utf-8") -> str:
            if self == bad_path:
                raise OSError("Permission denied")
            return orig(self, encoding=encoding)

        with patch.object(Path, "read_text", patched_read):
            result = load_eval_task_dicts(tmp_path)
        assert len(result) == 1
        assert result[0]["id"] == "1"


class TestBuildEvalTasks:
    """Tests for build_eval_tasks."""

    def test_validates_and_filters_by_id(self) -> None:
        """Valid records are validated and filtered by selected_ids."""

        def validate(rec: dict[str, object]) -> SimpleNamespace | None:
            if isinstance(rec.get("id"), str):
                return SimpleNamespace(id=rec["id"])
            return None

        records: list[dict[str, object]] = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        result = build_eval_tasks(
            records, selected_ids={"a", "c"}, validate=validate, id_attr="id"
        )
        assert len(result) == 2
        assert result[0].id == "a"
        assert result[1].id == "c"

    def test_empty_selected_ids_returns_all_valid(self) -> None:
        """When selected_ids is empty, all valid records are returned."""

        def validate(rec: dict[str, object]) -> SimpleNamespace | None:
            return SimpleNamespace(id=rec.get("id"))

        records: list[dict[str, object]] = [{"id": "1"}, {"id": "2"}]
        result = build_eval_tasks(records, selected_ids=set(), validate=validate)
        assert len(result) == 2
        assert result[0].id == "1"
        assert result[1].id == "2"

    def test_validate_raising_skips_record(self) -> None:
        """When validate raises, record is skipped."""

        def validate(rec: dict[str, object]) -> SimpleNamespace | None:
            if rec.get("id") == "bad":
                raise ValueError("invalid")
            return SimpleNamespace(id=rec.get("id"))

        records: list[dict[str, object]] = [
            {"id": "good"},
            {"id": "bad"},
            {"id": "ok"},
        ]
        result = build_eval_tasks(records, selected_ids=set(), validate=validate)
        assert len(result) == 2
        assert result[0].id == "good"
        assert result[1].id == "ok"

    def test_validate_returning_none_skips_record(self) -> None:
        """When validate returns None, record is skipped."""

        def validate(rec: dict[str, object]) -> SimpleNamespace | None:
            if rec.get("id") == "skip":
                return None
            return SimpleNamespace(id=rec.get("id"))

        records: list[dict[str, object]] = [
            {"id": "keep"},
            {"id": "skip"},
            {"id": "keep2"},
        ]
        result = build_eval_tasks(records, selected_ids=set(), validate=validate)
        assert len(result) == 2
        assert result[0].id == "keep"
        assert result[1].id == "keep2"
