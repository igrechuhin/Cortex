"""Search interface for tools and scripts by query string."""

import re


def _tokenize_query(query: str) -> set[str]:
    """Tokenize query into lowercase words (min length 2)."""
    normalized = query.lower().replace("-", " ").replace("_", " ")
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    return {t for t in tokens if len(t) >= 2}


def _name_tokens(name: str) -> set[str]:
    """Tokenize a tool/script name."""
    normalized = name.lower().replace("-", " ").replace("_", " ")
    return set(re.findall(r"[a-z0-9]+", normalized))


def _query_score(query_tokens: set[str], name: str) -> float:
    """Score 0-1: fraction of query tokens that appear in name."""
    if not query_tokens:
        return 0.0
    name_t = _name_tokens(name)
    if not name_t:
        return 0.0
    hits = sum(1 for q in query_tokens if q in name_t or any(q in n for n in name_t))
    return min(1.0, hits / len(query_tokens))


def search_tools_and_scripts(
    query: str,
    tool_names: list[str],
    script_names: list[str],
    min_score: float = 0.2,
    max_results: int = 20,
) -> list[tuple[str, str, float]]:
    """Search tools and scripts by query string; return (name, type, score).

    Args:
        query: Search query (e.g. "format python").
        tool_names: Known MCP tool names.
        script_names: Known Synapse script names.
        min_score: Minimum score to include.
        max_results: Maximum total results.

    Returns:
        List of (name, type, score) sorted by score descending.
    """
    q_tokens = _tokenize_query(query)
    if not q_tokens:
        return []
    results: list[tuple[str, str, float]] = []
    for name in tool_names:
        score = _query_score(q_tokens, name)
        if score >= min_score:
            results.append((name, "tool", round(score, 4)))
    for name in script_names:
        score = _query_score(q_tokens, name)
        if score >= min_score:
            results.append((name, "script", round(score, 4)))
    results.sort(key=lambda x: -x[2])
    return results[:max_results]
