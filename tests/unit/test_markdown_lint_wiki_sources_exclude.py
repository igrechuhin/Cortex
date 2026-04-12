"""Wiki ``sources/`` snapshots are omitted from markdown lint file lists."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.files.markdown_lint_core import get_all_markdown_files_for_lint


def test_get_all_markdown_files_for_lint_skips_wiki_sources(tmp_path: Path) -> None:
    """Immutable wiki ingest copies keep repo-relative links; skip MD057 noise."""
    root_md = tmp_path / "keep.md"
    _ = root_md.write_text("# x\n", encoding="utf-8")
    snap = tmp_path / ".cortex" / "wiki" / "sources" / "seed.md"
    snap.parent.mkdir(parents=True)
    _ = snap.write_text("# snap\n", encoding="utf-8")

    paths = {
        p.relative_to(tmp_path).as_posix()
        for p in get_all_markdown_files_for_lint(tmp_path)
    }

    assert "keep.md" in paths
    assert ".cortex/wiki/sources/seed.md" not in paths
