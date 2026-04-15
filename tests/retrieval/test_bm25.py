"""Unit tests for cortex.retrieval.bm25."""

from cortex.retrieval.bm25 import bm25_scores, rank, tokenize


class TestTokenize:
    def test_lowercases_text(self) -> None:
        assert tokenize("Hello WORLD") == ["hello", "world"]

    def test_splits_on_punctuation(self) -> None:
        result = tokenize("foo,bar.baz")
        assert "foo" in result
        assert "bar" in result
        assert "baz" in result

    def test_drops_short_tokens(self) -> None:
        result = tokenize("a ab abc")
        assert "a" not in result
        assert "ab" in result
        assert "abc" in result

    def test_empty_string(self) -> None:
        assert tokenize("") == []


class TestBm25Scores:
    def test_empty_corpus_returns_empty(self) -> None:
        assert bm25_scores("query", []) == []

    def test_higher_tf_scores_higher(self) -> None:
        corpus = [
            "crash crash crash startup fastmcp",
            "crash startup fastmcp",
            "unrelated content about something else entirely",
        ]
        scores = bm25_scores("crash", corpus)
        assert scores[0] > scores[1] > 0.0
        assert scores[2] == 0.0

    def test_rare_term_scores_higher_than_common(self) -> None:
        corpus = [
            "fastmcp startup crash error",
            "startup",
            "startup startup startup startup",
        ]
        scores = bm25_scores("fastmcp", corpus)
        # "fastmcp" appears only in doc 0; docs 1 and 2 have zero
        assert scores[0] > 0.0
        assert scores[1] == 0.0
        assert scores[2] == 0.0

    def test_deterministic_for_same_inputs(self) -> None:
        corpus = ["foo bar baz", "bar baz qux", "unrelated text here"]
        result1 = bm25_scores("foo bar", corpus)
        result2 = bm25_scores("foo bar", corpus)
        assert result1 == result2

    def test_parallel_to_corpus_length(self) -> None:
        corpus = ["alpha beta", "gamma delta", "epsilon zeta"]
        scores = bm25_scores("alpha", corpus)
        assert len(scores) == 3


class TestRank:
    def test_returns_correct_indices(self) -> None:
        corpus = [
            "unrelated content here",
            "fastmcp startup crash",
            "fastmcp crash crash crash",
        ]
        results = rank("fastmcp crash", corpus)
        indices = [idx for idx, _ in results]
        assert 2 in indices
        assert 1 in indices
        assert 0 not in indices

    def test_sorted_descending(self) -> None:
        corpus = [
            "target term appears here twice target",
            "target term appears once",
            "unrelated content entirely",
        ]
        results = rank("target", corpus)
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_filters_zero_scores(self) -> None:
        corpus = ["apple banana", "cherry date", "matching query term here"]
        results = rank("matching", corpus)
        for _, score in results:
            assert score > 0.0

    def test_top_k_limits_results(self) -> None:
        corpus = [f"term doc{i}" for i in range(20)]
        results = rank("term", corpus, top_k=5)
        assert len(results) <= 5

    def test_empty_corpus_returns_empty(self) -> None:
        assert rank("query", []) == []

    def test_query_with_no_matches_returns_empty(self) -> None:
        corpus = ["apple banana", "cherry date"]
        results = rank("zzz_nonexistent", corpus)
        assert results == []

    def test_two_docs_only_one_matches(self) -> None:
        corpus = [
            "fastmcp startup crash error log",
            "unrelated content about other things",
        ]
        results = rank("fastmcp startup crash", corpus)
        assert len(results) == 1
        assert results[0][0] == 0
        assert results[0][1] > 0.0
