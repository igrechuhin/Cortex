"""Regression coverage for Makefile env-check and smoke guard wiring."""

from cortex.managers.initialization import get_project_root


def _read_repo_file(relative_path: str) -> str:
    """Read a repository file as UTF-8 text."""
    return (get_project_root() / relative_path).read_text(encoding="utf-8")


def test_env_check_uses_valid_python_version_snippet() -> None:
    """Makefile env-check must pass a valid -c snippet to bash (no stray backslashes)."""
    makefile = _read_repo_file("Makefile")
    assert (
        'print("%d.%d" % (sys.version_info.major, sys.version_info.minor))' in makefile
    )
    assert 'print(f\\"' not in makefile


def test_quality_workflow_runs_env_check_smoke_guard() -> None:
    """CI quality workflow must run make env-check after bootstrap."""
    workflow_path = get_project_root() / ".github/workflows/quality.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "Smoke-check local environment preflight" in workflow_text
    assert "make env-check" in workflow_text


def test_make_check_is_non_mutating_and_uses_black_check() -> None:
    """make check must not invoke mutating formatters; Black is verify-only on src/tests."""
    makefile = _read_repo_file("Makefile")
    check_line = next(
        line for line in makefile.splitlines() if line.startswith("check:")
    )
    deps = check_line.split(":", maxsplit=1)[1].strip().split()
    assert "format-check" in deps
    assert "format" not in deps
    assert "black --check src/ tests/" in makefile


def test_makefile_defines_bootstrap_offline_with_wheelhouse() -> None:
    """Offline bootstrap target must guard wheelhouse and mirror uv sync shape."""
    makefile = _read_repo_file("Makefile")
    assert "bootstrap-offline:" in makefile
    assert "WHEELHOUSE ?=" in makefile
    assert "uv sync --offline --group dev --extra dev" in makefile
    assert "UV_NO_INDEX=1" in makefile


def test_bootstrap_offline_workflow_is_wired() -> None:
    """Restricted-egress bootstrap workflow must exist with path filters and Docker isolation."""
    workflow_path = get_project_root() / ".github/workflows/bootstrap-offline.yml"
    text = workflow_path.read_text(encoding="utf-8")
    assert "bootstrap-restricted" in text
    assert "network none" in text
    assert "paths:" in text
    assert "uv.lock" in text
    assert "make bootstrap-offline" in text
    assert "make preflight" in text
