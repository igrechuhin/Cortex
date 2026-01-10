"""
Phase 4: Relevance Scoring Operations

This module contains the implementation logic for the get_relevance_scores tool.
"""

import json
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.manager_utils import get_manager
from cortex.optimization.relevance_scorer import RelevanceScorer


async def get_relevance_scores_impl(
    mgrs: dict[str, object],
    task_description: str,
    include_sections: bool,
) -> str:
    """Implementation logic for get_relevance_scores tool.

    Args:
        mgrs: Dictionary of managers
        task_description: Task description
        include_sections: Whether to include section-level scores

    Returns:
        JSON string with relevance scores
    """
    relevance_scorer = await get_manager(mgrs, "relevance_scorer", RelevanceScorer)
    metadata_index = cast(MetadataIndex, mgrs["index"])
    fs_manager = cast(FileSystemManager, mgrs["fs"])

    # Read files and metadata
    files_content, files_metadata = await _read_files_for_scoring(
        metadata_index, fs_manager
    )

    # Score files
    file_scores = await relevance_scorer.score_files(
        task_description=task_description,
        files_content=files_content,
        files_metadata=files_metadata,
    )

    # Optionally score sections
    section_scores = await _score_sections_if_needed(
        include_sections, relevance_scorer, task_description, files_content
    )

    # Build and return result
    return _build_relevance_scores_result(
        task_description,
        cast(dict[str, dict[str, object]], file_scores),
        section_scores,
        include_sections,
    )


async def _read_files_for_scoring(
    metadata_index: MetadataIndex, fs_manager: FileSystemManager
) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
    """Read files and metadata for scoring.

    Args:
        metadata_index: Metadata index manager
        fs_manager: File system manager

    Returns:
        Tuple of (files_content, files_metadata)
    """
    all_files = await metadata_index.list_all_files()

    files_content: dict[str, str] = {}
    files_metadata: dict[str, dict[str, object]] = {}

    for file_name in all_files:
        try:
            file_path = metadata_index.memory_bank_dir / file_name
            content, _ = await fs_manager.read_file(file_path)
            files_content[file_name] = content

            metadata = await metadata_index.get_file_metadata(file_name)
            if metadata:
                files_metadata[file_name] = metadata

        except FileNotFoundError:
            continue

    return files_content, files_metadata


async def _score_sections_if_needed(
    include_sections: bool,
    relevance_scorer: RelevanceScorer,
    task_description: str,
    files_content: dict[str, str],
) -> dict[str, object]:
    """Score sections if include_sections is True.

    Args:
        include_sections: Whether to score sections
        relevance_scorer: Relevance scorer instance
        task_description: Task description
        files_content: Dictionary of file contents

    Returns:
        Dictionary of section scores (empty if include_sections is False)
    """
    section_scores: dict[str, object] = {}
    if include_sections:
        for file_name_str, content_str in files_content.items():
            sections = await relevance_scorer.score_sections(
                task_description=task_description,
                file_name=file_name_str,
                content=content_str,
            )
            section_scores[file_name_str] = sections

    return section_scores


def _build_relevance_scores_result(
    task_description: str,
    file_scores: dict[str, dict[str, object]],
    section_scores: dict[str, object],
    include_sections: bool,
) -> str:
    """Build and return relevance scores result as JSON.

    Args:
        task_description: Task description
        file_scores: Dictionary of file scores
        section_scores: Dictionary of section scores
        include_sections: Whether sections were included

    Returns:
        JSON string with results
    """

    # Sort files by total score
    def get_total_score(item: tuple[str, dict[str, object]]) -> float:
        score_val = item[1].get("total_score", 0)
        if isinstance(score_val, (int, float)):
            return float(score_val)
        return 0.0

    sorted_files = sorted(file_scores.items(), key=get_total_score, reverse=True)

    result: dict[str, object] = {
        "status": "success",
        "task_description": task_description,
        "files_scored": len(sorted_files),
        "file_scores": dict(sorted_files),
    }

    if include_sections:
        result["section_scores"] = section_scores

    return json.dumps(result, indent=2)
