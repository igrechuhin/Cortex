"""Compare captured scripts against existing tools and scripts."""

import re

from cortex.script_analysis.models import GapAnalysis, UseCaseExtraction


def _tokenize_name(name: str) -> set[str]:
    """Tokenize a name into lowercase words (split on _ and non-alpha)."""
    normalized = name.lower().replace("-", " ").replace("_", " ")
    return set(re.findall(r"[a-z0-9]+", normalized))


def _token_overlaps(combined: set[str], name_tokens: set[str]) -> int:
    """Count name tokens that overlap combined (exact or substring)."""
    count = 0
    for nt in name_tokens:
        if nt in combined:
            count += 1
        else:
            for c in combined:
                if len(c) >= 2 and (c in nt or nt in c):
                    count += 1
                    break
    return count


def _overlap_score(use_case_label: str, keywords: list[str], name: str) -> float:
    """Return overlap score 0-1 between use case and a tool/script name."""
    label_tokens = _tokenize_name(use_case_label)
    keyword_set = set(kw.lower() for kw in keywords)
    name_tokens = _tokenize_name(name)
    if not name_tokens:
        return 0.0
    combined = label_tokens | keyword_set
    if not combined:
        return 0.0
    overlap_count = _token_overlaps(combined, name_tokens)
    return min(1.0, overlap_count / len(name_tokens))


def _find_overlapping(
    use_case: UseCaseExtraction,
    names: list[str],
    threshold: float = 0.3,
) -> list[str]:
    """Return names that overlap with the use case above threshold."""
    overlapping: list[str] = []
    for name in names:
        score = _overlap_score(
            use_case.use_case_label,
            use_case.keywords,
            name,
        )
        if score >= threshold:
            overlapping.append(name)
    return overlapping


def _build_gap_result(
    existing_tools: list[str],
    existing_scripts: list[str],
) -> GapAnalysis:
    """Build GapAnalysis from overlapping tool/script lists."""
    if existing_tools or existing_scripts:
        reason_parts: list[str] = []
        if existing_tools:
            reason_parts.append(f"Overlapping tools: {', '.join(existing_tools[:5])}")
        if existing_scripts:
            reason_parts.append(
                f"Overlapping scripts: {', '.join(existing_scripts[:5])}"
            )
        return GapAnalysis(
            existing_tool_names=existing_tools,
            existing_script_names=existing_scripts,
            gap_reason="; ".join(reason_parts),
            is_gap=False,
        )
    return GapAnalysis(
        existing_tool_names=[],
        existing_script_names=[],
        gap_reason="No existing tool or script name overlaps with this use case",
        is_gap=True,
    )


def analyze_gap(
    use_case: UseCaseExtraction,
    known_tool_names: list[str],
    known_script_names: list[str],
    overlap_threshold: float = 0.3,
) -> GapAnalysis:
    """Compare use case to known tools/scripts; return GapAnalysis (is_gap, reason)."""
    existing_tools = _find_overlapping(
        use_case, known_tool_names, threshold=overlap_threshold
    )
    existing_scripts = _find_overlapping(
        use_case, known_script_names, threshold=overlap_threshold
    )
    return _build_gap_result(existing_tools, existing_scripts)
