"""
Cache operations for summarization engine.

Extracted from summarization_engine for file size compliance.
"""

import hashlib
import json
from pathlib import Path

from pydantic import Field, ValidationError

from cortex.core.async_file_utils import open_async_text_file
from cortex.optimization.models import DroppedSection, OptimizationBaseModel


def compute_content_hash(content: str) -> str:
    """Compute hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def compute_variant_hash(
    strategy: str, target_tokens: int, scorer_identity: str
) -> str:
    """Stable short hash over the (strategy, target_tokens, scorer) combination.

    # AI: a cached summary's CONTENT depends on target_tokens (the integer
    # budget that actually drives section selection) and on which
    # SectionScorer produced it, not just on content+strategy. Folding both
    # into the cache key stops a summary built for one target/scorer
    # combination from being served for another. Keying on target_tokens
    # itself -- rather than the raw target_reduction ratio -- matters
    # because two ratios equal up to any fixed rounding can still floor to
    # different integer budgets on large content; a ratio-based key would
    # let one variant's cache entry silently serve the other's request.
    """
    variant = f"{strategy}|{target_tokens}|{scorer_identity}"
    return hashlib.sha256(variant.encode()).hexdigest()[:16]


class CachedResult(OptimizationBaseModel):
    """Full provenance persisted for a cached, variant-keyed summary."""

    summary: str = Field(..., description="Generated summary text")
    sections_kept: int = Field(default=0, ge=0)
    sections_removed: int = Field(default=0, ge=0)
    dropped_sections: list[DroppedSection] = Field(default_factory=list[DroppedSection])


def _result_cache_path(
    cache_dir: Path,
    file_name: str,
    strategy: str,
    variant_hash: str,
    content_hash: str,
) -> Path:
    """Build the variant-keyed cache path: strategy stays human-readable,
    variant_hash+content_hash keep it unique and filesystem-safe."""
    return cache_dir / f"{file_name}.{strategy}.{variant_hash}.{content_hash}.json"


def get_cached_result(
    cache_dir: Path,
    file_name: str,
    content_hash: str,
    strategy: str,
    variant_hash: str,
) -> CachedResult | None:
    """
    Get the cached summary and its full provenance for one specific
    (content, strategy, target_reduction, scorer) combination.

    Returns:
        None on a miss, a corrupt entry, an entry written by an older
        cache schema, or a cache directory that cannot even be stat'd
        (e.g. permission-denied) -- this never raises on a stale,
        foreign, or inaccessible file.
    """
    cache_file = _result_cache_path(
        cache_dir, file_name, strategy, variant_hash, content_hash
    )
    try:
        if not cache_file.exists():
            return None
        with open(cache_file) as f:
            data = json.load(f)
        return CachedResult.model_validate(data)
    except (OSError, json.JSONDecodeError, ValidationError):
        return None


async def cache_result_async(
    cache_dir: Path,
    file_name: str,
    content_hash: str,
    strategy: str,
    variant_hash: str,
    summary: str,
    sections_kept: int = 0,
    sections_removed: int = 0,
    dropped_sections: list[DroppedSection] | None = None,
) -> None:
    """Cache a generated summary together with its full provenance."""
    cache_file = _result_cache_path(
        cache_dir, file_name, strategy, variant_hash, content_hash
    )
    payload = CachedResult(
        summary=summary,
        sections_kept=sections_kept,
        sections_removed=sections_removed,
        dropped_sections=dropped_sections or [],
    )
    try:
        async with open_async_text_file(cache_file, "w", "utf-8") as f:
            _ = await f.write(payload.model_dump_json(indent=2))
    except OSError:
        pass  # Silently fail on cache write errors
