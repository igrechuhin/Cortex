"""
Cache operations for summarization engine.

Extracted from summarization_engine for file size compliance.
"""

import hashlib
import json
from pathlib import Path

from cortex.core.async_file_utils import open_async_text_file


def compute_content_hash(content: str) -> str:
    """Compute hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_cached_summary(
    cache_dir: Path,
    file_name: str,
    content_hash: str,
    strategy: str,
) -> str | None:
    """
    Get cached summary if available.

    Args:
        cache_dir: Cache directory
        file_name: File name
        content_hash: Content hash
        strategy: Strategy used

    Returns:
        Cached summary or None
    """
    cache_file = cache_dir / f"{file_name}.{strategy}.{content_hash}.json"

    if cache_file.exists():
        try:
            with open(cache_file) as f:
                data = json.load(f)
                return data.get("summary")
        except (OSError, json.JSONDecodeError):
            return None

    return None


async def cache_summary_async(
    cache_dir: Path,
    file_name: str,
    content_hash: str,
    strategy: str,
    summary: str,
) -> None:
    """
    Cache generated summary.

    Args:
        cache_dir: Cache directory
        file_name: File name
        content_hash: Content hash
        strategy: Strategy used
        summary: Generated summary
    """
    cache_file = cache_dir / f"{file_name}.{strategy}.{content_hash}.json"

    try:
        async with open_async_text_file(cache_file, "w", "utf-8") as f:
            _ = await f.write(
                json.dumps(
                    {
                        "file_name": file_name,
                        "content_hash": content_hash,
                        "strategy": strategy,
                        "summary": summary,
                    },
                    indent=2,
                )
            )
    except OSError:
        pass  # Silently fail on cache write errors
