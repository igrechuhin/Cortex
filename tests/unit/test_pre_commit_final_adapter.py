"""Regressions for the opt-in detached final Swift adapter."""

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.context_logging import MCPContext
from cortex.core.models import ModelDict
from cortex.core.quality_gate_config import ProjectQualityGateConfig
from cortex.tools.execution import pre_commit_final_adapter as adapter
from cortex.tools.execution.pre_commit_final_tree import StagedCandidate
from cortex.tools.execution.pre_commit_final_worker_proof import (
    attach_worker_proof,
    final_worker_challenge,
    verify_worker_proof,
    worker_challenge_env,
)
from cortex.tools.execution.pre_commit_ownership import current_owner


def _worker() -> dict[str, object]:
    return {
        "status": "completed",
        "owner": "server",
        "quality_gate_pending": True,
        "markdown_result": {"files_with_errors": 0, "status": "success"},
        "result": {
            "language": "swift",
            "status": "success",
            "success": True,
            "checks_performed": [
                "fix_errors",
                "quality",
                "format",
                "synapse_format",
                "synapse_lint",
                "spelling",
                "type_check",
                "tests",
            ],
            "results": {
                "tests": {
                    "success": True,
                    "tests_passed": 98,
                    "tests_failed": 0,
                    "coverage": 0.91,
                }
            },
        },
    }


def test_only_worker_can_issue_a_bound_terminal_proof(tmp_path: Path) -> None:
    """Changing job path, owner, payload or challenge invalidates proof."""
    path = tmp_path / "worker.json"
    payload = _worker()
    key = "opaque server secret"
    with final_worker_challenge(key):
        attach_worker_proof(path, payload)
    assert not verify_worker_proof(path, payload, key)
    with final_worker_challenge(key, worker=True):
        attach_worker_proof(path, payload)
    assert verify_worker_proof(path, payload, key)
    payload["quality_gate_pending"] = False
    assert verify_worker_proof(path, payload, key)
    assert not verify_worker_proof(path, payload, "later attempt")
    assert not verify_worker_proof(path.with_name("different.json"), payload, key)
    payload["owner"] = "different server"
    assert not verify_worker_proof(path, payload, key)


def test_worker_verdict_rejects_trimmed_and_incomplete_payloads() -> None:
    """Green summary text is insufficient and selected results cannot certify."""
    payload = _worker()
    assert adapter.parse_worker_verdict(payload, 0.9).passed()
    assert not adapter.parse_worker_verdict(payload, 0.92).passed()
    result = payload["result"]
    assert isinstance(result, dict)
    result["test_filter"] = "one selected test"
    assert not adapter.parse_worker_verdict(payload, 0.9).passed()
    result["skipped_checks"] = ["quality"]
    with pytest.raises(ValueError, match="every required"):
        _ = adapter.parse_worker_verdict(payload, 0.9)
    with pytest.raises(ValueError):
        _ = adapter.parse_worker_verdict({"result": {"success": True}}, 0.9)


def test_legacy_project_config_keeps_regular_workflow() -> None:
    """Existing configurations do not turn on the new staged mode."""
    config = ProjectQualityGateConfig.model_validate_json('{"test_timeout":7200}')
    assert config.staged_final_swiftpm_commit is False


def _configure_adapter(
    monkeypatch: pytest.MonkeyPatch, root: Path, job: Path
) -> MCPContext:
    candidate = StagedCandidate(
        root=str(root),
        head="commit",
        index_hash="a" * 64,
        tree="candidate-tree",
        branch="refs/heads/main",
    )
    policy = ProjectQualityGateConfig(
        test_timeout=None, staged_final_swiftpm_commit=True
    )
    monkeypatch.setattr(
        adapter, "capture_staged_candidate", MagicMock(return_value=candidate)
    )
    monkeypatch.setattr(
        adapter, "get_session_id", MagicMock(return_value="123456789abc")
    )
    monkeypatch.setattr(
        adapter, "staged_final_preparation_complete", MagicMock(return_value=True)
    )
    monkeypatch.setattr(adapter, "quality_gate_job_path", MagicMock(return_value=job))
    monkeypatch.setattr(adapter, "run_staged_final_parity", AsyncMock())
    monkeypatch.setattr(
        adapter, "load_quality_gate_config", MagicMock(return_value=policy)
    )
    return cast(MCPContext, MagicMock(session_id="owned"))


