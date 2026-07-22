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
    _ = await pipeline_handoff(operation="init", pipeline="implement", ctx=None)
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
async def test_gate_success_clears_only_gate_feedback_phase(
    isolated_project_root: Path,
) -> None:
    """A passing gate must clear only its own scratch phase.

    Regression: clearing "gate_feedback" previously wiped the *entire*
    live pipeline directory (op_clear ignored the `phase` argument and
    unconditionally rmtree'd the pipeline dir), silently discarding every
    other phase (select, code, review, finalize, verify, ...) an
    orchestrator had already accumulated in the same /cortex/do run the
    instant a mid-run run_quality_gate()/run_docs_gate() call happened to
    pass. See investigate-pipeline-handoff-phase-state-loss-during-long-
    running-subagent-calls.md.
    """
    _ = await pipeline_handoff(operation="init", pipeline="implement", ctx=None)
    _ = await pipeline_handoff(
        operation="write_result",
        pipeline="implement",
        phase="select",
        data='{"status": "complete"}',
        ctx=None,
    )
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
    assert pdir.exists()
    assert not (pdir / "gate_feedback-result.json").exists()

    state = json.loads(
        await pipeline_handoff(operation="read_state", pipeline="implement", ctx=None)
    )
    assert "select" in state["phases"]
    assert "gate_feedback" not in state["phases"]
