"""Tests for upstream plan dependency resolution."""

from pathlib import Path

from cortex.core.artifact_graph import resolve_upstream_plans


def _write_plan(plans_dir: Path, slug: str, status: str, depends_on: list[str]) -> None:
    deps = ", ".join(f'"{dep}"' for dep in depends_on)
    content = (
        "---\n"
        f"title: {slug}\n"
        f"status: {status}\n"
        f"depends_on: [{deps}]\n"
        "---\n"
    )
    _ = (plans_dir / f"{slug}.md").write_text(content, encoding="utf-8")


def test_resolve_upstream_plans_transitive_order(tmp_path: Path) -> None:
    # Arrange
    _write_plan(tmp_path, "base", "DONE", [])
    _write_plan(tmp_path, "mid", "DONE", ["base"])
    _write_plan(tmp_path, "leaf", "PENDING", ["mid"])

    # Act
    upstream = resolve_upstream_plans("leaf", tmp_path)

    # Assert
    assert upstream == ["base", "mid"]


def test_resolve_upstream_plans_excludes_non_done_dependencies(tmp_path: Path) -> None:
    # Arrange
    _write_plan(tmp_path, "base", "IN_PROGRESS", [])
    _write_plan(tmp_path, "leaf", "PENDING", ["base"])

    # Act
    upstream = resolve_upstream_plans("leaf", tmp_path)

    # Assert
    assert upstream == []
