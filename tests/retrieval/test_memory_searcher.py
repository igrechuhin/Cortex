"""Unit and integration tests for cortex.retrieval.memory_searcher."""

from pathlib import Path

from cortex.retrieval.memory_searcher import (
    MemoryBankSearcher,
    SearchResult,
    deduplicate,
)


def _make_cortex_dirs(root: Path) -> None:
    """Create minimal .cortex directory structure for tests."""
    (root / ".cortex" / "memory-bank").mkdir(parents=True, exist_ok=True)
    (root / ".cortex" / "plans").mkdir(parents=True, exist_ok=True)
    (root / ".cortex" / "wiki").mkdir(parents=True, exist_ok=True)


class TestDeduplicate:
    def test_removes_duplicate_by_source_and_start_line(self) -> None:
        results = [
            SearchResult(
                text="a", source="file.md", score=0.9, heading="H", start_line=1
            ),
            SearchResult(
                text="a", source="file.md", score=0.8, heading="H", start_line=1
            ),
            SearchResult(
                text="b", source="file.md", score=0.7, heading="H", start_line=5
            ),
        ]
        unique = deduplicate(results)
        assert len(unique) == 2
        assert unique[0].score == 0.9

    def test_preserves_different_source_same_line(self) -> None:
        results = [
            SearchResult(text="x", source="a.md", score=0.9, heading="", start_line=1),
            SearchResult(text="x", source="b.md", score=0.8, heading="", start_line=1),
        ]
        assert len(deduplicate(results)) == 2

    def test_empty_list(self) -> None:
        assert deduplicate([]) == []

    def test_no_duplicates_unchanged(self) -> None:
        results = [
            SearchResult(text="a", source="a.md", score=0.9, heading="", start_line=1),
            SearchResult(text="b", source="b.md", score=0.8, heading="", start_line=1),
        ]
        assert len(deduplicate(results)) == 2


class TestMemoryBankSearcher:
    def test_empty_cortex_returns_empty_results(self, tmp_path: Path) -> None:
        _make_cortex_dirs(tmp_path)
        searcher = MemoryBankSearcher(tmp_path)
        results = searcher.search("fastmcp startup crash")
        assert results == []

    def test_finds_matching_content(self, tmp_path: Path) -> None:
        _make_cortex_dirs(tmp_path)
        mb = tmp_path / ".cortex" / "memory-bank"
        _ = (mb / "activeContext.md").write_text(
            "# Active Context\n\nFastMCP startup crash occurred during initialization phase.\nThe error was related to port binding failure on startup.\n"
        )
        searcher = MemoryBankSearcher(tmp_path)
        results = searcher.search("FastMCP startup crash")
        assert len(results) >= 1
        assert any("FastMCP" in r.text or "startup" in r.text for r in results)

    def test_correct_file_ranks_first(self, tmp_path: Path) -> None:
        _make_cortex_dirs(tmp_path)
        mb = tmp_path / ".cortex" / "memory-bank"
        _ = (mb / "relevant.md").write_text(
            "## Temporal Memory\n\nTemporal memory indexing tracks when facts were created and ended.\nThe temporal indexer stores facts in a SQLite database for fast lookup.\n"
        )
        _ = (mb / "other.md").write_text(
            "## Other Topics\n\nUnrelated content about routing and network configuration.\n"
        )
        searcher = MemoryBankSearcher(tmp_path)
        results = searcher.search("temporal memory")
        assert len(results) >= 1
        assert "relevant.md" in results[0].source

    def test_file_filter_restricts_sources(self, tmp_path: Path) -> None:
        _make_cortex_dirs(tmp_path)
        mb = tmp_path / ".cortex" / "memory-bank"
        _ = (mb / "included.md").write_text(
            "Target query term appears here in included file content.\n"
        )
        _ = (mb / "excluded.md").write_text(
            "Target query term also appears in excluded file content.\n"
        )
        searcher = MemoryBankSearcher(tmp_path)
        results = searcher.search("Target query", file_filter=["included.md"])
        sources = {r.source for r in results}
        assert all("excluded.md" not in s for s in sources)

    def test_top_k_limits_results(self, tmp_path: Path) -> None:
        _make_cortex_dirs(tmp_path)
        mb = tmp_path / ".cortex" / "memory-bank"
        for i in range(10):
            _ = (mb / f"doc{i}.md").write_text(
                f"# Doc {i}\n\nSearch term match document content number {i}.\n"
            )
        searcher = MemoryBankSearcher(tmp_path)
        results = searcher.search("Search term match", top_k=3)
        assert len(results) <= 3

    def test_deduplication_applied(self, tmp_path: Path) -> None:
        _make_cortex_dirs(tmp_path)
        mb = tmp_path / ".cortex" / "memory-bank"
        _ = (mb / "dup.md").write_text(
            "# Section\n\nUnique content that matches the search query exactly.\n"
        )
        searcher = MemoryBankSearcher(tmp_path)
        results = searcher.search("unique content matches search", top_k=20)
        sources_lines = [(r.source, r.start_line) for r in results]
        assert len(sources_lines) == len(set(sources_lines))

    def test_results_are_search_result_models(self, tmp_path: Path) -> None:
        _make_cortex_dirs(tmp_path)
        mb = tmp_path / ".cortex" / "memory-bank"
        _ = (mb / "test.md").write_text(
            "Some relevant content that matches a search query term.\n"
        )
        searcher = MemoryBankSearcher(tmp_path)
        results = searcher.search("relevant content matches")
        for r in results:
            assert isinstance(r, SearchResult)
            assert r.score > 0.0
            assert r.source != ""

    def test_missing_directory_does_not_crash(self, tmp_path: Path) -> None:
        (tmp_path / ".cortex" / "memory-bank").mkdir(parents=True)
        _ = (tmp_path / ".cortex" / "memory-bank" / "test.md").write_text(
            "FastMCP connection error during startup initialization phase.\n"
        )
        searcher = MemoryBankSearcher(tmp_path)
        results = searcher.search("FastMCP connection error")
        assert len(results) >= 1

    def test_search_across_plans_dir(self, tmp_path: Path) -> None:
        _make_cortex_dirs(tmp_path)
        plans = tmp_path / ".cortex" / "plans"
        _ = (plans / "my-plan.md").write_text(
            "## Goal\n\nImplement the hybrid BM25 retrieval engine for memory bank search.\nThis will improve recall significantly.\n"
        )
        searcher = MemoryBankSearcher(tmp_path)
        results = searcher.search("hybrid BM25 retrieval engine")
        assert len(results) >= 1
        assert any("plans" in r.source for r in results)
