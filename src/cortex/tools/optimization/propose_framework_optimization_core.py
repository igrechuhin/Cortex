"""Core orchestration for propose_framework_optimization.

Flow: validate paths (lexical, no filesystem) -> create isolated worktree ->
apply changes inside it -> self-test -> on pass, build a diff -> always tear
down the worktree. The live working tree is never written to.
"""

from __future__ import annotations

from pathlib import Path

from cortex.core.execution_env import ExecutionEnvironment
from cortex.tools.optimization.propose_framework_optimization_allowlist import (
    PathAllowlistError,
    validate_relative_path_lexically,
)
from cortex.tools.optimization.propose_framework_optimization_apply import (
    apply_changes_to_worktree,
)
from cortex.tools.optimization.propose_framework_optimization_diff import (
    build_diff_and_rationale,
)
from cortex.tools.optimization.propose_framework_optimization_models import (
    ProposeFrameworkOptimizationRequest,
    ProposeFrameworkOptimizationResult,
)
from cortex.tools.optimization.propose_framework_optimization_selftest import (
    run_self_test,
)
from cortex.tools.optimization.propose_framework_optimization_worktree import (
    isolated_worktree,
)


def _validate_request_paths(request: ProposeFrameworkOptimizationRequest) -> str | None:
    """Lexical allowlist check for every change, before any worktree exists."""
    for change in request.changes:
        try:
            _ = validate_relative_path_lexically(change.relative_path)
        except PathAllowlistError as exc:
            return str(exc)
    return None


def _failure_result(rationale: str, reason: str) -> ProposeFrameworkOptimizationResult:
    return ProposeFrameworkOptimizationResult(
        self_test_passed=False,
        diff="",
        rationale=rationale,
        failure_reason=reason,
        changed_paths=[],
    )


def propose_framework_optimization_core(
    project_root: Path,
    request: ProposeFrameworkOptimizationRequest,
    env: ExecutionEnvironment,
) -> ProposeFrameworkOptimizationResult:
    """Draft, self-test, and (on pass) diff a Synapse/rules change.

    # AI: Never writes to project_root directly; all writes happen inside a
    # git worktree that isolated_worktree() guarantees removes in `finally`,
    # even when self-test raises mid-run (see worktree module docstring).
    """
    lexical_error = _validate_request_paths(request)
    if lexical_error is not None:
        return _failure_result(request.rationale, lexical_error)

    with isolated_worktree(project_root, env) as worktree_path:
        applied = apply_changes_to_worktree(worktree_path, request.changes)
        failure_reason = run_self_test(applied)
        if failure_reason is not None:
            return _failure_result(request.rationale, failure_reason)
        diff_text = build_diff_and_rationale(project_root, request.changes)

    return ProposeFrameworkOptimizationResult(
        self_test_passed=True,
        diff=diff_text,
        rationale=request.rationale,
        failure_reason=None,
        changed_paths=[c.relative_path for c in request.changes],
    )
