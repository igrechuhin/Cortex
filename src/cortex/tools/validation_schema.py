"""Schema validation operations for Memory Bank files."""

import json
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.validation.schema_validator import SchemaValidator


async def validate_schema_single_file(
    fs_manager: FileSystemManager,
    schema_validator: SchemaValidator,
    root: Path,
    file_name: str,
) -> str:
    """Validate a single file against schema."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return json.dumps(
            {"status": "error", "error": f"Invalid file name: {e}"}, indent=2
        )
    if not file_path.exists():
        return json.dumps(
            {"status": "error", "error": f"File {file_name} does not exist"}, indent=2
        )
    content, _ = await fs_manager.read_file(file_path)
    validation_result = await schema_validator.validate_file(file_name, content)
    return json.dumps(
        {
            "status": "success",
            "check_type": "schema",
            "file_name": file_name,
            "validation": validation_result,
        },
        indent=2,
    )


async def validate_schema_all_files(
    fs_manager: FileSystemManager, schema_validator: SchemaValidator, root: Path
) -> str:
    """Validate all files against schema."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    results_dict: dict[str, object] = {}
    for md_file in memory_bank_dir.glob("*.md"):
        if md_file.is_file():
            content, _ = await fs_manager.read_file(md_file)
            validation_result = await schema_validator.validate_file(
                md_file.name, content
            )
            results_dict[md_file.name] = validation_result
    return json.dumps(
        {"status": "success", "check_type": "schema", "results": results_dict},
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
