"""Integration tests for propose_framework_optimization_core (real git worktrees)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cortex.core.execution_env import (
    ExecutionEnvironment,
    ExecutionResult,
    LocalExecutionEnvironment,
)
from cortex.tools.optimization.propose_framework_optimization_core import (
    propose_framework_optimization_core,
)
from cortex.tools.optimization.propose_framework_optimization_models import (
    ProposedFileChange,
    ProposeFrameworkOptimizationRequest,
)

_VALID_MDC = "---\ndescription: Isolated worktree fix\n---\n\nBody.\n"


def _init_git_repo(root: Path) -> None:
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        _ = subprocess.run(args, cwd=root, check=True, capture_output=True)
    _ = (root / "README.md").write_text("seed\n", encoding="utf-8")
    _ = subprocess.run(
        ["git", "add", "README.md"], cwd=root, check=True, capture_output=True
    )
    _ = subprocess.run(
        ["git", "commit", "-q", "-m", "seed"], cwd=root, check=True, capture_output=True
    )


def _worktree_cache_dir(root: Path) -> Path:
    return root / ".cortex" / ".cache" / "propose-optimization-worktrees"


@pytest.mark.timeout(30)
def test_self_test_success_returns_diff_and_leaves_live_tree_untouched(
    tmp_path: Path,
) -> None:
    _init_git_repo(tmp_path)
    request = ProposeFrameworkOptimizationRequest(
        changes=[
            ProposedFileChange(
                relative_path=".cortex/rules/general/new-rule.mdc",
                new_content=_VALID_MDC,
            )
        ],
        rationale="Observed edge case in session X",
    )

    result = propose_framework_optimization_core(
        tmp_path, request, LocalExecutionEnvironment()
    )

    assert result.self_test_passed is True
    assert result.failure_reason is None
    assert "new-rule.mdc" in result.diff
    assert result.changed_paths == [".cortex/rules/general/new-rule.mdc"]
    assert not (tmp_path / ".cortex" / "rules").exists()
    cache_dir = _worktree_cache_dir(tmp_path)
    assert not cache_dir.exists() or not any(cache_dir.iterdir())


@pytest.mark.timeout(30)
def test_self_test_failure_leaves_no_orphaned_worktree(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    request = ProposeFrameworkOptimizationRequest(
        changes=[
            ProposedFileChange(
                relative_path=".cortex/rules/general/bad-rule.mdc",
                new_content="no frontmatter here",
            )
        ],
        rationale="Observed edge case in session Y",
    )

    result = propose_framework_optimization_core(
        tmp_path, request, LocalExecutionEnvironment()
    )

    assert result.self_test_passed is False
    assert result.failure_reason is not None
    assert "missing YAML frontmatter" in result.failure_reason
    assert not (tmp_path / ".cortex" / "rules").exists()
    cache_dir = _worktree_cache_dir(tmp_path)
    assert not cache_dir.exists() or not any(cache_dir.iterdir())


@pytest.mark.timeout(30)
def test_path_traversal_rejected_before_worktree_created(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    env = MagicMock(spec=ExecutionEnvironment)
    request = ProposeFrameworkOptimizationRequest(
        changes=[
            ProposedFileChange(
                relative_path="../../src/cortex/main.py", new_content="malicious"
            )
        ],
        rationale="attempted escape",
    )

    result = propose_framework_optimization_core(tmp_path, request, env)

    assert result.self_test_passed is False
    assert result.failure_reason is not None
    assert "path traversal rejected" in result.failure_reason
    env.execute.assert_not_called()


@pytest.mark.timeout(30)
def test_forced_exception_mid_run_still_tears_down_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_git_repo(tmp_path)
    request = ProposeFrameworkOptimizationRequest(
        changes=[
            ProposedFileChange(
                relative_path=".cortex/rules/general/new-rule.mdc",
                new_content=_VALID_MDC,
            )
        ],
        rationale="forced crash test",
    )

    from cortex.tools.optimization import propose_framework_optimization_core as module

    def _boom(_paths: list[Path]) -> str | None:
        raise RuntimeError("forced self-test crash")

    monkeypatch.setattr(module, "run_self_test", _boom)

    with pytest.raises(RuntimeError, match="forced self-test crash"):
        _ = propose_framework_optimization_core(
            tmp_path, request, LocalExecutionEnvironment()
        )

    cache_dir = _worktree_cache_dir(tmp_path)
    assert not cache_dir.exists() or not any(cache_dir.iterdir())


def test_no_push_or_pr_calls_anywhere_in_worktree_module() -> None:
    """Grep-equivalent safety check: no code path calls git push or gh pr create."""
    import cortex.tools.optimization.propose_framework_optimization_core as core_mod
    import cortex.tools.optimization.propose_framework_optimization_worktree as wt_mod

    for module in (core_mod, wt_mod):
        module_file = module.__file__
        assert module_file is not None
        source = Path(module_file).read_text(encoding="utf-8")
        assert "push" not in source.lower()
        assert "gh pr create" not in source.lower()


def test_execution_result_is_reused_from_core_module() -> None:
    """Sanity: propose module reuses ExecutionResult, no parallel result type."""
    assert ExecutionResult.__module__ == "cortex.core.execution_env"
