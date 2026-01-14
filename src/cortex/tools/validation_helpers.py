"""Validation helper functions for error responses and utilities."""

from cortex.core.responses import error_response


def create_invalid_check_type_error(check_type: str) -> str:
    """Create error response for invalid check type.

    Args:
        check_type: The invalid check type

    Returns:
        JSON string with error response
    """
    valid_types = ["schema", "duplications", "quality", "infrastructure"]
    return error_response(
        ValueError(f"Invalid check_type: {check_type}"),
        action_required=(
            f"Use one of the valid check types: {', '.join(valid_types)}. "
            f"Received: '{check_type}'. "
            f"Example: {{'check_type': '{valid_types[0]}'}}"
        ),
        context={"invalid_check_type": check_type, "valid_check_types": valid_types},
    )


def create_validation_error_response(error: Exception) -> str:
    """Create error response for validation exceptions.

    Args:
        error: The exception that occurred

    Returns:
        JSON string with error response
    """
    error_type = type(error).__name__
    if "ValidationError" in error_type or "validation" in str(error).lower():
        action_required = (
            "Review the validation error and correct the memory bank files. "
            "Run 'validate_memory_bank()' to get detailed validation results. "
            "Check file schemas, fix duplications, or improve quality metrics as needed."
        )
    elif "FileNotFoundError" in error_type:
        action_required = (
            "Ensure the memory bank is properly initialized. "
            "Run 'initialize_memory_bank()' if needed. "
            "Verify that all referenced files exist."
        )
    else:
        action_required = (
            "Review the error details and retry the validation operation. "
            "Check system logs for additional context. "
            "Ensure the memory bank directory is accessible and properly configured."
        )

    return error_response(
        error,
        action_required=action_required,
        context={"error_type": error_type},
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
