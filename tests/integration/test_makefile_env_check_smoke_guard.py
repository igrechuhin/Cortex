"""Regression coverage for Makefile env-check and smoke guard wiring."""

from cortex.managers.initialization import get_project_root


def _read_repo_file(relative_path: str) -> str:
    """Read a repository file as UTF-8 text."""
    return (get_project_root() / relative_path).read_text(encoding="utf-8")


def test_env_check_uses_valid_python_f_string_quoting() -> None:
    """Makefile env-check inline Python must escape nested double quotes."""
    makefile = _read_repo_file("Makefile")
    assert 'print(f\\"{sys.version_info.major}.{sys.version_info.minor}\\")' in makefile
    assert 'print(f"{sys.version_info.major}.{sys.version_info.minor}")' not in makefile


def test_quality_workflow_runs_env_check_smoke_guard() -> None:
    """CI quality workflow must run make env-check after bootstrap."""
    workflow_path = get_project_root() / ".github/workflows/quality.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "Smoke-check local environment preflight" in workflow_text
    assert "make env-check" in workflow_text
