"""Unit tests for session(operation='predict') dispatch and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.experience.predictions import open_predictions
from cortex.tools.session.dispatcher import session
from tests.helpers.tool_call_helpers import get_tool_fn


@pytest.fixture(autouse=True)
def _isolated_project(  # pyright: ignore[reportUnusedFunction]
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CORTEX_SESSION_ID", "predictunit")

    def _root() -> Path:
        return tmp_path

    monkeypatch.setattr("cortex.core.usage_context.get_current_project_root", _root)


async def _predict(
    prediction: str | None, because: str | None = None
) -> dict[str, object]:
    tool_fn = get_tool_fn(session)
    result = await tool_fn(
        operation="predict",
        prediction=prediction,
        task_description=because,
        ctx=None,
    )
    return cast(dict[str, object], json.loads(str(result)))


@pytest.mark.asyncio
async def test_predict_parses_and_records_claims(tmp_path: Path) -> None:
    # Arrange / Act
    parsed = await _predict(
        "gate clean; touches src/cortex/experience/claims.py",
        because="new module should be lint-clean on first pass",
    )

    # Assert
    assert parsed["status"] == "success"
    assert parsed["recorded"] is True
    claims = cast(list[dict[str, object]], parsed["claims"])
    assert [claim["kind"] for claim in claims] == ["gate_clean", "touches"]
    assert parsed["because"] == "new module should be lint-clean on first pass"
    assert len(open_predictions(tmp_path, "predictunit")) == 2


@pytest.mark.asyncio
async def test_predict_rejects_an_empty_prediction(tmp_path: Path) -> None:
    # Arrange / Act
    parsed = await _predict(None)

    # Assert
    assert parsed["status"] == "error"
    assert "predicts nothing" in str(parsed["error"])
    assert "Claim forms" in str(parsed["help"])
    assert open_predictions(tmp_path, "predictunit") == []


@pytest.mark.asyncio
async def test_predict_rejects_a_malformed_claim_before_recording(
    tmp_path: Path,
) -> None:
    # Arrange / Act
    parsed = await _predict("gate clean; coverage > 90")

    # Assert
    assert parsed["status"] == "error"
    assert "Malformed claim" in str(parsed["error"])
    assert open_predictions(tmp_path, "predictunit") == []


@pytest.mark.asyncio
async def test_unknown_operation_names_predict() -> None:
    # Arrange
    tool_fn = get_tool_fn(session)

    # Act
    result = await tool_fn(operation="nonsense", ctx=None)
    parsed = cast(dict[str, object], json.loads(str(result)))

    # Assert
    assert parsed["status"] == "error"
    assert "predict" in str(parsed["error"])
