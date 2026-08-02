"""Tests for the shape_log_path plan parameter and pre-plan log path validation."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.files.operations import manage_file
from cortex.tools.plans.crud import create_plan
from cortex.tools.plans.plan_log_paths import (
    PlanLogPathError,
    inject_shaping_constraints_from_shape_log,
    resolve_plan_log_path,
)
from cortex.tools.plans.plan_payloads import build_plan_create_arguments
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.tool_call_helpers import get_tool_fn

_SHAPE_RECORD = """# Shape: retrieval scoring

## Created

2026-08-02T00:00:00Z

## Resolved Decisions

- Decision: Which scorer?
  - Answer: BM25 hybrid
  - Source: user

## Assumptions

- Corpus stays under 10k documents

## Explicitly Out of Scope

- Re-ranking model training
"""

_SHAPE_PATH = ".cortex/plans/shape/shape-retrieval.md"


def _write_shape_record(tmp_path: Path, text: str = _SHAPE_RECORD) -> None:
    """Write a shaping record at the canonical project-relative location."""
    record = tmp_path / _SHAPE_PATH
    record.parent.mkdir(parents=True, exist_ok=True)
    _ = record.write_text(text, encoding="utf-8")


async def _create_plan_with(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    """Invoke plan create against a temp project root and return parsed JSON."""
    create_fn = get_tool_fn(create_plan)
    with patch(
        "cortex.tools.plans.crud.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        raw = await create_fn(operation="create", ctx=None, **kwargs)
    return cast(dict[str, object], json.loads(str(raw)))


# --- resolve_plan_log_path ------------------------------------------------


def test_resolve_plan_log_path_accepts_project_relative_path(tmp_path: Path) -> None:
    """A project-relative path resolves inside the root."""
    # Arrange / Act
    resolved = resolve_plan_log_path(
        tmp_path, _SHAPE_PATH, parameter_name="shape_log_path"
    )

    # Assert
    assert resolved == (tmp_path / _SHAPE_PATH).resolve()


def test_resolve_plan_log_path_rejects_traversal(tmp_path: Path) -> None:
    """A `..` traversal escaping the root raises PlanLogPathError."""
    # Arrange
    escaping = "../../etc/passwd"

    # Act / Assert
    with pytest.raises(PlanLogPathError, match="within the project root"):
        _ = resolve_plan_log_path(tmp_path, escaping, parameter_name="shape_log_path")


def test_resolve_plan_log_path_rejects_absolute_path(tmp_path: Path) -> None:
    """An absolute path raises PlanLogPathError even when it exists."""
    # Act / Assert
    with pytest.raises(PlanLogPathError, match="project-relative"):
        _ = resolve_plan_log_path(
            tmp_path, "/etc/hosts", parameter_name="shape_log_path"
        )


def test_resolve_plan_log_path_allows_interior_dotdot(tmp_path: Path) -> None:
    """A `..` that normalizes back inside the root is accepted."""
    # Act
    resolved = resolve_plan_log_path(
        tmp_path, ".cortex/plans/../plans/shape/x.md", parameter_name="shape_log_path"
    )

    # Assert
    assert resolved == (tmp_path / ".cortex/plans/shape/x.md").resolve()


# --- injection ------------------------------------------------------------


def test_inject_shaping_constraints_is_noop_without_path(tmp_path: Path) -> None:
    """No shape_log_path leaves the plan body untouched."""
    # Act
    out = inject_shaping_constraints_from_shape_log(tmp_path, "# Plan\n", None)

    # Assert
    assert out == "# Plan\n"


def test_inject_shaping_constraints_is_noop_for_missing_file(tmp_path: Path) -> None:
    """A nonexistent record is ignored rather than failing plan creation."""
    # Act
    out = inject_shaping_constraints_from_shape_log(tmp_path, "# Plan\n", _SHAPE_PATH)

    # Assert
    assert out == "# Plan\n"


def test_inject_shaping_constraints_is_noop_for_empty_file(tmp_path: Path) -> None:
    """An empty record contributes no constraints."""
    # Arrange
    _write_shape_record(tmp_path, "")

    # Act
    out = inject_shaping_constraints_from_shape_log(tmp_path, "# Plan\n", _SHAPE_PATH)

    # Assert
    assert out == "# Plan\n"


def test_inject_shaping_constraints_is_noop_without_resolved_decisions(
    tmp_path: Path,
) -> None:
    """A malformed record lacking Resolved Decisions is ignored."""
    # Arrange
    _write_shape_record(tmp_path, "# Shape: x\n\n## Assumptions\n\n- something\n")

    # Act
    out = inject_shaping_constraints_from_shape_log(tmp_path, "# Plan\n", _SHAPE_PATH)

    # Assert
    assert out == "# Plan\n"


# --- create_plan integration ---------------------------------------------


@pytest.mark.asyncio
async def test_create_plan_with_shape_log_adds_shaping_constraints(
    tmp_path: Path,
) -> None:
    """create_plan prepends Shaping Constraints when shape_log_path is provided."""
    # Arrange
    _ = ensure_test_cortex_structure(tmp_path)
    _write_shape_record(tmp_path)

    # Act
    result = await _create_plan_with(
        tmp_path,
        title="Shaped plan",
        content="# Plan\n\ncontent",
        slug="shaped-plan",
        shape_log_path=_SHAPE_PATH,
    )

    # Assert
    assert result["status"] == "success"
    created = (tmp_path / ".cortex" / "plans" / "shaped-plan.md").read_text(
        encoding="utf-8"
    )
    assert "## Shaping Constraints" in created
    assert "BM25 hybrid" in created
    assert "Corpus stays under 10k documents" in created
    assert "Re-ranking model training" in created


@pytest.mark.asyncio
async def test_create_plan_with_both_log_paths_injects_both_sections(
    tmp_path: Path,
) -> None:
    """shape_log_path and explore_log_path can be supplied together."""
    # Arrange
    _ = ensure_test_cortex_structure(tmp_path)
    _write_shape_record(tmp_path)
    explore_log = tmp_path / ".cortex" / "plans" / "explore" / "decision-log-b.md"
    explore_log.parent.mkdir(parents=True, exist_ok=True)
    _ = explore_log.write_text(
        "# Explore\n\n## Recommendation\nUse Option B\n\n## Selected Option\nOption B\n",
        encoding="utf-8",
    )

    # Act
    result = await _create_plan_with(
        tmp_path,
        title="Both logs",
        content="# Plan\n\ncontent",
        slug="both-logs",
        explore_log_path=".cortex/plans/explore/decision-log-b.md",
        shape_log_path=_SHAPE_PATH,
    )

    # Assert
    assert result["status"] == "success"
    created = (tmp_path / ".cortex" / "plans" / "both-logs.md").read_text(
        encoding="utf-8"
    )
    assert "## Shaping Constraints" in created
    assert "## Decision Basis" in created
    # AI: resolved requirements must outrank the explored approach.
    assert created.index("## Shaping Constraints") < created.index("## Decision Basis")


@pytest.mark.asyncio
async def test_create_plan_without_log_paths_is_unchanged(tmp_path: Path) -> None:
    """Omitting both log paths preserves existing behavior."""
    # Arrange
    _ = ensure_test_cortex_structure(tmp_path)

    # Act
    result = await _create_plan_with(
        tmp_path,
        title="Plain plan",
        content="# Plan\n\ncontent",
        slug="plain-plan",
    )

    # Assert
    assert result["status"] == "success"
    created = (tmp_path / ".cortex" / "plans" / "plain-plan.md").read_text(
        encoding="utf-8"
    )
    assert "## Shaping Constraints" not in created
    assert "## Decision Basis" not in created


@pytest.mark.asyncio
async def test_create_plan_rejects_traversing_shape_log_path(tmp_path: Path) -> None:
    """A traversing shape_log_path returns a typed error, not a created plan."""
    # Arrange
    _ = ensure_test_cortex_structure(tmp_path)

    # Act
    result = await _create_plan_with(
        tmp_path,
        title="Bad path",
        content="# Plan\n\ncontent",
        slug="bad-path",
        shape_log_path="../../etc/passwd",
    )

    # Assert
    assert result["status"] == "error"
    assert result["error"] == "Invalid plan log path"
    assert not (tmp_path / ".cortex" / "plans" / "bad-path.md").exists()


@pytest.mark.asyncio
async def test_create_plan_rejects_traversing_explore_log_path(tmp_path: Path) -> None:
    """The shared validator also guards explore_log_path."""
    # Arrange
    _ = ensure_test_cortex_structure(tmp_path)

    # Act
    result = await _create_plan_with(
        tmp_path,
        title="Bad explore",
        content="# Plan\n\ncontent",
        slug="bad-explore",
        explore_log_path="../../etc/passwd",
    )

    # Assert
    assert result["status"] == "error"
    assert result["error"] == "Invalid plan log path"


_TEN_SECTIONS = [
    "Goal",
    "Context",
    "Scope",
    "Approach",
    "Implementation Steps",
    "Verification Checklist",
    "Dependencies",
    "Success Criteria",
    "Testing Strategy",
    "Risks and Mitigation",
]


@pytest.mark.asyncio
async def test_create_plan_with_shape_log_preserves_all_plan_sections(
    tmp_path: Path,
) -> None:
    """Shape injection is additive: every required plan section survives intact."""
    # Arrange
    _ = ensure_test_cortex_structure(tmp_path)
    _write_shape_record(tmp_path)
    body = "# Full plan\n\n" + "\n\n".join(
        f"## {name}\n\nbody for {name}" for name in _TEN_SECTIONS
    )

    # Act
    result = await _create_plan_with(
        tmp_path,
        title="Full plan",
        content=body,
        slug="full-plan",
        shape_log_path=_SHAPE_PATH,
    )

    # Assert
    assert result["status"] == "success"
    created = (tmp_path / ".cortex" / "plans" / "full-plan.md").read_text(
        encoding="utf-8"
    )
    for name in _TEN_SECTIONS:
        assert f"## {name}" in created
    assert "## Shaping Constraints" in created


# --- payload builder ------------------------------------------------------


def test_build_plan_create_arguments_includes_shape_log_path() -> None:
    """The payload builder round-trips shape_log_path."""
    # Act
    args = build_plan_create_arguments(
        title="T", content="C", shape_log_path=_SHAPE_PATH
    )

    # Assert
    assert args["shape_log_path"] == _SHAPE_PATH


def test_build_plan_create_arguments_omits_unset_shape_log_path() -> None:
    """Unset shape_log_path is excluded from the arguments dict."""
    # Act
    args = build_plan_create_arguments(title="T", content="C")

    # Assert
    assert "shape_log_path" not in args


# --- shape log lifecycle --------------------------------------------------


@pytest.mark.asyncio
async def test_manage_file_lists_and_clears_shape_logs(tmp_path: Path) -> None:
    """manage_file exposes list_shape_logs and clear_shape_logs."""
    # Arrange
    _ = ensure_test_cortex_structure(tmp_path)
    shape_dir = tmp_path / ".cortex" / "plans" / "shape"
    shape_dir.mkdir(parents=True, exist_ok=True)
    old_log = shape_dir / "shape-old.md"
    _ = old_log.write_text("# old\n", encoding="utf-8")
    _ = (shape_dir / "shape-fresh.md").write_text("# fresh\n", encoding="utf-8")
    old_time = time.time() - (9 * 24 * 60 * 60)
    os.utime(old_log, (old_time, old_time))

    # Act / Assert
    with patch(
        "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        listed = json.loads(
            await manage_file(file_name="activeContext.md", operation="list_shape_logs")
        )
        assert listed["count"] == 2

        cleared = json.loads(
            await manage_file(
                file_name="activeContext.md", operation="clear_shape_logs"
            )
        )
        assert cleared["count"] == 1

        listed_after = json.loads(
            await manage_file(file_name="activeContext.md", operation="list_shape_logs")
        )
        assert listed_after["count"] == 1
        logs = cast(list[str], listed_after["logs"])
        assert "shape-fresh.md" in logs[0]
