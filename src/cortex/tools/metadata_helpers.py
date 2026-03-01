"""
Phase 4: Metadata Building Helpers

Helper functions for building metadata structures for context loading.
"""

from typing import cast

from cortex.core.models import JsonValue, ModelDict, SectionMetadata
from cortex.optimization.agent_roles import AgentRole, get_role_profile
from cortex.tools.context_models import FileMapEntry, SectionSummary


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
    sections_list: list[SectionMetadata] | list[ModelDict] | object,
) -> list[SectionSummary]:
    """Extract sections list from metadata.

    Args:
        sections_list: Sections list from metadata (list of SectionMetadata,
            list of section dicts, or other; only lists are processed).

    Returns:
        List of section summary models
    """
    sections: list[SectionSummary] = []
    if not isinstance(sections_list, list):
        return sections
    normalized: list[ModelDict] = []
    items_typed = cast(list[SectionMetadata | ModelDict], sections_list)
    for item in items_typed:
        if isinstance(item, SectionMetadata):
            normalized.append(
                cast(ModelDict, item.model_dump(mode="json", by_alias=True))
            )
        else:
            normalized.append(item)
    for section_item in normalized:
        heading_raw: JsonValue = section_item.get("heading", "")
        heading = str(heading_raw) if heading_raw else ""

        token_count_raw: JsonValue = section_item.get("token_count", 0)
        tokens = int(token_count_raw) if isinstance(token_count_raw, (int, str)) else 0

        level_raw: JsonValue = section_item.get("level", 2)
        level = int(level_raw) if isinstance(level_raw, (int, str)) else 2

        sections.append(SectionSummary(heading=heading, tokens=tokens, level=level))
    return sections


def build_file_entry(
    file_name: str,
    metadata: ModelDict,
    relevance_scores: dict[str, float],
) -> tuple[FileMapEntry, int]:
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

    relevance_score: float = relevance_scores.get(file_name, 0.0)

    last_modified_raw = metadata.get("last_modified", "")
    last_modified = str(last_modified_raw) if last_modified_raw else ""

    file_entry = FileMapEntry(
        name=file_name,
        total_tokens=file_tokens,
        last_modified=last_modified,
        relevance_score=round(relevance_score, 2),
        sections=sections,
    )

    return file_entry, file_tokens


def build_files_map_from_metadata(
    files_metadata: dict[str, ModelDict], relevance_scores: dict[str, float]
) -> tuple[list[FileMapEntry], int]:
    """Build files map from metadata and relevance scores.

    Args:
        files_metadata: File metadata dictionary
        relevance_scores: Relevance scores dictionary

    Returns:
        Tuple of (files_map, total_tokens_available)
    """
    files_map: list[FileMapEntry] = []
    total_tokens_available = 0

    for file_name, metadata in files_metadata.items():
        file_entry, file_tokens = build_file_entry(
            file_name, metadata, relevance_scores
        )
        files_map.append(file_entry)
        total_tokens_available += file_tokens

    files_map.sort(key=lambda x: x.relevance_score, reverse=True)
    return files_map, total_tokens_available


def extract_selected_files_from_map(
    files_map: list[FileMapEntry],
) -> tuple[list[str], dict[str, list[str]]]:
    """Extract selected files and sections from files_map."""
    selected_files: list[str] = []
    selected_sections: dict[str, list[str]] = {}
    for file_entry in files_map:
        file_name = file_entry.name
        if file_name:
            selected_files.append(file_name)
            if file_entry.sections:
                selected_sections[file_name] = [
                    s.heading for s in file_entry.sections if s.heading
                ]
    return selected_files, selected_sections


def calculate_metadata_tokens(files_map: list[FileMapEntry]) -> int:
    """Calculate total tokens from metadata files."""
    return sum(file_entry.total_tokens for file_entry in files_map[:10])


def summarize_files_content(
    files_content: dict[str, str], files_metadata: dict[str, ModelDict]
) -> dict[str, str]:
    """Summarize file contents to first paragraph + section headings.

    Args:
        files_content: Full file contents
        files_metadata: File metadata including sections

    Returns:
        Dictionary with summarized content (first paragraph + headings)
    """
    summarized: dict[str, str] = {}
    for file_name, content in files_content.items():
        lines = content.split("\n")
        summary_parts: list[str] = []
        first_paragraph_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if first_paragraph_lines:
                    break
                continue
            if stripped.startswith("#"):
                break
            first_paragraph_lines.append(line)
        if first_paragraph_lines:
            summary_parts.append("\n".join(first_paragraph_lines))
        metadata = files_metadata.get(file_name, {})
        sections_list = metadata.get("sections", [])
        if isinstance(sections_list, list) and sections_list:
            summary_parts.append("\n\n## Sections:")
            for section in sections_list[:10]:
                if isinstance(section, dict):
                    heading = str(section.get("heading", ""))
                    if heading:
                        summary_parts.append(heading)
        summarized[file_name] = "\n".join(summary_parts) if summary_parts else content
    return summarized
