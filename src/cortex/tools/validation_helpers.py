"""Validation helper functions for error responses and utilities."""

import json


def create_invalid_check_type_error(check_type: str) -> str:
    """Create error response for invalid check type.

    Args:
        check_type: The invalid check type

    Returns:
        JSON string with error response
    """
    return json.dumps(
        {
            "status": "error",
            "error": f"Invalid check_type: {check_type}",
            "valid_check_types": [
                "schema",
                "duplications",
                "quality",
                "infrastructure",
            ],
        },
        indent=2,
    )


def create_validation_error_response(error: Exception) -> str:
    """Create error response for validation exceptions.

    Args:
        error: The exception that occurred

    Returns:
        JSON string with error response
    """
    return json.dumps(
        {"status": "error", "error": str(error), "error_type": type(error).__name__},
        indent=2,
    )


def generate_duplication_fixes(
    duplications_dict: dict[str, object],
) -> list[dict[str, object]]:
    """Generate fix suggestions for duplications.

    Args:
        duplications_dict: Dictionary containing duplication results

    Returns:
        List of fix suggestion dictionaries
    """
    from typing import cast

    fixes: list[dict[str, object]] = []
    exact_dups = cast(
        list[dict[str, object]], duplications_dict.get("exact_duplicates", [])
    )
    similar = cast(
        list[dict[str, object]], duplications_dict.get("similar_content", [])
    )

    for dup in exact_dups + similar:
        fix: dict[str, object] = {
            "files": dup.get("files", []),
            "suggestion": "Consider using transclusion: {{include:shared-content.md}}",
            "steps": [
                "1. Create a new file for shared content",
                "2. Move duplicate content to the new file",
                "3. Replace duplicates with transclusion syntax",
            ],
        }
        fixes.append(fix)
    return fixes
