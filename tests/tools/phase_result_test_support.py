"""Isolated real pipeline API helpers for publication regression fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)


@pytest.fixture
def publication_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    monkeypatch.setenv("CORTEX_PIPELINE_SESSION_ID", "publication-test")
    monkeypatch.setenv("CORTEX_EXPERIENCE_RECORDING", "0")
    return tmp_path


async def call(
    operation: str,
    data: object = None,
    *,
    phase: str = "code",
    pipeline: str = "implement",
) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            await pipeline_handoff(
                operation=operation, pipeline=pipeline, phase=phase, data=data
            )
        ),
    )


def read_object(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def evidence_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    }


def publication_dir(root: Path) -> Path:
    return root / ".cortex/.session/publication-test/implement"
