"""Schema validation operations for Memory Bank files."""

import json
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.response_builder import error_response, success_response
from cortex.validation.schema_validator import SchemaValidator


async def _resolve_schema_file_path(
    fs_manager: FileSystemManager,
    root: Path,
    file_name: str,
) -> tuple[Path | None, str | None]:
    """Resolve schema file path or return error JSON."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        error_json = json.dumps(
            error_response(
                error=f"Invalid file name: {e}", error_type=type(e).__name__
            ),
            indent=2,
        )
        return None, error_json
    if not file_path.exists():
        error_json = json.dumps(
            error_response(
                error=f"File {file_name} does not exist", error_type="FileNotFoundError"
            ),
            indent=2,
        )
        return None, error_json
    return file_path, None


async def validate_schema_single_file(
    fs_manager: FileSystemManager,
    schema_validator: SchemaValidator,
    root: Path,
    file_name: str,
) -> str:
    """Validate a single file against schema."""
    file_path, error_json = await _resolve_schema_file_path(fs_manager, root, file_name)
    if error_json is not None:
        return error_json
    assert file_path is not None
    content, _ = await fs_manager.read_file(file_path)
    validation_result = await schema_validator.validate_file(file_name, content)
    return json.dumps(
        success_response(
            check_type="schema",
            file_name=file_name,
            validation=validation_result.model_dump(),
        ),
        indent=2,
    )


async def validate_schema_all_files(
    fs_manager: FileSystemManager, schema_validator: SchemaValidator, root: Path
) -> str:
    """Validate all files against schema."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    results_dict: ModelDict = {}
    for md_file in memory_bank_dir.glob("*.md"):
        if md_file.is_file():
            content, _ = await fs_manager.read_file(md_file)
            validation_result = await schema_validator.validate_file(
                md_file.name, content
            )
            results_dict[md_file.name] = validation_result.model_dump()
    return json.dumps(
        success_response(check_type="schema", results=results_dict),
        indent=2,
    )


async def handle_schema_validation(
    fs_manager: FileSystemManager,
    schema_validator: SchemaValidator,
    root: Path,
    file_name: str | None,
) -> str:
    """Handle schema validation routing.

    Args:
        fs_manager: File system manager
        schema_validator: Schema validator instance
        root: Project root path
        file_name: Optional specific file to validate

    Returns:
        JSON string with schema validation results
    """
    if file_name:
        return await validate_schema_single_file(
            fs_manager, schema_validator, root, file_name
        )
    else:
        return await validate_schema_all_files(fs_manager, schema_validator, root)
