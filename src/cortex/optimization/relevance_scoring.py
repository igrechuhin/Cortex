"""
Relevance scoring strategies (keyword, dependency, recency, section parsing).

Pure computation functions used by RelevanceScorer. No caching or orchestration.
"""

import math
import re
from datetime import datetime

from cortex.core.dependency_graph import DependencyGraph
from cortex.optimization.models import FileMetadataForScoring


def calculate_keyword_score(task_keywords: list[str], content: str) -> float:
    """
    Calculate TF-IDF based keyword score.

    Args:
        task_keywords: Keywords from task description
        content: File or section content

    Returns:
        Score between 0.0 and 1.0
    """
    if not task_keywords or not content:
        return 0.0

    content_lower: str = content.lower()
    keyword_counts: dict[str, int] = {}
    for keyword in task_keywords:
        keyword_counts[keyword] = content_lower.count(keyword)

    total_words = len(content_lower.split())
    if total_words == 0:
        return 0.0

    tf_scores: dict[str, float] = {
        kw: count / total_words for kw, count in keyword_counts.items()
    }
    idf_scores: dict[str, float] = {}
    for i, kw in enumerate(task_keywords):
        idf_scores[kw] = 1.0 / (1.0 + math.log(1 + i))

    tfidf_scores: dict[str, float] = {
        kw: tf_scores[kw] * idf_scores[kw] for kw in task_keywords
    }
    total_tfidf: float = sum(tfidf_scores.values())
    score = 1.0 - math.exp(-total_tfidf * 100)
    return min(score, 1.0)


def calculate_keyword_scores_for_files(
    task_keywords: list[str], files_content: dict[str, str]
) -> dict[str, float]:
    """Calculate keyword scores for all files."""
    return {
        file_name: calculate_keyword_score(task_keywords, content)
        for file_name, content in files_content.items()
    }


def compute_dependency_scores(
    keyword_scores: dict[str, float],
    dependency_graph: DependencyGraph,
) -> dict[str, float]:
    """
    Compute dependency scores from keyword scores and graph (no caching).

    Files that are dependencies of high-scoring files get boosted.
    """
    dependency_scores: dict[str, float] = {
        file_name: 0.0 for file_name in keyword_scores.keys()
    }

    for file_name, keyword_score in keyword_scores.items():
        if keyword_score < 0.3:
            continue
        deps: list[str] = dependency_graph.get_dependencies(file_name)
        boost = keyword_score * 0.7
        for dep in deps:
            if dep in dependency_scores:
                dependency_scores[dep] = max(dependency_scores[dep], boost)

    for file_name, keyword_score in keyword_scores.items():
        if keyword_score < 0.3:
            continue
        dependents: list[str] = dependency_graph.get_dependents(file_name)
        if dependents:
            boost = keyword_score * 0.5
            dependency_scores[file_name] = max(dependency_scores[file_name], boost)

    return dependency_scores


def calculate_recency_score(metadata: FileMetadataForScoring) -> float:
    """
    Score based on how recently the file was modified.

    Returns:
        Score between 0.0 and 1.0
    """
    last_modified = metadata.last_modified
    if not last_modified:
        return 0.5
    try:
        last_modified_str: str = str(last_modified)
        modified_time = datetime.fromisoformat(last_modified_str.replace("Z", "+00:00"))
        now = datetime.now(modified_time.tzinfo)
        age_days: float = (now - modified_time).total_seconds() / 86400
        score: float = math.exp(-age_days / 45.0)
        return min(score, 1.0)
    except (ValueError, AttributeError):
        return 0.5


def calculate_recency_scores_for_files(
    files_metadata: dict[str, FileMetadataForScoring],
) -> dict[str, float]:
    """Calculate recency scores for all files."""
    return {
        file_name: calculate_recency_score(metadata)
        for file_name, metadata in files_metadata.items()
    }


def parse_sections(content: str) -> dict[str, str]:
    """
    Parse markdown sections from content.

    Returns:
        Dict mapping section names to section content
    """
    sections: dict[str, str] = {}
    current_section: str = "preamble"
    current_content: list[str] = []
    lines: list[str] = content.split("\n")

    for line in lines:
        if line.startswith("#"):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            heading_match = re.match(r"^#+\s+(.+)$", line)
            if heading_match:
                current_section = heading_match.group(1).strip()
                current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections[current_section] = "\n".join(current_content)
    return sections
