"""Execution environment abstractions for command dispatch."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from cortex.core.pydantic_extra import EXTRA_FORBID


class ExecutionResult(BaseModel):
    """Normalized command execution result."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    returncode: int
    stdout: str
    stderr: str
    duration_ms: int


@runtime_checkable
class ExecutionEnvironment(Protocol):
    """Protocol for command execution in a specific environment."""

    def execute(self, tool: str, args: list[str], cwd: Path) -> ExecutionResult:
        """Execute command and return normalized result."""
        ...


class LocalExecutionEnvironment:
    """Run commands in the caller-provided working directory."""

    def execute(self, tool: str, args: list[str], cwd: Path) -> ExecutionResult:
        started = time.perf_counter()
        completed = subprocess.run(
            [tool, *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ExecutionResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_ms=elapsed_ms,
        )


class WorktreeExecutionEnvironment:
    """Run commands in a fixed worktree path regardless of caller-provided cwd."""

    def __init__(self, worktree_path: Path) -> None:
        self.worktree_path = worktree_path

    def execute(
        self, tool: str, args: list[str], cwd: Path
    ) -> ExecutionResult:  # noqa: ARG002
        started = time.perf_counter()
        completed = subprocess.run(
            [tool, *args],
            capture_output=True,
            text=True,
            cwd=self.worktree_path,
            check=False,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ExecutionResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_ms=elapsed_ms,
        )
