"""Freshness and structure scoring helpers for quality metrics.

Score ranges: freshness 0-100 by age tiers; structure 0-100 with heading
penalties; token efficiency 0-100 by total token count bands.
"""

import re
from datetime import datetime

from cortex.core.constants import (
    ORPHAN_FILE_THRESHOLD_DAYS,
    QUALITY_FRESHNESS_DAYS_OLD,
    QUALITY_FRESHNESS_DAYS_RECENT,
    QUALITY_FRESHNESS_DAYS_VERY_OLD,
    QUALITY_FRESHNESS_SCORE_OLD,
    QUALITY_FRESHNESS_SCORE_RECENT,
    QUALITY_FRESHNESS_SCORE_STALE,
    QUALITY_FRESHNESS_SCORE_UNKNOWN,
    QUALITY_FRESHNESS_SCORE_VERY_OLD,
    QUALITY_FRESHNESS_SCORE_WITHIN_ORPHAN_DAYS,
    QUALITY_STRUCTURE_INITIAL_SCORE,
    QUALITY_STRUCTURE_MAX_HEADING_LEVEL,
    QUALITY_STRUCTURE_PENALTY_DEEP_HEADING,
    QUALITY_STRUCTURE_PENALTY_SKIP_LEVEL,
    QUALITY_TOKEN_EFFICIENCY_FLOOR,
    QUALITY_TOKEN_EFFICIENCY_MAX_PENALTY,
    QUALITY_TOKEN_EFFICIENCY_PENALTY_PER_1000,
    QUALITY_TOKEN_OPTIMAL_MAX,
    QUALITY_TOKEN_OPTIMAL_MIN,
)
from cortex.core.models import DetailedFileMetadata, ModelDict
from cortex.validation.models import FileMetadataForQuality

from .quality_metrics_coercion import coerce_file_metadata


def score_by_age(days_old: int) -> float:
    """Calculate freshness score based on age in days.

    Age tiers: ≤7 days (100), 8-30 days (80), 31-90 days (60),
    91-180 days (40), >180 days (20).

    Args:
        days_old: Number of days since last modification

    Returns:
        Freshness score 0-100

    Example:
        >>> score_by_age(3)   # Recent: 100.0
        >>> score_by_age(45)  # 31-90 days: 60.0
    """
    if days_old <= QUALITY_FRESHNESS_DAYS_RECENT:
        return QUALITY_FRESHNESS_SCORE_RECENT
    if days_old <= ORPHAN_FILE_THRESHOLD_DAYS:
        return QUALITY_FRESHNESS_SCORE_WITHIN_ORPHAN_DAYS
    if days_old <= QUALITY_FRESHNESS_DAYS_OLD:
        return QUALITY_FRESHNESS_SCORE_OLD
    if days_old <= QUALITY_FRESHNESS_DAYS_VERY_OLD:
        return QUALITY_FRESHNESS_SCORE_VERY_OLD
    return QUALITY_FRESHNESS_SCORE_STALE


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
        return QUALITY_FRESHNESS_SCORE_UNKNOWN

    try:
        last_mod_dt = datetime.fromisoformat(
            metadata.last_modified.replace("Z", "+00:00")
        )
        days_old = (now - last_mod_dt).days
        return score_by_age(days_old)
    except Exception:
        return QUALITY_FRESHNESS_SCORE_UNKNOWN


def calculate_file_structure_score(content: str) -> float:
    """Calculate structure score for a single file based on heading hierarchy.

    Penalties: skip in heading level (e.g. ## to ####) = 10; heading level > 4 = 5.
    """
    score = QUALITY_STRUCTURE_INITIAL_SCORE
    lines = content.split("\n")
    prev_level = 0

    for line in lines:
        match = re.match(r"^(#{1,})\s+(.+)$", line)
        if match:
            level = len(match.group(1))

            if prev_level > 0 and level > prev_level + 1:
                score -= QUALITY_STRUCTURE_PENALTY_SKIP_LEVEL

            if level > QUALITY_STRUCTURE_MAX_HEADING_LEVEL:
                score -= QUALITY_STRUCTURE_PENALTY_DEEP_HEADING

            prev_level = level

    return max(0.0, score)


def calculate_file_freshness_from_metadata(
    metadata: DetailedFileMetadata | FileMetadataForQuality | ModelDict,
) -> float:
    """Calculate freshness for a single file from metadata."""
    meta = coerce_file_metadata(metadata)
    if not meta.last_modified:
        return QUALITY_FRESHNESS_SCORE_UNKNOWN

    try:
        days_old = parse_last_modified_date(meta.last_modified)
        return score_by_age(days_old)
    except Exception:
        return QUALITY_FRESHNESS_SCORE_UNKNOWN


def calculate_token_efficiency_score(
    metadata_map: dict[str, FileMetadataForQuality],
) -> float:
    """Calculate token efficiency score 0-100 from metadata map.

    Optimal band: 20k-80k tokens → 100; below 20k scales 50-100; above 80k
    applies penalty (2 per 1k excess, max 50 penalty).
    """
    if not metadata_map:
        return QUALITY_STRUCTURE_INITIAL_SCORE

    total_tokens = sum(meta.token_count for meta in metadata_map.values())

    if QUALITY_TOKEN_OPTIMAL_MIN <= total_tokens <= QUALITY_TOKEN_OPTIMAL_MAX:
        return QUALITY_STRUCTURE_INITIAL_SCORE
    if total_tokens < QUALITY_TOKEN_OPTIMAL_MIN:
        ratio = total_tokens / QUALITY_TOKEN_OPTIMAL_MIN
        return QUALITY_TOKEN_EFFICIENCY_FLOOR + (ratio * QUALITY_TOKEN_EFFICIENCY_FLOOR)

    excess = total_tokens - QUALITY_TOKEN_OPTIMAL_MAX
    penalty = min(
        QUALITY_TOKEN_EFFICIENCY_MAX_PENALTY,
        (excess / 1000) * QUALITY_TOKEN_EFFICIENCY_PENALTY_PER_1000,
    )
    return max(QUALITY_TOKEN_EFFICIENCY_FLOOR, 100 - penalty)


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
