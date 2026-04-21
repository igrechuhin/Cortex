from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.core.execution_env import (
    ExecutionEnvironment,
    ExecutionResult,
    LocalExecutionEnvironment,
    WorktreeExecutionEnvironment,
)
from cortex.tools.execution.pre_commit_zero_arg_tools import run_quality_gate_with_env


def test_local_environment_satisfies_protocol() -> None:
    env = LocalExecutionEnvironment()
    assert isinstance(env, ExecutionEnvironment)


def test_worktree_environment_satisfies_protocol() -> None:
    env = WorktreeExecutionEnvironment(Path("/tmp/worktree"))
    assert isinstance(env, ExecutionEnvironment)


def test_local_execution_environment_uses_caller_cwd() -> None:
    env = LocalExecutionEnvironment()
    process = subprocess.CompletedProcess(
        args=["git", "status"], returncode=0, stdout="ok", stderr=""
    )
    with patch("cortex.core.execution_env.subprocess.run", return_value=process) as run:
        result = env.execute("git", ["status"], Path("/tmp/project"))

    run.assert_called_once()
    assert run.call_args.kwargs["cwd"] == Path("/tmp/project")
    assert result == ExecutionResult(
        returncode=0, stdout="ok", stderr="", duration_ms=result.duration_ms
    )


def test_worktree_execution_environment_overrides_cwd() -> None:
    env = WorktreeExecutionEnvironment(Path("/tmp/worktree"))
    process = subprocess.CompletedProcess(
        args=["git", "status"], returncode=0, stdout="ok", stderr=""
    )
    with patch("cortex.core.execution_env.subprocess.run", return_value=process) as run:
        _ = env.execute("git", ["status"], Path("/tmp/ignored"))

    run.assert_called_once()
    assert run.call_args.kwargs["cwd"] == Path("/tmp/worktree")


@pytest.mark.asyncio
async def test_run_quality_gate_uses_injected_environment() -> None:
    env = MagicMock(spec=ExecutionEnvironment)
    with patch(
        "cortex.tools.execution.pre_commit_zero_arg_tools.run_quality_gate_inner",
        return_value={"status": "success", "preflight_passed": True},
    ) as inner:
        _ = await run_quality_gate_with_env(ctx=None, env=env)
    _ = inner.assert_awaited_once_with(None, env)
