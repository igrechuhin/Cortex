"""Integration tests for GateFeedback persistence via pipeline_handoff.

Plan: .cortex/plans/feedback-loop-error-context.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.session.gate_feedback import (
    GateError,
    GateFeedback,
    GateName,
    persist_gate_feedback,
)
from cortex.tools.session.pipeline_handoff import pipeline_handoff


def _sample_quality_feedback() -> GateFeedback:
    return GateFeedback(
        gate=GateName.QUALITY,
        errors=[
            GateError(
                file="src/example.py",
                line=10,
                check="lint",
                message="unused import",
            )
        ],
        top_files=["src/example.py"],
        summary="Quality gate failed with 1 issue group(s).",
    )


@pytest.fixture
def isolated_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Use a temp tree as project root; fix session id for stable paths."""
    _ = (tmp_path / ".cortex").mkdir()
    monkeypatch.setenv("CORTEX_SESSION_ID", "gatefbinteg01")

    async def _root(_ctx: object | None) -> Path:
        return tmp_path

    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        _root,
    )
    return tmp_path


@pytest.mark.asyncio
async def test_gate_failure_writes_gate_feedback_result_file(
    isolated_project_root: Path,
) -> None:
    await pipeline_handoff(operation="init", pipeline="implement", ctx=None)
    feedback = _sample_quality_feedback()
    await persist_gate_feedback(feedback, ctx=None)

    result_path = (
        isolated_project_root
        / ".cortex"
        / ".session"
        / "gatefbinteg01"
        / "implement"
        / "gate_feedback-result.json"
    )
    assert result_path.is_file()
    raw: object = json.loads(result_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    loaded = GateFeedback.model_validate(raw)
    assert loaded.gate == GateName.QUALITY
    assert loaded.errors[0].file == "src/example.py"
    assert loaded.summary == feedback.summary


@pytest.mark.asyncio
async def test_gate_success_clears_implement_pipeline_dir(
    isolated_project_root: Path,
) -> None:
    await pipeline_handoff(operation="init", pipeline="implement", ctx=None)
    feedback = GateFeedback(
        gate=GateName.DOCS,
        errors=[GateError(file="<docs>", check="docs-gate", message="fail")],
        top_files=["<docs>"],
        summary="Docs gate failed with 1 issue group(s).",
    )
    await persist_gate_feedback(feedback, ctx=None)
    pdir = (
        isolated_project_root / ".cortex" / ".session" / "gatefbinteg01" / "implement"
    )
    assert (pdir / "gate_feedback-result.json").is_file()

    await persist_gate_feedback(None, ctx=None)
    assert not pdir.exists()
