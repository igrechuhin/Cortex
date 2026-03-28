"""Tests for MCP startup Synapse submodule sync (non-fatal, mocked git)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.core.synapse_submodule_startup import (
    SynapseStartupSyncOutcome,
    try_sync_synapse_submodule_at_mcp_startup,
)


def _git_root(tmp: Path) -> Path:
    (tmp / ".git").mkdir(parents=True, exist_ok=True)
    return tmp


def test_skipped_opt_out_no_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CORTEX_SKIP_SYNAPSE_UPDATE", "1")
    _ = _git_root(tmp_path)
    with patch("cortex.core.synapse_submodule_startup.subprocess.run") as run:
        result = try_sync_synapse_submodule_at_mcp_startup(tmp_path)
    run.assert_not_called()
    assert result.outcome is SynapseStartupSyncOutcome.SKIPPED_OPT_OUT


def test_skipped_not_git_root(tmp_path: Path) -> None:
    with patch("cortex.core.synapse_submodule_startup.subprocess.run") as run:
        result = try_sync_synapse_submodule_at_mcp_startup(tmp_path)
    run.assert_not_called()
    assert result.outcome is SynapseStartupSyncOutcome.SKIPPED_NOT_GIT_ROOT


def test_skipped_dirty_worktree_no_update(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CORTEX_SKIP_SYNAPSE_UPDATE", raising=False)
    _ = _git_root(tmp_path)
    with (
        patch(
            "cortex.core.synapse_submodule_startup.submodule_path_has_local_changes",
            return_value=True,
        ),
        patch("cortex.core.synapse_submodule_startup.subprocess.run") as run,
    ):
        result = try_sync_synapse_submodule_at_mcp_startup(tmp_path)
    run.assert_not_called()
    assert result.outcome is SynapseStartupSyncOutcome.SKIPPED_DIRTY_WORKTREE


def test_success_on_clean_git_root(tmp_path: Path) -> None:
    _ = _git_root(tmp_path)

    def fake_run(
        cmd: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        assert "submodule" in cmd and "update" in cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with (
        patch(
            "cortex.core.synapse_submodule_startup.submodule_path_has_local_changes",
            return_value=False,
        ),
        patch(
            "cortex.core.synapse_submodule_startup.subprocess.run",
            side_effect=fake_run,
        ) as run,
    ):
        result = try_sync_synapse_submodule_at_mcp_startup(tmp_path)
    run.assert_called_once()
    assert result.outcome is SynapseStartupSyncOutcome.SUCCESS


def test_git_error_nonfatal_returns_outcome(tmp_path: Path) -> None:
    _ = _git_root(tmp_path)

    def fake_run(
        cmd: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "network exploded")

    with (
        patch(
            "cortex.core.synapse_submodule_startup.submodule_path_has_local_changes",
            return_value=False,
        ),
        patch(
            "cortex.core.synapse_submodule_startup.subprocess.run",
            side_effect=fake_run,
        ),
    ):
        result = try_sync_synapse_submodule_at_mcp_startup(tmp_path)
    assert result.outcome is SynapseStartupSyncOutcome.GIT_ERROR
    assert "network" in result.detail


def test_git_timeout_nonfatal_returns_outcome(tmp_path: Path) -> None:
    _ = _git_root(tmp_path)

    def fake_run(
        cmd: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd, timeout=1.0)

    with (
        patch(
            "cortex.core.synapse_submodule_startup.submodule_path_has_local_changes",
            return_value=False,
        ),
        patch(
            "cortex.core.synapse_submodule_startup.subprocess.run",
            side_effect=fake_run,
        ),
    ):
        result = try_sync_synapse_submodule_at_mcp_startup(
            tmp_path, update_timeout=0.01
        )
    assert result.outcome is SynapseStartupSyncOutcome.GIT_TIMEOUT


def test_run_server_once_invokes_sync_before_mcp_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Server startup path calls sync once; failures do not block mcp.run."""
    calls: list[str] = []

    def fake_sync_before_listen() -> None:
        calls.append("sync")

    def fake_inject() -> None:
        calls.append("inject")

    def fake_patch() -> None:
        calls.append("patch")

    def fake_transport() -> str:
        return "stdio"

    def fake_run_mcp_with_handlers(transport: str) -> None:
        _ = transport
        calls.append("mcp.run")

    monkeypatch.setattr(
        "cortex.main._sync_synapse_before_listen", fake_sync_before_listen
    )
    monkeypatch.setattr("cortex.main._inject_sequential_thinking_core", fake_inject)
    monkeypatch.setattr("cortex.main._patch_mcp_server_handle_request", fake_patch)
    monkeypatch.setattr("cortex.main.get_effective_transport", fake_transport)
    monkeypatch.setattr(
        "cortex.main._run_mcp_with_transport_handlers", fake_run_mcp_with_handlers
    )

    import cortex.main as cortex_main

    cortex_main._run_server_once()  # pyright: ignore[reportPrivateUsage]

    assert calls[0] == "sync"
    assert "mcp.run" in calls
