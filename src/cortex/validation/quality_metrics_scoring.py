"""Freshness and structure scoring helpers for quality metrics."""

import re
from datetime import datetime

from cortex.core.constants import ORPHAN_FILE_THRESHOLD_DAYS
from cortex.core.models import DetailedFileMetadata, ModelDict
from cortex.validation.models import FileMetadataForQuality

from .quality_metrics_coercion import coerce_file_metadata


def score_by_age(days_old: int) -> float:
    """Calculate freshness score based on age in days.

    Args:
        days_old: Number of days since last modification

    Returns:
        Freshness score 0-100
    """
    if days_old <= 7:
        return 100.0
    if days_old <= ORPHAN_FILE_THRESHOLD_DAYS:
        return 80.0
    if days_old <= 90:
        return 60.0
    if days_old <= 180:
        return 40.0
    return 20.0


def parse_last_modified_date(last_modified: str) -> int:
    """Parse last modified date and calculate days old.

    Args:
        last_modified: ISO timestamp string

    Returns:
        Number of days since last modification
    """
    last_mod_dt = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
    return (datetime.now() - last_mod_dt).days


def calculate_file_freshness_score(
    metadata: FileMetadataForQuality, now: datetime
) -> float:
    """Calculate freshness score for a single file."""
    if not metadata.last_modified:
        return 50.0

    try:
        last_mod_dt = datetime.fromisoformat(
            metadata.last_modified.replace("Z", "+00:00")
        )
        days_old = (now - last_mod_dt).days
        return score_by_age(days_old)
    except Exception:
        return 50.0


def calculate_file_structure_score(content: str) -> float:
    """Calculate structure score for a single file based on heading hierarchy."""
    score = 100.0
    lines = content.split("\n")
    prev_level = 0

    for line in lines:
        match = re.match(r"^(#{1,})\s+(.+)$", line)
        if match:
            level = len(match.group(1))

            if prev_level > 0 and level > prev_level + 1:
                score -= 10

            if level > 4:
                score -= 5

            prev_level = level

    return max(0.0, score)


def calculate_file_freshness_from_metadata(
    metadata: DetailedFileMetadata | FileMetadataForQuality | ModelDict,
) -> float:
    """Calculate freshness for a single file from metadata."""
    meta = coerce_file_metadata(metadata)
    if not meta.last_modified:
        return 50.0

    try:
        days_old = parse_last_modified_date(meta.last_modified)
        return score_by_age(days_old)
    except Exception:
        return 50.0


def calculate_token_efficiency_score(
    metadata_map: dict[str, FileMetadataForQuality],
) -> float:
    """Calculate token efficiency score 0-100 from metadata map."""
    if not metadata_map:
        return 100.0

    total_tokens = sum(meta.token_count for meta in metadata_map.values())

    if 20000 <= total_tokens <= 80000:
        return 100.0
    if total_tokens < 20000:
        ratio = total_tokens / 20000
        return 50 + (ratio * 50)

    excess = total_tokens - 80000
    penalty = min(50, (excess / 1000) * 2)
    return max(50.0, 100 - penalty)


def calculate_weighted_score(category_scores: dict[str, float]) -> int:
    """Calculate weighted overall score from category scores."""
    from cortex.core.constants import (
        QUALITY_WEIGHT_COMPLETENESS,
        QUALITY_WEIGHT_CONSISTENCY,
        QUALITY_WEIGHT_EFFICIENCY,
        QUALITY_WEIGHT_FRESHNESS,
        QUALITY_WEIGHT_STRUCTURE,
    )

    weights = {
        "completeness": QUALITY_WEIGHT_COMPLETENESS,
        "consistency": QUALITY_WEIGHT_CONSISTENCY,
        "freshness": QUALITY_WEIGHT_FRESHNESS,
        "structure": QUALITY_WEIGHT_STRUCTURE,
        "token_efficiency": QUALITY_WEIGHT_EFFICIENCY,
    }
    return int(
        category_scores["completeness"] * weights["completeness"]
        + category_scores["consistency"] * weights["consistency"]
        + category_scores["freshness"] * weights["freshness"]
        + category_scores["structure"] * weights["structure"]
        + category_scores["token_efficiency"] * weights["token_efficiency"]
    )
