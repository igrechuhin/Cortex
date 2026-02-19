"""
Phase 4: Metadata Building Helpers

Helper functions for building metadata structures for context loading.
"""

from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict
from cortex.core.session_logger import log_load_context_call
from cortex.optimization.agent_roles import AgentRole, get_role_profile


def calculate_metadata_relevance_scores(
    task_description: str,
    files_metadata: dict[str, ModelDict],
    agent_role: AgentRole | None = None,
) -> dict[str, float]:
    """Calculate relevance scores for files using metadata only.

    Args:
        task_description: Task description
        files_metadata: File metadata dictionary
        agent_role: Optional agent role for role-based scoring adjustments

    Returns:
        Dictionary mapping file names to relevance scores
    """
    task_keywords = _extract_task_keywords(task_description)
    relevance_scores = _calculate_base_scores(task_keywords, files_metadata)

    # Apply role-based adjustments if agent_role is provided
    if agent_role is not None:
        relevance_scores = _apply_role_based_adjustments(relevance_scores, agent_role)

    return relevance_scores


def _extract_task_keywords(task_description: str) -> list[str]:
    """Extract keywords from task description."""
    import re

    return [
        w.lower()
        for w in re.findall(r"\b[a-z0-9][-a-z0-9]*\b", task_description.lower())
        if len(w) > 2
    ]


def _calculate_base_scores(
    task_keywords: list[str], files_metadata: dict[str, ModelDict]
) -> dict[str, float]:
    """Calculate base relevance scores before role adjustments."""
    relevance_scores: dict[str, float] = {}
    for file_name, metadata in files_metadata.items():
        score = _score_file(file_name, metadata, task_keywords)
        relevance_scores[file_name] = min(score, 1.0)
    return relevance_scores


def _score_file(file_name: str, metadata: ModelDict, task_keywords: list[str]) -> float:
    """Score a single file's metadata for relevance."""
    score = 0.0
    file_name_lower = file_name.lower()

    # Filename keyword match
    for keyword in task_keywords:
        if keyword in file_name_lower:
            score += 0.3
            break

    # Section heading keyword match
    sections_list = metadata.get("sections", [])
    if isinstance(sections_list, list):
        for section in sections_list[:5]:
            if isinstance(section, dict):
                heading = str(section.get("heading", "")).lower()
                for keyword in task_keywords:
                    if keyword in heading:
                        score += 0.2
                        break

    # Recency bonus
    if metadata.get("last_modified"):
        score += 0.1

    return score


def _apply_role_based_adjustments(
    relevance_scores: dict[str, float], agent_role: AgentRole
) -> dict[str, float]:
    """Apply role-based adjustments to relevance scores.

    Files in the role's context_focus get a boost, while files not
    in the focus get a slight penalty. This helps prioritize the most
    relevant files for each agent role.

    Args:
        relevance_scores: Base relevance scores
        agent_role: Agent role to use for adjustments

    Returns:
        Adjusted relevance scores
    """
    profile = get_role_profile(agent_role)
    adjusted_scores = relevance_scores.copy()

    # Boost scores for files in the role's context focus
    for file_name in adjusted_scores:
        if file_name in profile.context_focus:
            # Boost by 0.3, capped at 1.0
            adjusted_scores[file_name] = min(adjusted_scores[file_name] + 0.3, 1.0)
        elif adjusted_scores[file_name] > 0.0:
            # Apply slight penalty to files not in focus (0.9x multiplier)
            # but only if they have some relevance already
            adjusted_scores[file_name] *= 0.9

    return adjusted_scores


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


def extract_selected_files_from_map(
    files_map: list[dict[str, object]],
) -> tuple[list[str], dict[str, list[str]]]:
    """Extract selected files and sections from files_map."""
    selected_files: list[str] = []
    selected_sections: dict[str, list[str]] = {}
    for file_entry in files_map:
        file_name_raw = file_entry.get("file_name", "")
        file_name = str(file_name_raw) if file_name_raw else ""
        if file_name:
            selected_files.append(file_name)
            sections_raw = file_entry.get("sections", [])
            if isinstance(sections_raw, list) and sections_raw:
                section_strings: list[str] = []
                for section_item_raw in cast(list[object], sections_raw):
                    if section_item_raw is not None:
                        section_strings.append(str(section_item_raw))
                selected_sections[file_name] = section_strings
    return selected_files, selected_sections


def calculate_metadata_tokens(files_map: list[dict[str, object]]) -> int:
    """Calculate total tokens from metadata files."""
    return sum(
        (
            int(tokens_val)
            if isinstance(tokens_val := file_entry.get("total_tokens"), (int, str))
            else 0
        )
        for file_entry in files_map[:10]
    )


def extract_metadata_logging_info(
    files_map: list[dict[str, object]],
    always_loaded_content: dict[str, str],
    always_load_sections: dict[str, list[str]],
    files_metadata: dict[str, ModelDict],
    always_loaded_tokens: int,
    token_budget: int,
) -> tuple[list[str], dict[str, list[str]], list[str], int, float]:
    """Extract logging information from metadata-only context.

    Returns:
        Tuple of (selected_files, selected_sections, excluded_files, total_tokens, utilization)
    """
    selected_files, selected_sections = extract_selected_files_from_map(files_map)
    selected_files.extend(list(always_loaded_content.keys()))
    for file_name, sections_dict in always_load_sections.items():
        if file_name not in selected_sections:
            selected_sections[file_name] = sections_dict
    all_metadata_files = set(files_metadata.keys())
    excluded_files = list(all_metadata_files - set(selected_files))
    metadata_tokens = calculate_metadata_tokens(files_map)
    total_tokens = metadata_tokens + always_loaded_tokens
    utilization = round(total_tokens / token_budget, 2) if token_budget > 0 else 0.0
    return selected_files, selected_sections, excluded_files, total_tokens, utilization


def _prepare_logging_params(
    files_map: list[dict[str, object]],
    always_loaded_content: dict[str, str],
    always_load_sections: dict[str, list[str]],
    files_metadata: dict[str, ModelDict],
    always_loaded_tokens: int,
    token_budget: int,
) -> tuple[list[str], dict[str, list[str]], list[str], int, float]:
    """Prepare logging parameters from metadata context."""
    return extract_metadata_logging_info(
        files_map,
        always_loaded_content,
        always_load_sections,
        files_metadata,
        always_loaded_tokens,
        token_budget,
    )


def log_metadata_context_call(project_root: Path, task_description: str, token_budget: int, strategy: str, files_map: list[dict[str, object]], always_loaded_content: dict[str, str], always_load_sections: dict[str, list[str]], files_metadata: dict[str, ModelDict], always_loaded_tokens: int, relevance_scores: dict[str, float], agent_role: AgentRole | None) -> None:
    """Log metadata-only context loading call."""
    selected_files, selected_sections, excluded_files, total_tokens, utilization = _prepare_logging_params(files_map, always_loaded_content, always_load_sections, files_metadata, always_loaded_tokens, token_budget)
    log_load_context_call(project_root, task_description, token_budget, strategy, selected_files, selected_sections, total_tokens, utilization, excluded_files, relevance_scores, agent_role.value if agent_role else None)
