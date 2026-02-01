"""Map use cases to relevant tools and scripts."""

import re

from cortex.script_analysis.models import UseCaseExtraction


def _tokenize_name(name: str) -> set[str]:
    """Tokenize a name into lowercase words (split on _ and non-alpha)."""
    normalized = name.lower().replace("-", " ").replace("_", " ")
    return set(re.findall(r"[a-z0-9]+", normalized))


def _overlap_score(
    use_case_label: str,
    keywords: list[str],
    name: str,
) -> float:
    """Return overlap score 0-1 between use case and a tool/script name."""
    label_tokens = _tokenize_name(use_case_label)
    keyword_set = set(kw.lower() for kw in keywords)
    name_tokens = _tokenize_name(name)
    if not name_tokens:
        return 0.0
    combined = label_tokens | keyword_set
    if not combined:
        return 0.0
    count = 0
    for nt in name_tokens:
        if nt in combined:
            count += 1
        else:
            for c in combined:
                if len(c) >= 2 and (c in nt or nt in c):
                    count += 1
                    break
    return min(1.0, count / len(name_tokens))


def map_use_case_to_tools_and_scripts(
    use_case: UseCaseExtraction,
    tool_names: list[str],
    script_names: list[str],
    min_score: float = 0.2,
) -> tuple[list[tuple[str, str, float]], list[tuple[str, str, float]]]:
    """Map a use case to relevant tools and scripts by keyword overlap.

    Returns:
        (tool_matches, script_matches) where each match is (name, type, score).
    """
    tool_matches: list[tuple[str, str, float]] = []
    script_matches: list[tuple[str, str, float]] = []
    for name in tool_names:
        score = _overlap_score(
            use_case.use_case_label,
            use_case.keywords,
            name,
        )
        if score >= min_score:
            tool_matches.append((name, "tool", round(score, 4)))
    for name in script_names:
        score = _overlap_score(
            use_case.use_case_label,
            use_case.keywords,
            name,
        )
        if score >= min_score:
            script_matches.append((name, "script", round(score, 4)))
    tool_matches.sort(key=lambda x: -x[2])
    script_matches.sort(key=lambda x: -x[2])
    return (tool_matches, script_matches)
