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
    assert "autofix()" in text
    assert "run_quality_gate()" in text


_LEGACY_RESCUE_DOC_EXCEPTIONS = frozenset(
    {
        # These intentionally document the one-time migration rescue of a real
        # (non-symlink) .cursor/memory-bank directory left by a pre-removal
        # Cortex version — not a canonical path recommendation.
        _REPO_ROOT / "docs" / "prompts" / "migrate.md",
        _REPO_ROOT / "docs" / "prompts" / "initialize.md",
        _REPO_ROOT / "docs" / "guides" / "migration.md",
        _REPO_ROOT / "docs" / "getting-started.md",
        # Immutable raw ingest mirrors of the above (.cortex/wiki/sources/ is a
        # verbatim, content-preserving archive — see mcp__cortex__ingest).
        _REPO_ROOT / ".cortex" / "wiki" / "sources" / "docs-prompts-migrate-md.md",
        _REPO_ROOT / ".cortex" / "wiki" / "sources" / "docs-prompts-initialize-md.md",
        _REPO_ROOT / ".cortex" / "wiki" / "sources" / "docs-guides-migration-md.md",
        _REPO_ROOT / ".cortex" / "wiki" / "sources" / "docs-getting-started-md.md",
    }
)


def test_markdown_files_have_no_stale_cursor_memory_bank_path_when_scanned() -> None:
    skip_parts = frozenset({".git", ".venv", "node_modules"})
    for md_path in _REPO_ROOT.rglob("*.md"):
        if skip_parts.intersection(md_path.parts):
            continue
        if md_path in _LEGACY_RESCUE_DOC_EXCEPTIONS:
            continue
        text = md_path.read_text(encoding="utf-8")
        assert (
            _LEGACY_CURSOR_MEMORY_BANK not in text
        ), f"Stale path in {md_path.relative_to(_REPO_ROOT)}"
