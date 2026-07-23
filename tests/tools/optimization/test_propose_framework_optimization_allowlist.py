"""Tests for propose_framework_optimization path-allowlist enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.tools.optimization.propose_framework_optimization_allowlist import (
    PathAllowlistError,
    resolve_in_worktree,
    validate_relative_path_lexically,
)


def test_accepts_path_under_cortex_synapse() -> None:
    result = validate_relative_path_lexically(".cortex/synapse/rules/general/foo.mdc")

    assert result == ".cortex/synapse/rules/general/foo.mdc"


def test_accepts_path_under_cortex_rules() -> None:
    result = validate_relative_path_lexically(".cortex/rules/foo.mdc")

    assert result == ".cortex/rules/foo.mdc"


def test_normalizes_backslashes_and_whitespace() -> None:
    result = validate_relative_path_lexically("  .cortex\\rules\\foo.mdc  ")

    assert result == ".cortex/rules/foo.mdc"


def test_rejects_empty_path() -> None:
    with pytest.raises(PathAllowlistError):
        _ = validate_relative_path_lexically("   ")


def test_rejects_absolute_path() -> None:
    with pytest.raises(PathAllowlistError):
        _ = validate_relative_path_lexically("/etc/passwd")


def test_rejects_path_traversal() -> None:
    with pytest.raises(PathAllowlistError):
        _ = validate_relative_path_lexically("../../src/cortex/core/execution_env.py")


def test_rejects_traversal_inside_allowlisted_prefix() -> None:
    with pytest.raises(PathAllowlistError):
        _ = validate_relative_path_lexically(".cortex/rules/../../src/cortex/main.py")


def test_rejects_path_outside_allowlist() -> None:
    with pytest.raises(PathAllowlistError):
        _ = validate_relative_path_lexically("src/cortex/core/execution_env.py")


def test_rejects_similarly_prefixed_sibling_directory() -> None:
    """`.cortex/rules-evil/` must not pass a naive startswith(".cortex/rules") check."""
    with pytest.raises(PathAllowlistError):
        _ = validate_relative_path_lexically(".cortex/rules-evil/foo.mdc")


def test_resolve_in_worktree_returns_path_inside_worktree(tmp_path: Path) -> None:
    resolved = resolve_in_worktree(tmp_path, ".cortex/rules/foo.mdc")

    assert resolved == (tmp_path / ".cortex" / "rules" / "foo.mdc").resolve()
    assert resolved.is_relative_to(tmp_path.resolve())


def test_resolve_in_worktree_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(PathAllowlistError):
        _ = resolve_in_worktree(tmp_path, "../outside.mdc")
