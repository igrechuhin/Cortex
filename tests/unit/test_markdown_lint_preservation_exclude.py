"""Owner-only ``.preservation/`` archives are omitted from markdown lint lists."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.files.markdown_lint_core import get_all_markdown_files_for_lint


def test_get_all_markdown_files_for_lint_skips_preservation(tmp_path: Path) -> None:
    """Frozen owner-only archives are not authored docs; skip them from lint."""
    root_md = tmp_path / "keep.md"
    _ = root_md.write_text("# x\n", encoding="utf-8")
    archived = tmp_path / ".preservation" / "research" / "snapshot.md"
    archived.parent.mkdir(parents=True)
    _ = archived.write_text("# snap\n", encoding="utf-8")

    paths = {
        p.relative_to(tmp_path).as_posix()
        for p in get_all_markdown_files_for_lint(tmp_path)
    }

    assert "keep.md" in paths
    assert ".preservation/research/snapshot.md" not in paths
