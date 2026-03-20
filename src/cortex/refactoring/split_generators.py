"""
Split Point Generators

Functions that generate split points using different strategies (by topics,
by sections, by size). Extracted from SplitRecommender to keep files focused.
"""

from __future__ import annotations

from typing import Protocol, cast

from cortex.core.models import JsonValue, ModelDict

from .split_models import SplitPoint


class SplitAnalyzerProtocol(Protocol):
    """Protocol for the subset of SplitAnalyzer used by split generators and recommender."""

    max_file_size: int
    max_sections: int
    min_section_independence: float

    def parse_file_structure(self, content: str) -> list[ModelDict]: ...

    async def should_split_file(
        self,
        file_path: str,
        content: str,
        token_count: int,
        sections: list[ModelDict],
    ) -> tuple[bool, list[str]]: ...

    def determine_split_strategy(
        self, token_count: int, section_count: int, sections: list[ModelDict]
    ) -> str: ...

    def calculate_section_independence(
        self,
        section: ModelDict,
        sections: list[ModelDict],
        content: str,
    ) -> float: ...

    def group_related_sections(
        self, sections: list[ModelDict]
    ) -> dict[str, list[ModelDict]]: ...

    def calculate_group_independence(
        self,
        group_sections: list[ModelDict],
        sections: list[ModelDict],
        content: str,
    ) -> float: ...


class SplitRecommenderProtocol(Protocol):
    """Protocol for the subset of SplitRecommender used by split_generators."""

    min_section_independence: float
    max_file_size: int
    analyzer: SplitAnalyzerProtocol

    def get_section_str(
        self, section: ModelDict, key: str, default: str = ""
    ) -> str: ...
    def get_section_int(
        self, section: ModelDict, key: str, default: int = 0
    ) -> int: ...
    def get_section_content(self, section: ModelDict) -> str: ...
    def generate_split_filename(
        self, original_file: str, section_heading: str
    ) -> str: ...


async def generate_split_by_topics(
    recommender: SplitRecommenderProtocol,
    file_path: str,
    content: str,
    sections: list[ModelDict],
) -> list[SplitPoint]:
    """Generate split points by top-level topics."""
    split_points: list[SplitPoint] = []
    top_level_sections = [
        s for s in sections if recommender.get_section_int(s, "level", 0) == 1
    ]

    for section in top_level_sections:
        independence = recommender.analyzer.calculate_section_independence(
            section, sections, content
        )

        if independence >= recommender.min_section_independence:
            section_heading = recommender.get_section_str(section, "heading", "")
            start_line = recommender.get_section_int(section, "start_line", 0)
            end_line = recommender.get_section_int(section, "end_line", 0)
            section_content = recommender.get_section_content(section)

            split_point = SplitPoint(
                section_heading=section_heading,
                start_line=start_line,
                end_line=end_line,
                token_count=len(section_content) // 4,
                independence_score=independence,
                suggested_filename=recommender.generate_split_filename(
                    file_path, section_heading
                ),
            )
            split_points.append(split_point)

    return split_points


async def generate_split_by_sections(
    recommender: SplitRecommenderProtocol,
    file_path: str,
    content: str,
    sections: list[ModelDict],
) -> list[SplitPoint]:
    """Generate split points by grouping related sections."""
    split_points: list[SplitPoint] = []
    section_groups_raw = recommender.analyzer.group_related_sections(sections)

    for group_name, group_sections_raw in section_groups_raw.items():
        group_sections = normalize_group_sections(group_sections_raw)
        if not group_sections:
            continue

        split_point = create_split_point_from_group(
            recommender, file_path, content, sections, group_name, group_sections
        )
        if split_point:
            split_points.append(split_point)

    return split_points


