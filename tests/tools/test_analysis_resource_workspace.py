"""Real usage models and selected-workspace inventory at cortex://analysis."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.pattern_types import FileStatsEntry
from cortex.managers.types import ManagersDict
from cortex.tools.context.analysis_operations import analyze
from tests.helpers.managers import make_test_managers
from tests.helpers.session_log_fixtures import recent_stamp, seed_accesses


async def _workspace_managers(root: Path) -> ManagersDict:
    """Keep the real workspace-backed analyzer without unrelated managers."""
    managers = make_test_managers()
    managers.pattern_analyzer = PatternAnalyzer(root)
    return managers


@contextmanager
def _selected_workspace(root: Path, target: str) -> Iterator[None]:
    """Select request-local input without writing live session configuration."""
    with (
        patch("cortex.core.usage_context.get_current_project_root", return_value=root),
        patch("cortex.core.mcp_stability_usage.get_current_managers", return_value={}),
        patch(
            "cortex.core.session_config.read_session_config",
            return_value={"analysis_target": target},
        ),
        patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new=AsyncMock(side_effect=_workspace_managers),
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_resource_preserves_real_nonempty_patterns(tmp_path: Path) -> None:
    """A qualifying pair retains every co-access and task evidence field."""
    # Arrange
    files = ["a.md", "b.md"]
    _ = seed_accesses(tmp_path, "selected", [files] * 5)
    # Act
    with _selected_workspace(tmp_path, "usage_patterns"):
        result = json.loads(await analyze())
    # Assert
    assert result["status"] == "success"
    assert result["time_window_days"] == 30
    patterns = result["patterns"]
    assert patterns["co_access_patterns"] == [
        {
            "files": files,
            "file_1": "a.md",
            "file_2": "b.md",
            "correlation": 0.0,
            "correlation_strength": "medium",
            "occurrences": 5,
            "co_access_count": 5,
            "context": None,
        }
    ]
    assert patterns["access_frequency"]["a.md"]["access_count"] == 5
    tasks = {task["task_id"]: task for task in patterns["task_patterns"]}
    assert tasks["selected:0"]["files"] == files
    assert tasks["selected:0"]["file_count"] == 2
    assert tasks["selected:0"]["description"] == "task-0"
    assert patterns["unused_files"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("call_count", [0, 2], ids=["empty", "below-threshold"])
async def test_resource_empty_and_below_threshold(
    tmp_path: Path, call_count: int
) -> None:
    """Low co-access frequency is not a serialization error or lost task data."""
    # Arrange
    if call_count:
        _ = seed_accesses(tmp_path, "selected", [["a.md", "b.md"]] * call_count)
    # Act
    with _selected_workspace(tmp_path, "usage_patterns"):
        result = json.loads(await analyze())
    # Assert
    assert result["status"] == "success"
    patterns = result["patterns"]
    assert patterns["co_access_patterns"] == []
    assert patterns["unused_files"] == []
    if call_count:
        assert patterns["access_frequency"]["a.md"]["access_count"] == call_count
        assert {t["task_id"] for t in patterns["task_patterns"]} == {
            "selected:0",
            "selected:1",
        }
    else:
        assert patterns["access_frequency"] == {}
        assert patterns["task_patterns"] == []


@pytest.mark.asyncio
async def test_resource_serializes_unused_file_models(tmp_path: Path) -> None:
    """The sibling unused-file model list also crosses the JSON boundary."""
    # Arrange
    managers = await _workspace_managers(tmp_path)
    analyzer = managers.pattern_analyzer
    assert isinstance(analyzer, PatternAnalyzer)
    analyzer.access_data.file_stats["old.md"] = FileStatsEntry(
        total_accesses=0, first_access=recent_stamp(), last_access=""
    )
    # Act
    with (
        _selected_workspace(tmp_path, "usage_patterns"),
        patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new=AsyncMock(return_value=managers),
        ),
    ):
        result = json.loads(await analyze())
    # Assert
    assert result["status"] == "success"
    assert result["patterns"]["unused_files"] == [
        {
            "file": "old.md",
            "last_access": None,
            "days_since_access": None,
            "total_accesses": 0,
            "status": "never_accessed",
        }
    ]


def _write_inventory(root: Path, prefix: str, count: int) -> None:
    """Create canonical prompt and categorized rule inputs, including empty dirs."""
    synapse = root / ".cortex" / "synapse"
    prompts = synapse / "prompts"
    rules = synapse / "rules" / "python"
    prompts.mkdir(parents=True)
    rules.mkdir(parents=True)
    (synapse / "rules" / "empty").mkdir()
    for index in range(count):
        _ = (prompts / f"{prefix}-{index}.md").write_text(
            f"# {prefix} prompt {index}\nReview the selected workspace.",
            encoding="utf-8",
        )
        _ = (rules / f"{prefix}-{index}.mdc").write_text(
            f"# {prefix} rule {index}\nUse explicit types.", encoding="utf-8"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["prompts", "rules"])
@pytest.mark.parametrize("count", [0, 3], ids=["empty", "populated"])
async def test_resource_inventory_uses_selected_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str, count: int
) -> None:
    """Inventory honors selection outside CWD and counts files, not categories."""
    # Arrange
    selected, other = tmp_path / "selected", tmp_path / "other"
    _write_inventory(selected, "selected", count)
    _write_inventory(other, "other", 2)
    monkeypatch.chdir(other)
    # Act
    with _selected_workspace(selected, target):
        selected_result = json.loads(await analyze())
    with _selected_workspace(other, target):
        other_result = json.loads(await analyze())
    # Assert
    assert selected_result["status"] == "success"
    assert selected_result[target]["total"] == count
    assert other_result[target]["total"] == 2
    dependencies = selected_result[f"{target[:-1]}_dependencies"]
    expected_prefix = "python/" if target == "rules" else ""
    suffix = "mdc" if target == "rules" else "md"
    assert set(dependencies) == {
        f"{expected_prefix}selected-{i}.{suffix}" for i in range(count)
    }


@pytest.mark.asyncio
async def test_resource_patterns_do_not_leak_between_workspaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workspace selection cannot reuse CWD or previously analyzed patterns."""
    # Arrange
    selected, other = tmp_path / "selected", tmp_path / "other"
    _ = seed_accesses(selected, "selected", [["a.md", "b.md"]] * 3)
    _ = seed_accesses(other, "other", [["x.md", "y.md"]] * 5)
    monkeypatch.chdir(other)
    # Act
    with _selected_workspace(selected, "usage_patterns"):
        first = json.loads(await analyze())
    with _selected_workspace(other, "usage_patterns"):
        second = json.loads(await analyze())
    with _selected_workspace(selected, "usage_patterns"):
        repeated = json.loads(await analyze())
    # Assert
    assert set(first["patterns"]["access_frequency"]) == {"a.md", "b.md"}
    assert first["patterns"]["co_access_patterns"][0]["co_access_count"] == 3
    assert set(second["patterns"]["access_frequency"]) == {"x.md", "y.md"}
    assert second["patterns"]["co_access_patterns"][0]["co_access_count"] == 5
    assert repeated["patterns"] == first["patterns"]
