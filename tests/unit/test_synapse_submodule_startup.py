"""Tests for MCP startup Synapse submodule sync (non-fatal, mocked git)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.core.synapse_submodule_startup import (
    SynapseStartupSyncOutcome,
    SynapseStartupSyncResult,
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


def test_dirty_worktree_stash_update_pop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Dirty worktree triggers stash push, update, stash pop sequence."""
    monkeypatch.delenv("CORTEX_SKIP_SYNAPSE_UPDATE", raising=False)
    _ = _git_root(tmp_path)
    calls: list[str] = []

    def fake_run(
        cmd: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if "stash" in cmd and "push" in cmd:
            calls.append("stash_push")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if "stash" in cmd and "pop" in cmd:
            calls.append("stash_pop")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if "submodule" in cmd and "update" in cmd:
            calls.append("update")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "unknown")

    with (
        patch(
            "cortex.core.synapse_submodule_startup.submodule_path_has_local_changes",
            return_value=True,
        ),
        patch(
            "cortex.core.synapse_submodule_startup.subprocess.run",
            side_effect=fake_run,
        ),
    ):
        result = try_sync_synapse_submodule_at_mcp_startup(tmp_path)
    assert calls == ["stash_push", "update", "stash_pop"]
    assert result.outcome is SynapseStartupSyncOutcome.SUCCESS_WITH_STASH


def test_dirty_worktree_stash_push_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When stash push fails, return STASH_FAILED and skip update."""
    monkeypatch.delenv("CORTEX_SKIP_SYNAPSE_UPDATE", raising=False)
    _ = _git_root(tmp_path)

    def fake_run(
        cmd: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if "stash" in cmd and "push" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "stash failed")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with (
        patch(
            "cortex.core.synapse_submodule_startup.submodule_path_has_local_changes",
            return_value=True,
        ),
        patch(
            "cortex.core.synapse_submodule_startup.subprocess.run",
            side_effect=fake_run,
        ),
    ):
        result = try_sync_synapse_submodule_at_mcp_startup(tmp_path)
    assert result.outcome is SynapseStartupSyncOutcome.STASH_FAILED


def test_dirty_worktree_stash_pop_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When stash pop fails after successful update, return STASH_POP_FAILED."""
    monkeypatch.delenv("CORTEX_SKIP_SYNAPSE_UPDATE", raising=False)
    _ = _git_root(tmp_path)

    def fake_run(
        cmd: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if "stash" in cmd and "push" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if "stash" in cmd and "pop" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "conflict")
        if "submodule" in cmd and "update" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with (
        patch(
            "cortex.core.synapse_submodule_startup.submodule_path_has_local_changes",
            return_value=True,
        ),
        patch(
            "cortex.core.synapse_submodule_startup.subprocess.run",
            side_effect=fake_run,
        ),
    ):
        result = try_sync_synapse_submodule_at_mcp_startup(tmp_path)
    assert result.outcome is SynapseStartupSyncOutcome.STASH_POP_FAILED
    assert "update=success" in result.detail


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


@pytest.mark.asyncio
async def test_lazy_registry_invokes_sync_after_root_resolution(
    tmp_path: Path,
) -> None:
    """Lazy prompt registry calls synapse sync after resolving project root."""
    from cortex.setup.lazy_prompt_registration import LazyPromptRegistry

    _ = _git_root(tmp_path)
    calls: list[str] = []

    async def fake_resolve(_ctx: object) -> Path:
        calls.append("resolve_root")
        return tmp_path

    def fake_sync(root: Path) -> SynapseStartupSyncResult:
        calls.append(f"sync:{root}")
        return SynapseStartupSyncResult(outcome=SynapseStartupSyncOutcome.SUCCESS)

    def fake_has_synapse() -> bool:
        return True  # Skip synapse prompt registration

    registry = LazyPromptRegistry()
    with (
        patch(
            "cortex.setup.lazy_prompt_registration._resolve_project_root",
            side_effect=fake_resolve,
        ),
        patch(
            "cortex.setup.lazy_prompt_registration.try_sync_synapse_submodule_at_mcp_startup",
            side_effect=fake_sync,
        ),
        patch(
            "cortex.setup.lazy_prompt_registration.prompt_manager_has_synapse_prompts",
            side_effect=fake_has_synapse,
        ),
        patch(
            "cortex.setup.lazy_prompt_registration._run_startup_repair",
            return_value=None,
        ),
        patch(
            "cortex.setup.lazy_prompt_registration._register_setup_if_needed",
            return_value=False,
        ),
    ):
        await registry.ensure_registered(None)

    assert calls[0] == "resolve_root"
    assert f"sync:{tmp_path}" in calls
