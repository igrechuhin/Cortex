"""
Phase 4: Metadata Building Helpers

Helper functions for building metadata structures for context loading.
"""

from cortex.core.models import JsonValue, ModelDict


def calculate_metadata_relevance_scores(
    task_description: str, files_metadata: dict[str, ModelDict]
) -> dict[str, float]:
    """Calculate relevance scores for files using metadata only.

    Args:
        task_description: Task description
        files_metadata: File metadata dictionary

    Returns:
        Dictionary mapping file names to relevance scores
    """
    import re

    task_keywords = [
        w.lower()
        for w in re.findall(r"\b[a-z0-9][-a-z0-9]*\b", task_description.lower())
        if len(w) > 2
    ]

    relevance_scores: dict[str, float] = {}
    for file_name, metadata in files_metadata.items():
        score = 0.0
        file_name_lower = file_name.lower()
        for keyword in task_keywords:
            if keyword in file_name_lower:
                score += 0.3
                break

        sections_list = metadata.get("sections", [])
        if isinstance(sections_list, list):
            for section in sections_list[:5]:
                if isinstance(section, dict):
                    heading = str(section.get("heading", "")).lower()
                    for keyword in task_keywords:
                        if keyword in heading:
                            score += 0.2
                            break

        if metadata.get("last_modified"):
            score += 0.1

        relevance_scores[file_name] = min(score, 1.0)

    return relevance_scores


def extract_sections_from_metadata(
    sections_list: object,
) -> list[dict[str, object]]:
    """Extract sections list from metadata.

    Args:
        sections_list: Sections list from metadata

    Returns:
        List of section dictionaries
    """
    from typing import cast

    from cortex.core.models import ModelDict

    sections: list[dict[str, object]] = []
    if isinstance(sections_list, list):
        for section_item in sections_list:  # type: ignore[reportUnknownVariableType]
            if isinstance(section_item, dict):
                section_dict = cast(ModelDict, section_item)
                heading_raw: JsonValue = section_dict.get("heading", "")
                heading = str(heading_raw) if heading_raw else ""

                token_count_raw: JsonValue = section_dict.get("token_count", 0)
                tokens = (
                    int(token_count_raw)
                    if isinstance(token_count_raw, (int, str))
                    else 0
                )

                level_raw: JsonValue = section_dict.get("level", 2)
                level = int(level_raw) if isinstance(level_raw, (int, str)) else 2

                sections.append(
                    {
                        "heading": heading,
                        "tokens": tokens,
                        "level": level,
                    }
                )
    return sections


def build_file_entry(
    file_name: str,
    metadata: ModelDict,
    relevance_scores: dict[str, float],
) -> tuple[dict[str, object], int]:
    """Build a single file entry for files map.

    Args:
        file_name: File name
        metadata: File metadata
        relevance_scores: Relevance scores dictionary

    Returns:
        Tuple of (file_entry, file_tokens)
    """
    sections = extract_sections_from_metadata(metadata.get("sections", []))

    token_count_raw = metadata.get("token_count", 0)
    file_tokens = int(token_count_raw) if isinstance(token_count_raw, (int, str)) else 0

    relevance_score_raw = relevance_scores.get(file_name, 0.0)
    relevance_score = float(relevance_score_raw)  # type: ignore[arg-type]

    last_modified_raw = metadata.get("last_modified", "")
    last_modified = str(last_modified_raw) if last_modified_raw else ""

    file_entry: dict[str, object] = {
        "name": file_name,
        "total_tokens": file_tokens,
        "last_modified": last_modified,
        "relevance_score": round(relevance_score, 2),
        "sections": sections,
    }

    return file_entry, file_tokens


def build_files_map_from_metadata(
    files_metadata: dict[str, ModelDict], relevance_scores: dict[str, float]
) -> tuple[list[dict[str, object]], int]:
    """Build files map from metadata and relevance scores.

    Args:
        files_metadata: File metadata dictionary
        relevance_scores: Relevance scores dictionary

    Returns:
        Tuple of (files_map, total_tokens_available)
    """
    files_map: list[dict[str, object]] = []
    total_tokens_available = 0

    for file_name, metadata in files_metadata.items():
        file_entry, file_tokens = build_file_entry(
            file_name, metadata, relevance_scores
        )
        files_map.append(file_entry)
        total_tokens_available += file_tokens

    def get_relevance_for_sort(x: dict[str, object]) -> float:
        score_raw = x.get("relevance_score", 0.0)
        return float(score_raw) if isinstance(score_raw, (int, float)) else 0.0

    files_map.sort(key=get_relevance_for_sort, reverse=True)
    return files_map, total_tokens_available
