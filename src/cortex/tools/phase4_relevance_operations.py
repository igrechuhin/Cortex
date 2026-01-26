"""
Phase 4: Relevance Scoring Operations

This module contains the implementation logic for the get_relevance_scores tool.
"""

import json

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.models import FileMetadataForScoring
from cortex.optimization.relevance_scorer import RelevanceScorer
from cortex.tools.models import (
    FileRelevanceScore,
    GetRelevanceScoresResult,
    SectionRelevanceScore,
)


async def get_relevance_scores_impl(
    mgrs: ManagersDict,
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
    metadata_index: MetadataIndex = mgrs.index
    fs_manager: FileSystemManager = mgrs.fs

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
        file_scores,
        section_scores,
        include_sections,
    )


async def _read_files_for_scoring(
    metadata_index: MetadataIndex, fs_manager: FileSystemManager
) -> tuple[dict[str, str], dict[str, FileMetadataForScoring]]:
    """Read files and metadata for scoring.

    Args:
        metadata_index: Metadata index manager
        fs_manager: File system manager

    Returns:
        Tuple of (files_content, files_metadata)
    """
    all_files = await metadata_index.list_all_files()

    files_content: dict[str, str] = {}
    files_metadata: dict[str, FileMetadataForScoring] = {}

    for file_name in all_files:
        try:
            file_path = metadata_index.memory_bank_dir / file_name
            content, _ = await fs_manager.read_file(file_path)
            files_content[file_name] = content

            metadata_raw = await metadata_index.get_file_metadata(file_name)
            if metadata_raw:
                files_metadata[file_name] = FileMetadataForScoring.model_validate(
                    metadata_raw
                )

        except FileNotFoundError:
            continue

    return files_content, files_metadata


async def _score_sections_if_needed(
    include_sections: bool,
    relevance_scorer: RelevanceScorer,
    task_description: str,
    files_content: dict[str, str],
) -> dict[str, list[SectionRelevanceScore]]:
    """Score sections if include_sections is True.

    Args:
        include_sections: Whether to score sections
        relevance_scorer: Relevance scorer instance
        task_description: Task description
        files_content: Dictionary of file contents

    Returns:
        Dictionary mapping file names to lists of SectionRelevanceScore
    """
    section_scores: dict[str, list[SectionRelevanceScore]] = {}
    if include_sections:
        for file_name_str, content_str in files_content.items():
            sections_raw = await relevance_scorer.score_sections(
                task_description=task_description,
                file_name=file_name_str,
                content=content_str,
            )
            # Convert SectionScoreModel to SectionRelevanceScore for tool response
            section_models = [
                SectionRelevanceScore(
                    section=section.section or section.title or "",
                    score=section.score,
                    reason=section.reason,
                )
                for section in sections_raw
            ]
            section_scores[file_name_str] = section_models

    return section_scores


def _build_relevance_scores_result(
    task_description: str,
    file_scores: dict[str, dict[str, float | str]],
    section_scores: dict[str, list[SectionRelevanceScore]],
    include_sections: bool,
) -> str:
    """Build and return relevance scores result as JSON.

    Args:
        task_description: Task description
        file_scores: Dictionary of file scores (from relevance_scorer)
        section_scores: Dictionary of section scores as models
        include_sections: Whether sections were included

    Returns:
        JSON string with results
    """
    # Convert file_scores dict to FileRelevanceScore models
    file_score_models: dict[str, FileRelevanceScore] = {}
    for file_name, score_dict in file_scores.items():
        file_score_models[file_name] = FileRelevanceScore.model_validate(score_dict)

    # Sort files by total score
    sorted_files = sorted(
        file_score_models.items(),
        key=lambda item: item[1].total_score,
        reverse=True,
    )

    result = GetRelevanceScoresResult(
        task_description=task_description,
        files_scored=len(sorted_files),
        file_scores=dict(sorted_files),
        section_scores=section_scores if include_sections else None,
    )

    return json.dumps(result.model_dump(exclude_none=True), indent=2)
