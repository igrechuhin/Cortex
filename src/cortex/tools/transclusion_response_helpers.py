"""Response and error building helpers for transclusion resolution.

Extracted from transclusion_operations to keep the main module under 400 lines.
"""

import json
from typing import cast

from cortex.core.models import ModelDict
from cortex.linking.transclusion_engine import (
    CircularDependencyError,
    MaxDepthExceededError,
)
from cortex.tools.context_auxiliary_models import (
    CacheStats,
    ResolveTransclusionsErrorResult,
    ResolveTransclusionsResult,
)


def build_transclusion_success_response(
    file_name: str,
    original_content: str,
    resolved_content: str,
    cache_stats: ModelDict,
) -> ResolveTransclusionsResult:
    """Build success response for transclusion resolution.

    Args:
        file_name: Name of file
        original_content: Original file content
        resolved_content: Resolved content with transclusions
        cache_stats: Cache statistics dict

    Returns:
        Success response model
    """
    cache_stats_model: CacheStats | None = None
    if cache_stats:
        cache_stats_model = CacheStats(
            hits=cast(int, cache_stats.get("hits", 0)),
            misses=cast(int, cache_stats.get("misses", 0)),
            size=cast(int, cache_stats.get("size", 0)),
        )
    return ResolveTransclusionsResult(
        file=file_name,
        original_content=original_content,
        resolved_content=resolved_content,
        has_transclusions=True,
        cache_stats=cache_stats_model,
    )


def build_circular_dependency_error(
    error_message: str,
) -> ResolveTransclusionsErrorResult:
    """Build error response for circular dependency.

    Args:
        error_message: Error message

    Returns:
        Error response model
    """
    return ResolveTransclusionsErrorResult(
        error=error_message,
        error_type="CircularDependencyError",
        message=(
            "Circular transclusion detected. Fix the circular reference and try again."
        ),
    )


def build_max_depth_error(
    error_message: str, max_depth: int
) -> ResolveTransclusionsErrorResult:
    """Build error response for max depth exceeded.

    Args:
        error_message: Error message
        max_depth: Maximum depth that was exceeded

    Returns:
        Error response model
    """
    return ResolveTransclusionsErrorResult(
        error=error_message,
        error_type="MaxDepthExceededError",
        message=f"Maximum transclusion depth ({max_depth}) exceeded",
    )


def build_transclusion_error(
    error_message: str, error_type: str
) -> ResolveTransclusionsErrorResult:
    """Build error response for general transclusion errors.

    Args:
        error_message: Error message
        error_type: Error type name

    Returns:
        Error response model
    """
    return ResolveTransclusionsErrorResult(
        error=error_message,
        error_type=error_type,
    )


def resolve_transclusions_error_json(e: BaseException, max_depth: int) -> str:
    """Build error JSON string for transclusion resolution exceptions."""
    if isinstance(e, CircularDependencyError):
        return json.dumps(
            build_circular_dependency_error(str(e)).model_dump(), indent=2
        )
    if isinstance(e, MaxDepthExceededError):
        return json.dumps(
            build_max_depth_error(str(e), max_depth).model_dump(), indent=2
        )
    return json.dumps(
        build_transclusion_error(str(e), type(e).__name__).model_dump(),
        indent=2,
    )
