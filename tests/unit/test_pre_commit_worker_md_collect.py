"""Tests for markdown path collection in the detached pre-commit worker.

See also phase A pre-commit tests in ``test_pre_commit_phase_tools_phase_a_integration``.
"""

from __future__ import annotations

from pathlib import Path

from cortex.tools.execution.pre_commit_worker import collect_pre_commit_markdown_paths


def test_collect_md_files_excludes_history_and_session_cache(tmp_path: Path) -> None:
    """Snapshots and cache copies are not linted as primary markdown sources."""
    hist = tmp_path / ".cortex" / "history"
    cache = tmp_path / ".cortex" / ".cache" / "session"
    bank = tmp_path / ".cortex" / "memory-bank"
    hist.mkdir(parents=True)
    cache.mkdir(parents=True)
    bank.mkdir(parents=True)
    _ = (hist / "snap.md").write_text("# snap\n", encoding="utf-8")
    _ = (cache / "pre.md").write_text("# cache\n", encoding="utf-8")
    keep = bank / "active.md"
    _ = keep.write_text("# active\n", encoding="utf-8")

    out = collect_pre_commit_markdown_paths(tmp_path)

    assert str(keep) in out
    assert not any("history" in Path(p).parts for p in out)
    assert not any(".cache" in Path(p).parts for p in out)


def test_collect_md_files_excludes_wiki_sources(tmp_path: Path) -> None:
    """Wiki ingest snapshots are not linted; relative links are repo-relative."""
    wiki_src = tmp_path / ".cortex" / "wiki" / "sources"
    wiki_src.mkdir(parents=True)
    snap = wiki_src / "readme-copy.md"
    _ = snap.write_text("# copy\n", encoding="utf-8")
    root_md = tmp_path / "top.md"
    _ = root_md.write_text("# top\n", encoding="utf-8")

    out = collect_pre_commit_markdown_paths(tmp_path)

    assert str(root_md) in out
    assert str(snap) not in out
