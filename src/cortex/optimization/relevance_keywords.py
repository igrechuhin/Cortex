"""
Keyword extraction for relevance scoring.

Provides text-to-keywords pipeline used by the relevance scorer
for task description and content analysis.
"""

import re

_STOP_WORDS: set[str] = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "should",
    "could",
    "may",
    "might",
    "must",
    "can",
    "this",
    "that",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "what",
    "which",
    "who",
    "when",
    "where",
    "why",
    "how",
}


def _extract_words_from_text(text_lower: str) -> list[str]:
    """Extract words from lowercase text."""
    return re.findall(r"\b[a-z0-9][-a-z0-9]*\b", text_lower)


def _filter_stop_words_and_short(words: list[str]) -> list[str]:
    """Filter stop words and short words."""
    return [w for w in words if w not in _STOP_WORDS and len(w) > 2]


def _deduplicate_keywords(keywords: list[str]) -> list[str]:
    """Deduplicate keywords while maintaining order."""
    seen: set[str] = set()
    unique_keywords: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)
    return unique_keywords


def extract_keywords(text: str) -> list[str]:
    """
    Extract important keywords from text.

    Args:
        text: Input text

    Returns:
        List of keywords (lowercased)
    """
    text_lower = text.lower()
    words = _extract_words_from_text(text_lower)
    keywords = _filter_stop_words_and_short(words)
    return _deduplicate_keywords(keywords)
