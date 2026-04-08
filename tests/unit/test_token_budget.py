"""Unit tests for token budget helpers."""

from pathlib import Path

import pytest

from cortex.tools.analysis.token_budget import (
    TokenBudgetEntry,
    compute_token_budget,
    format_token_budget_report,
    iter_memory_bank_text_paths,
)


def test_iter_memory_bank_skips_roadmap_and_original_backups(tmp_path: Path) -> None:
    """roadmap.md and *.original* names are excluded from iteration."""
    _ = (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    mb = tmp_path / ".cortex" / "memory-bank"
    mb.mkdir(parents=True)
    _ = (mb / "roadmap.md").write_text("y", encoding="utf-8")
    _ = (mb / "note.md.original").write_text("z", encoding="utf-8")
    _ = (mb / "keep.md").write_text("w", encoding="utf-8")
    paths = iter_memory_bank_text_paths(tmp_path)
    names = {p.name for p in paths}
    assert "roadmap.md" not in names
    assert "note.md.original" not in names
    assert "keep.md" in names
    assert "CLAUDE.md" in names


def test_word_threshold_boundaries(tmp_path: Path) -> None:
    """499/500/501 words map to candidate only when strictly over 500."""
    _ = (tmp_path / "CLAUDE.md").write_text(" ".join(["w"] * 499), encoding="utf-8")
    entries = compute_token_budget(tmp_path)
    assert len(entries) == 1
    assert entries[0].word_count == 499
    assert entries[0].is_candidate is False

    _ = (tmp_path / "CLAUDE.md").write_text(" ".join(["w"] * 500), encoding="utf-8")
    entries = compute_token_budget(tmp_path)
    assert entries[0].word_count == 500
    assert entries[0].is_candidate is False

    _ = (tmp_path / "CLAUDE.md").write_text(" ".join(["w"] * 501), encoding="utf-8")
    entries = compute_token_budget(tmp_path)
    assert entries[0].word_count == 501
    assert entries[0].is_candidate is True


def test_format_empty_entries() -> None:
    """Empty entry list produces a short message."""
    text = format_token_budget_report([])
    assert "No memory files scanned" in text


def test_format_mixed_candidates_and_recommendation() -> None:
    """Candidates get warning status; recommendation line appears when any candidate."""
    entries = [
        TokenBudgetEntry(path="a.md", word_count=100, is_candidate=False),
        TokenBudgetEntry(path="b.md", word_count=600, is_candidate=True),
    ]
    out = format_token_budget_report(entries)
    assert "| a.md | 100 | ✓ |" in out
    assert "compression candidate" in out
    assert "compress_memory_bank()" in out


@pytest.mark.timeout(10)
def test_compute_empty_project_no_files(tmp_path: Path) -> None:
    """No CLAUDE.md and no memory-bank yields no entries."""
    assert compute_token_budget(tmp_path) == []
