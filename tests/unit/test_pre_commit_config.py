"""Tests for pre-commit configuration (e.g. .pre-commit-config.yaml)."""

from pathlib import Path
from typing import Any, cast

import yaml


def _repo_root() -> Path:
    """Return the repository root (directory containing .pre-commit-config.yaml)."""
    path = Path(__file__).resolve().parent.parent.parent
    assert (path / ".pre-commit-config.yaml").exists(), "Run from repo root"
    return path


def test_pre_commit_config_has_markdownlint_hook() -> None:
    """Pre-commit config must include markdownlint hook for early markdown lint on staged files."""
    root = _repo_root()
    config_path = root / ".pre-commit-config.yaml"
    raw = config_path.read_text()
    data = cast(dict[str, Any], yaml.safe_load(raw))
    assert isinstance(data, dict) and "repos" in data
    repos: list[dict[str, Any]] = data["repos"]
    local_repos = [r for r in repos if r.get("repo") == "local"]
    assert local_repos, "Expected at least one local repo in pre-commit config"
    hooks: list[dict[str, Any]] = []
    for repo in local_repos:
        hooks.extend(repo.get("hooks", []))
    markdownlint: dict[str, Any] | None = next(
        (h for h in hooks if h.get("id") == "markdownlint"), None
    )
    assert (
        markdownlint is not None
    ), "Pre-commit config must include hook with id=markdownlint"
    assert "markdownlint-cli2" in str(
        markdownlint.get("entry", "")
    ), "Markdownlint hook entry must run markdownlint-cli2"
    files_val = markdownlint.get("files")
    types_val = markdownlint.get("types")
    entry_str = str(markdownlint.get("entry", ""))
    has_files_match = files_val == r"\.(md|mdc)$"
    has_types_match = isinstance(types_val, list) and any(
        "md" in str(t) for t in cast(list[Any], types_val)
    )
    has_entry_md = "*.md" in entry_str or ".md" in entry_str
    assert (
        has_files_match or has_types_match or has_entry_md
    ), "Markdownlint hook must target .md/.mdc files (files regex, types, or entry glob)"
