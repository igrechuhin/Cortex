"""Allowlist validation for pipeline_handoff pipeline/phase parameters."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff


def _resolve_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        AsyncMock(return_value=str(tmp_path)),
    )


@pytest.mark.asyncio
async def test_unknown_pipeline_rejected_when_alphanumeric(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shape-safe but unknown pipeline names must not create directories."""
    _resolve_root(monkeypatch, tmp_path)
    result = json.loads(
        await pipeline_handoff(operation="init", pipeline="custom-pipeline")
    )
    assert result["status"] == "error"
    assert "Unknown pipeline" in result["error"]
    assert "custom-pipeline" in result["error"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_unknown_phase_rejected_when_alphanumeric(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _resolve_root(monkeypatch, tmp_path)
    result = json.loads(
        await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="unknown-phase",
            data='{"status":"ok"}',
        )
    )
    assert result["status"] == "error"
    assert "Unknown phase" in result["error"]
    assert "unknown-phase" in result["error"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_allowed_pipeline_and_phase_still_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _resolve_root(monkeypatch, tmp_path)
    init = json.loads(await pipeline_handoff(operation="init", pipeline="implement"))
    assert init["status"] == "ok"
    wr = json.loads(
        await pipeline_handoff(
            operation="write_result",
            pipeline="implement",
            phase="finalize",
            data='{"status":"complete"}',
        )
    )
    assert wr["status"] == "ok"


@pytest.mark.asyncio
async def test_review_phase_allowed_for_implement_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Implement pipeline must accept the Review Gate phase."""
    _resolve_root(monkeypatch, tmp_path)
    init = json.loads(await pipeline_handoff(operation="init", pipeline="implement"))
    assert init["status"] == "ok"
    wr = json.loads(
        await pipeline_handoff(
            operation="write_result",
            pipeline="implement",
            phase="review",
            data='{"status":"complete","review_outcome":"no_gaps"}',
        )
    )
    assert wr["status"] == "ok"
    assert wr["phase"] == "review"
