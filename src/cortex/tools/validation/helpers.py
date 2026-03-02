"""Shared validation helper functions.

This module groups validation-related utilities used by the validate tool and
pre-commit pipelines:

- ValidationCheckType: Enum of valid check types (schema, duplications, etc.)
- Error creators: create_invalid_check_type_error, create_validation_error_response
- Duplication fixes: generate_duplication_fixes (exact/similar content)
"""

from enum import Enum
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.models import JsonValue, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.execution.error_formatters import (
    format_invalid_parameter_error,
    format_tool_error,
)


class ValidationCheckType(str, Enum):
    """Fixed set of validate() check types. Use instead of raw strings."""

    SCHEMA = "schema"
    DUPLICATIONS = "duplications"
    QUALITY = "quality"
    INFRASTRUCTURE = "infrastructure"
    TIMESTAMPS = "timestamps"
    ROADMAP_SYNC = "roadmap_sync"


def parse_validation_check_type(value: str | None) -> ValidationCheckType | None:
    """Parse string to ValidationCheckType. Returns None if invalid or missing."""
    if value is None:
        return None
    try:
        return ValidationCheckType(value)
    except ValueError:
        return None


async def read_all_memory_bank_files(
    fs_manager: FileSystemManager, root: Path
) -> dict[str, str]:
    """Read all markdown files in memory-bank directory."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    files_content: dict[str, str] = {}
    for md_file in memory_bank_dir.glob("*.md"):
        if md_file.is_file():
            content, _ = await fs_manager.read_file(md_file)
            files_content[md_file.name] = content
    return files_content


def create_invalid_check_type_error(check_type: str) -> str:
    """Create error response for invalid check type.

    Args:
        check_type: Invalid check type that was provided

    Returns:
        JSON string with error response
    """
    valid_types = [e.value for e in ValidationCheckType]
    return format_invalid_parameter_error(
        parameter_name="check_type",
        invalid_value=check_type,
        valid_options=valid_types,
        tool_name="validate",
    )


def create_validation_error_response(error: Exception) -> str:
    """Create error response for validation errors.

    Args:
        error: Exception that occurred during validation

    Returns:
        JSON string with error response
    """
    return format_tool_error(
        error,
        suggestion=(
            "Review the error details and ensure all parameters are valid. "
            "Check the tool documentation for correct usage."
        ),
        example={"check_type": "schema", "file_name": "activeContext.md"},
    )


def _create_transclusion_fix(files: list[str]) -> ModelDict:
    """Create a transclusion fix suggestion for duplicated files."""
    files_json: list[JsonValue] = [cast(JsonValue, f) for f in files]
    steps: list[JsonValue] = [
        cast(JsonValue, "1. Create a new file for shared content"),
        cast(JsonValue, "2. Move duplicate content to the new file"),
        cast(JsonValue, "3. Replace duplicates with transclusion syntax"),
    ]
    return {
        "files": files_json,
        "suggestion": "Consider using transclusion: {{include:shared-content.md}}",
        "steps": steps,
    }


def _extract_fixes_from_dup_entries(entries: object) -> list[ModelDict]:
    """Extract transclusion fixes from a list of duplication entries."""
    fixes: list[ModelDict] = []
    if not isinstance(entries, list):
        return fixes
    for raw_entry in cast(list[object], entries):
        entry = cast(ModelDict, raw_entry) if isinstance(raw_entry, dict) else None
        if entry is None:
            continue
        files = entry.get("files")
        if not isinstance(files, list) or len(files) < 2:
            continue
        fixes.append(_create_transclusion_fix([str(f) for f in files]))
    return fixes


def generate_duplication_fixes(
    duplications_data: ModelDict,
) -> list[ModelDict]:
    """Generate fix suggestions for duplicate content."""
    fixes: list[ModelDict] = []
    for key in ("exact_duplicates", "similar_content"):
        fixes.extend(_extract_fixes_from_dup_entries(duplications_data.get(key)))
    return fixes