def create_split_point_from_group(
    recommender: SplitRecommenderProtocol,
    file_path: str,
    content: str,
    sections: list[ModelDict],
    group_name: str,
    group_sections: list[ModelDict],
) -> SplitPoint | None:
    """Create split point from section group."""
    combined_content = "\n".join(
        recommender.get_section_content(s) for s in group_sections
    )
    start_line = recommender.get_section_int(group_sections[0], "start_line", 0)
    end_line = recommender.get_section_int(group_sections[-1], "end_line", 0)

    independence = recommender.analyzer.calculate_group_independence(
        group_sections, sections, content
    )

    if independence < recommender.min_section_independence:
        return None

    group_name_str = str(group_name)
    return SplitPoint(
        section_heading=group_name_str,
        start_line=start_line,
        end_line=end_line,
        token_count=len(combined_content) // 4,
        independence_score=independence,
        suggested_filename=recommender.generate_split_filename(
            file_path, group_name_str
        ),
    )


async def generate_split_by_size(
    recommender: SplitRecommenderProtocol,
    file_path: str,
    sections: list[ModelDict],
) -> list[SplitPoint]:
    """Generate split points by size, creating roughly equal chunks."""
    split_points: list[SplitPoint] = []
    target_chunk_size = recommender.max_file_size
    current_chunk_sections: list[ModelDict] = []
    current_chunk_tokens = 0

    for section in sections:
        section_content = recommender.get_section_content(section)
        section_tokens = len(section_content) // 4

        if (
            current_chunk_tokens + section_tokens > target_chunk_size
            and current_chunk_sections
        ):
            split_point = create_chunk_split_point(
                recommender, file_path, current_chunk_sections, current_chunk_tokens
            )
            split_points.append(split_point)

            # Start new chunk
            current_chunk_sections = [section]
            current_chunk_tokens = section_tokens
        else:
            current_chunk_sections.append(section)
            current_chunk_tokens += section_tokens

    # Add last chunk
    if current_chunk_sections:
        split_point = create_chunk_split_point(
            recommender, file_path, current_chunk_sections, current_chunk_tokens
        )
        split_points.append(split_point)

    return split_points


def create_chunk_split_point(
    recommender: SplitRecommenderProtocol,
    file_path: str,
    chunk_sections: list[ModelDict],
    chunk_tokens: int,
) -> SplitPoint:
    """Create a split point for a size-based chunk."""
    chunk_heading = recommender.get_section_str(chunk_sections[0], "heading", "")
    start_line = recommender.get_section_int(chunk_sections[0], "start_line", 0)
    end_line = recommender.get_section_int(chunk_sections[-1], "end_line", 0)

    return SplitPoint(
        section_heading=chunk_heading,
        start_line=start_line,
        end_line=end_line,
        token_count=chunk_tokens,
        independence_score=0.7,  # Moderate independence for size-based splits
        suggested_filename=recommender.generate_split_filename(
            file_path, chunk_heading
        ),
    )


async def generate_split_points(
    recommender: SplitRecommenderProtocol,
    file_path: str,
    content: str,
    sections: list[ModelDict],
    strategy: str,
) -> list[SplitPoint]:
    """
    Generate specific split points based on strategy.

    Uses analyzer for independence calculations.
    """
    if strategy == "by_topics":
        return await generate_split_by_topics(recommender, file_path, content, sections)
    elif strategy == "by_sections":
        return await generate_split_by_sections(
            recommender, file_path, content, sections
        )
    elif strategy == "by_size":
        return await generate_split_by_size(recommender, file_path, sections)
    else:
        return []


def normalize_group_sections(
    group_sections_raw: JsonValue | list[ModelDict],
) -> list[ModelDict]:
    """Normalize group sections to a list of dictionaries.

    Args:
        group_sections_raw: Raw group sections from analyzer

    Returns:
        Normalized list of section dictionaries
    """
    if isinstance(group_sections_raw, list):
        return [cast(ModelDict, s) for s in group_sections_raw if isinstance(s, dict)]
    else:
        return (
            [cast(ModelDict, group_sections_raw)]
            if isinstance(group_sections_raw, dict)
            else []
        )
