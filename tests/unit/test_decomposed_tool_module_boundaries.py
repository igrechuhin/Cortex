"""Guard decomposed tool-module public surfaces (re-exports and facade wiring).

Batches 1–3 split ``models_reexports``, ``pre_commit_tools``, and ``similarity_engine``.
These tests fail early if a refactor breaks the stable import paths callers rely on.

When repo-wide ``check_file_sizes`` / ``check_function_lengths`` are clean, we still
assert plan-target modules stay within limits (and a soft cap for filename-excluded
``structure/models.py``) so excluded or recently-split files cannot silently regress.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.core.constants import (
    FILE_SIZE_EXCLUDED_FILENAMES,
    MAX_FILE_LINES,
)
from cortex.health_check.similarity_core import SimilarityCore
from cortex.health_check.similarity_engine import SimilarityEngine
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.refactoring_engine import RefactoringEngine
from cortex.tools import models as tools_models
from cortex.tools.execution import pre_commit_tools
from cortex.tools.execution.pre_commit_tools_inline_execution import (
    ADAPTER_REGISTRY as INLINE_ADAPTER_REGISTRY,
)
from cortex.tools.models_reexports_system import SessionStartResult
from cortex.tools.models_reexports_workflows import ExecutePreCommitChecksResult


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _logical_lines_py(path: Path) -> int:
    """Match ``.cortex/synapse/scripts/python/check_file_sizes.py`` ``count_lines``."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    count = 0
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if '"""' in stripped or "'''" in stripped:
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if not stripped or stripped.startswith("#"):
            continue
        count += 1
    return count


def test_refactoring_entrypoints_import_from_canonical_modules() -> None:
    """Container and execution tools import these paths; keep them stable."""
    assert ApprovalManager.__module__ == "cortex.refactoring.approval_manager"
    assert RefactoringEngine.__module__ == "cortex.refactoring.refactoring_engine"


@pytest.mark.parametrize(
    "relative",
    [
        "src/cortex/refactoring/approval_manager.py",
        "src/cortex/refactoring/refactoring_engine.py",
        "src/cortex/tools/usage/usage_analytics.py",
        "src/cortex/tools/files/markdown_lint_core.py",
        "src/cortex/tools/files/markdown_lint_cache_updates.py",
    ],
)
def test_plan_priority_modules_respect_max_logical_file_lines(relative: str) -> None:
    path = _repo_root() / relative
    assert _logical_lines_py(path) <= MAX_FILE_LINES


def test_excluded_structure_models_stays_below_soft_cap() -> None:
    """Filename-excluded from CI; still bound growth (see contributing size policy)."""
    path = _repo_root() / "src/cortex/structure/models.py"
    assert path.name in FILE_SIZE_EXCLUDED_FILENAMES
    assert _logical_lines_py(path) <= MAX_FILE_LINES * 2


def test_models_facade_matches_split_system_and_workflow_exports() -> None:
    """``cortex.tools.models`` must stay a single entrypoint for split re-export modules."""
    assert tools_models.SessionStartResult is SessionStartResult
    assert tools_models.ExecutePreCommitChecksResult is ExecutePreCommitChecksResult


def test_pre_commit_tools_reexports_adapter_registry_from_inline_module() -> None:
    """Facade must expose the same registry object tests and workers patch."""
    assert pre_commit_tools.ADAPTER_REGISTRY is INLINE_ADAPTER_REGISTRY


@pytest.mark.parametrize(
    ("attr", "expected"),
    [
        ("__mro__", (SimilarityEngine, SimilarityCore, object)),
        ("__module__", "cortex.health_check.similarity_engine"),
    ],
)
def test_similarity_engine_public_class_stays_on_facade_module(
    attr: str, expected: tuple[type, ...] | str
) -> None:
    """Subclass stays importable from ``similarity_engine``; core stays separate."""
    assert getattr(SimilarityEngine, attr) == expected