@pytest.fixture
def staged_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Callable[[str, float], Awaitable[ModelDict]]:
    """Use actual adapter receipt handling, with a fixture worker endpoint."""
    job = tmp_path / "pre_commit_result_mock.json"
    ctx = _configure_adapter(monkeypatch, tmp_path, job)

    async def invoke() -> ModelDict:
        payload = _worker()
        payload["owner"] = current_owner()
        (challenge,) = worker_challenge_env().values()
        with final_worker_challenge(challenge, worker=True):
            attach_worker_proof(job, payload)
        _ = job.write_text(json.dumps(payload))
        return {"status": "success", "preflight_passed": True}

    async def call(intent: str, threshold: float) -> ModelDict:
        return await adapter.staged_swift_gate(
            tmp_path,
            intent=intent,
            ctx=ctx,
            timeout=30,
            threshold=threshold,
            test_filter=None,
            invoke=invoke,
            commit_message="test candidate",
        )

    return call


@pytest.mark.asyncio
async def test_adapter_denies_early_verify_and_binds_gate_settings(
    staged_gate: Callable[[str, float], Awaitable[ModelDict]],
) -> None:
    """Production handler authorizes only after an owned authenticated worker."""
    initial = await staged_gate("verify-staged-final", 0.90)
    assert initial["preflight_passed"] is False
    finished = await staged_gate("staged-final", 0.90)
    assert finished["staged_final_authorized"] is True
    verified = await staged_gate("verify-staged-final", 0.90)
    assert verified["staged_final_authorized"] is True
    changed = await staged_gate("verify-staged-final", 0.91)
    assert changed["preflight_passed"] is False


def test_staged_final_requires_prep_but_no_early_quality_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An opt-in attempt cannot import a legacy or synthetic early verdict."""
    run_id = "123456abcdef"
    commit = tmp_path / run_id / "commit"
    commit.mkdir(parents=True)
    monkeypatch.setattr(adapter, "session_dir", MagicMock(return_value=tmp_path))
    phases = {
        "preflight": {"status": "complete", "phase_status": "completed"},
        "docs": {"status": "complete", "phase_status": "completed"},
        "validate": {"status": "passed", "phase_status": "completed"},
    }
    state = {"session_id": run_id, "pipeline": "commit", "phases": phases}
    path = commit / "pipeline.json"
    _ = path.write_text(json.dumps(state))
    assert adapter.staged_final_preparation_complete(tmp_path, run_id)
    phases["checks"] = {"status": "passed", "phase_status": "completed"}
    _ = path.write_text(json.dumps(state))
    assert not adapter.staged_final_preparation_complete(tmp_path, run_id)
    del phases["checks"]
    phases["docs"]["phase_status"] = "running"
    _ = path.write_text(json.dumps(state))
    assert not adapter.staged_final_preparation_complete(tmp_path, run_id)


@pytest.mark.asyncio
async def test_local_commit_consumes_owned_receipt_once(
    staged_gate: Callable[[str, float], Awaitable[ModelDict]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = MagicMock(return_value="verified-commit")
    monkeypatch.setattr(adapter, "commit_verified_tree", writer)
    denied = await staged_gate("commit-staged-final", 0.90)
    assert denied["status"] == "error"
    writer.assert_not_called()
    assert (await staged_gate("staged-final", 0.90))["staged_final_authorized"] is True
    committed = await staged_gate("commit-staged-final", 0.90)
    assert committed["commit_sha"] == "verified-commit"
    assert committed["committed_tree"] == "candidate-tree"
    again = await staged_gate("commit-staged-final", 0.90)
    assert again["status"] == "error"
    writer.assert_called_once()
