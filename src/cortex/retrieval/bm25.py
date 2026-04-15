"""Okapi BM25 scorer for memory bank retrieval.

Implements the Okapi BM25 ranking function described in:
Robertson, S. & Zaragoza, H. (2009). The Probabilistic Relevance Framework:
BM25 and Beyond. Foundations and Trends in Information Retrieval 3(4).

Pure functions, no external dependencies, stateless and safe for concurrent use.
"""

import math
import re
from collections import Counter


def tokenize(text: str) -> list[str]:
    """Lowercase and split on whitespace/punctuation; drop tokens shorter than 2 chars."""
    return [t for t in re.split(r"[\s\W]+", text.lower()) if len(t) >= 2]


def bm25_scores(
    query: str,
    corpus: list[str],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Compute Okapi BM25 score for each document against the query.

    Returns a list of floats parallel to corpus. Empty corpus returns [].
    IDF is computed over the candidate corpus at call time (no global index).
    """
    if not corpus:
        return []
    query_tokens = tokenize(query)
    tokenized = [tokenize(doc) for doc in corpus]
    lengths = [len(t) for t in tokenized]
    avg_dl = sum(lengths) / len(lengths) if lengths else 1.0
    n = len(corpus)
    scores = [0.0] * n
    for term in set(query_tokens):
        df = sum(1 for doc_tokens in tokenized if term in doc_tokens)
        idf = math.log((n - df + 0.5) / (df + 0.5) + 1)
        for i, doc_tokens in enumerate(tokenized):
            tf = Counter(doc_tokens)[term]
            if tf == 0:
                continue
            dl = lengths[i]
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / avg_dl)
            scores[i] += idf * numerator / denominator
    return scores


def rank(
    query: str,
    corpus: list[str],
    top_k: int = 10,
) -> list[tuple[int, float]]:
    """Return (original_index, score) pairs sorted by score descending.

    Filters zero-score results. Returns at most top_k results.
    """
    scores = bm25_scores(query, corpus)
    ranked = [(i, s) for i, s in enumerate(scores) if s > 0.0]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
