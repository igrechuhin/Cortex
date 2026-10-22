"""Runnable disposable-root smoke using the actual source resource assembly path."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from tests.tools.scoped_revision_test_support import (
    ScopedResourceHarness,
    manifest,
    task_state,
    write_plan,
    write_source,
)


async def run_scoped_source_smoke(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, object]:
    """Exercise source reads, mutation, resource cache, provenance, and real budgeting."""
    harness = ScopedResourceHarness(root, monkeypatch)
    first = await harness.read()
    selected = write_plan(root, goal="Fresh goal after real file mutation.")
    second = await harness.read()
    _ = write_source(root, "src/unrelated.py", "unrelated = True\n")
    third = await harness.read()
    assert first["status"] == second["status"] == third["status"] == "success"
    assert task_state(second).plan_goal.value == "Fresh goal after real file mutation."
    assert (
        manifest(second)["plan:selected"].revision
        == sha256(selected.read_bytes()).hexdigest()
    )
    assert (
        manifest(first)["plan:selected"].revision
        != manifest(second)["plan:selected"].revision
    )
    assert second == third
    assert harness.calls == 2
    return {
        "before_revision": manifest(first)["plan:selected"].revision,
        "after_revision": manifest(second)["plan:selected"].revision,
        "optimizer_calls": harness.calls,
        "unrelated_mutation_cache_hit": second == third,
        "token_budget": second["token_budget"],
        "total_tokens": second["total_tokens"],
    }


@pytest.mark.asyncio
async def test_disposable_source_api_read_mutate_read_smoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: root is disposable; optimizer selection is the sole substituted layer.
    root = tmp_path / "project"
    # Act: use actual handlers.load_context, scoped builder, source reads, and budget.
    receipt = await run_scoped_source_smoke(root, monkeypatch)
    # Assert
    assert receipt["optimizer_calls"] == 2
    assert receipt["unrelated_mutation_cache_hit"] is True
