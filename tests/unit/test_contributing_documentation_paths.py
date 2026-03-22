"""Regression tests for contributor documentation paths and workflow matrix."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONTRIBUTING = _REPO_ROOT / "docs" / "development" / "contributing.md"

# Pre-.cortex Memory Bank path; must not appear in Markdown docs (canonical: .cortex/memory-bank).
_LEGACY_CURSOR_MEMORY_BANK = ".cursor" + "/memory-bank"


def test_contributing_md_has_no_stale_cursor_paths_when_scanned() -> None:
    text = _CONTRIBUTING.read_text(encoding="utf-8")
    assert _LEGACY_CURSOR_MEMORY_BANK not in text


def test_contributing_md_has_workflow_matrix_when_rendered() -> None:
    text = _CONTRIBUTING.read_text(encoding="utf-8")
    assert "| Task | Human (local CLI) | Agent (MCP) |" in text
    assert "fix_quality_issues()" in text
    assert "run_quality_gate()" in text


def test_markdown_files_have_no_stale_cursor_memory_bank_path_when_scanned() -> None:
    skip_parts = frozenset({".git", ".venv", "node_modules"})
    for md_path in _REPO_ROOT.rglob("*.md"):
        if skip_parts.intersection(md_path.parts):
            continue
        text = md_path.read_text(encoding="utf-8")
        assert (
            _LEGACY_CURSOR_MEMORY_BANK not in text
        ), f"Stale path in {md_path.relative_to(_REPO_ROOT)}"
