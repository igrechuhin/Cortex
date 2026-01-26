"""Shared validation helper functions."""

import json
from pathlib import Path
from typing import Literal, cast

from cortex.core.file_system import FileSystemManager
from cortex.core.models import JsonValue, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

CheckType = Literal[
    "schema",
    "duplications",
    "quality",
    "infrastructure",
    "timestamps",
    "roadmap_sync",
]


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
    valid_types: list[CheckType] = [
        "schema",
        "duplications",
        "quality",
        "infrastructure",
        "timestamps",
        "roadmap_sync",
    ]
    return json.dumps(
        {
            "status": "error",
            "error": f"Invalid check_type: {check_type}",
            "valid_check_types": valid_types,
        },
        indent=2,
    )


def create_validation_error_response(error: Exception) -> str:
    """Create error response for validation errors.

    Args:
        error: Exception that occurred during validation

    Returns:
        JSON string with error response
    """
    return json.dumps(
        {
            "status": "error",
            "error": str(error),
            "error_type": type(error).__name__,
        },
        indent=2,
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


def generate_duplication_fixes(
    duplications_data: ModelDict,
) -> list[ModelDict]:
    """Generate fix suggestions for duplicate content."""
    fixes: list[ModelDict] = []

    exact_duplicates = duplications_data.get("exact_duplicates")
    if isinstance(exact_duplicates, list):
        for dup in exact_duplicates:
            if isinstance(dup, dict):
                files = dup.get("files")
                if isinstance(files, list) and len(files) >= 2:
                    fixes.append(_create_transclusion_fix([str(f) for f in files]))

    similar_content = duplications_data.get("similar_content")
    if isinstance(similar_content, list):
        for sim in similar_content:
            if isinstance(sim, dict):
                files = sim.get("files")
                if isinstance(files, list) and len(files) >= 2:
                    fixes.append(_create_transclusion_fix([str(f) for f in files]))

    return fixes
