"""Parity test: check_function_lengths() vs run_quality_checks_for_all_languages().

Both code paths must produce the same violations for a synthetic fixture.
This test guards against silent divergence while the migration tracked in
.cortex/plans/migrate-check-function-lengths-callers.md is in progress.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.core.constants import MAX_FUNCTION_LINES
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root
from cortex.tools.execution.file_language_router import (
    run_quality_checks_for_all_languages,
)
from cortex.tools.execution.pre_commit_pipeline_quality import check_function_lengths

_REAL_ROOT = get_project_root(None)
_REAL_SYNAPSE = get_cortex_path(_REAL_ROOT, CortexResourceType.SYNAPSE)


def _make_oversized_function(project_root: Path) -> None:
    """Write a single Python file with one function that exceeds MAX_FUNCTION_LINES."""
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    body_lines = [f"    x{i} = {i}" for i in range(MAX_FUNCTION_LINES + 5)]
    content = "def oversized_func():\n" + "\n".join(body_lines) + "\n    return x0\n"
    _ = (src_dir / "fixture_oversized.py").write_text(content, encoding="utf-8")


def _symlink_synapse_scripts(project_root: Path) -> None:
    """Symlink the real synapse scripts tree so the router can find quality scripts."""
    cortex_dir = project_root / ".cortex"
    cortex_dir.mkdir(exist_ok=True)
    synapse_link = cortex_dir / "synapse"
    if not synapse_link.exists():
        synapse_link.symlink_to(_REAL_SYNAPSE)


@pytest.fixture()
def project_with_oversized_function(tmp_path: Path) -> Path:
    _make_oversized_function(tmp_path)
    _symlink_synapse_scripts(tmp_path)
    return tmp_path


def test_legacy_path_detects_oversized_function(
    project_with_oversized_function: Path,
) -> None:
    violations = check_function_lengths(project_with_oversized_function)
    assert len(violations) == 1
    assert violations[0].function == "oversized_func"
    assert violations[0].lines > MAX_FUNCTION_LINES


def test_router_path_detects_oversized_function(
    project_with_oversized_function: Path,
) -> None:
    _, func_violations = run_quality_checks_for_all_languages(
        project_with_oversized_function
    )
    assert len(func_violations) == 1
    assert func_violations[0].function == "oversized_func"
    assert func_violations[0].lines > MAX_FUNCTION_LINES


def test_both_paths_agree_on_violation_count(
    project_with_oversized_function: Path,
) -> None:
    """Core parity assertion: both paths must report the same number of violations."""
    legacy = check_function_lengths(project_with_oversized_function)
    _, router = run_quality_checks_for_all_languages(project_with_oversized_function)
    assert len(legacy) == len(router), (
        f"Legacy path found {len(legacy)} violation(s), "
        f"router path found {len(router)} — paths have diverged."
    )


def test_both_paths_agree_on_function_name(
    project_with_oversized_function: Path,
) -> None:
    legacy = check_function_lengths(project_with_oversized_function)
    _, router = run_quality_checks_for_all_languages(project_with_oversized_function)
    legacy_names = {v.function for v in legacy}
    router_names = {v.function for v in router}
    assert (
        legacy_names == router_names
    ), f"Legacy detected {legacy_names}, router detected {router_names}."
