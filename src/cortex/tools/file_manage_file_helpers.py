"""Helpers for manage_file: validation, logging, dispatch, manager resolution.

Extracted from file_operations to keep file size under limit.
"""

import json
import logging
import time
from pathlib import Path
from typing import cast

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import (
    get_current_managers,
    get_current_project_root,
    get_or_resolve_project_root,
)
from cortex.managers.initialization import get_managers
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.tools.file_crud_flow import (
    handle_read_operation,
    handle_write_operation,
)
from cortex.tools.file_crud_flow import (
    validate_file_path as _validate_file_path_impl,
)
from cortex.tools.file_metadata_operations import handle_metadata_operation
from cortex.tools.file_operation_helpers import (
    FileOperation,
    build_invalid_operation_error,
    validate_manage_file_operation,
)
from cortex.validation.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


async def _manage_file_get_root(ctx: MCPContext | None) -> Path:
    """Return current project root or resolve via ctx."""
    return await get_or_resolve_project_root(ctx)


async def _log_validation_failure(
    ctx: MCPContext | None, file_name: str | None, operation: str | None
) -> None:
    """Log validation failure for manage_file."""
    await log_client(
        ctx,
        "warning",
        f"manage_file: validation failed file_name={file_name!r} operation={operation!r}",
        logger_name=__name__,
    )


async def manage_file_validate_and_run(
    ctx: MCPContext | None,
    file_name: str | None,
    operation: str | None,
    content: str | None,
    include_metadata: bool,
    change_description: str | None,
    sections: list[str] | None,
) -> str:
    """Validate manage_file inputs and run operation or return error."""
    parsed_op, err = validate_manage_file_operation(operation, file_name)
    if err is not None:
        await _log_validation_failure(ctx, file_name, operation)
        return err

    assert parsed_op is not None and file_name is not None
    root = await _manage_file_get_root(ctx)
    return await _manage_file_run_or_error(
        ctx,
        file_name,
        parsed_op,
        content,
        root,
        include_metadata,
        change_description,
        sections,
    )


def _manage_file_error_response(exc: Exception) -> str:
    """Build JSON error response for manage_file failures."""
    return json.dumps(
        {"status": "error", "error": str(exc), "error_type": type(exc).__name__},
        indent=2,
    )


async def _log_manage_file_result(
    ctx: MCPContext | None,
    file_name: str,
    parsed_op: FileOperation,
    error: Exception | None,
) -> None:
    """Log manage_file completion or failure."""
    if error is None:
        await log_client(
            ctx,
            "info",
            f"manage_file: completed file_name={file_name!r} operation={parsed_op!r}",
            logger_name=__name__,
        )
    else:
        await log_client(
            ctx,
            "error",
            f"manage_file: operation failed file_name={file_name!r} operation={parsed_op!r}: {error}",
            logger_name=__name__,
        )


async def _log_result_by_status(
    ctx: MCPContext | None,
    file_name: str,
    parsed_op: FileOperation,
    result: str,
) -> None:
    """Log manage_file result from JSON response status (error vs success)."""
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            p = cast(dict[str, object], parsed)
            if p.get("status") == "error":
                err_msg = str(p.get("error") or "Operation failed")
                await _log_manage_file_result(
                    ctx, file_name, parsed_op, ValueError(err_msg)
                )
            else:
                await _log_manage_file_result(ctx, file_name, parsed_op, None)
        else:
            await _log_manage_file_result(ctx, file_name, parsed_op, None)
    except (json.JSONDecodeError, TypeError):
        await _log_manage_file_result(ctx, file_name, parsed_op, None)


async def _manage_file_run_or_error(
    ctx: MCPContext | None,
    file_name: str,
    parsed_op: FileOperation,
    content: str | None,
    root: Path,
    include_metadata: bool,
    change_description: str | None,
    sections: list[str] | None,
) -> str:
    """Run execute_file_operation and handle exceptions with logging."""
    try:
        result = await execute_file_operation(
            root,
            file_name,
            parsed_op,
            content,
            include_metadata,
            change_description,
            sections,
        )
        await _log_result_by_status(ctx, file_name, parsed_op, result)
        return result
    except Exception as e:
        await _log_manage_file_result(ctx, file_name, parsed_op, e)
        return _manage_file_error_response(e)


async def _get_managers_for_root(root: Path) -> tuple[ManagersDict, FileSystemManager]:
    """Resolve managers for root; reuse current when root matches."""
    current_mgrs = get_current_managers()
    current_root = get_current_project_root()
    if (
        current_mgrs is not None
        and current_root is not None
        and current_root.resolve() == root.resolve()
    ):
        logger.debug(
            "file_operations: reusing current managers for root %s",
            root,
        )
        managers = ManagersDict.model_validate(current_mgrs)
    else:
        t0 = time.monotonic()
        managers = await get_managers(root)
        logger.debug(
            "file_operations: get_managers(%s) took %.3fs",
            root,
            time.monotonic() - t0,
        )
    return managers, managers.fs


def _validate_and_get_path(
    fs_manager: FileSystemManager, root: Path, file_name: str
) -> tuple[Path | None, str]:
    """Validate file name and get safe file path."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    return _validate_file_path_impl(fs_manager, memory_bank_dir, file_name)


async def execute_file_operation(
    root: Path,
    file_name: str,
    operation: FileOperation,
    content: str | None,
    include_metadata: bool,
    change_description: str | None,
    sections: list[str] | None,
) -> str:
    """Execute file operation after validation. Reuses current managers when root matches."""
    managers, fs_manager = await _get_managers_for_root(root)
    file_path_result = _validate_and_get_path(fs_manager, root, file_name)
    if file_path_result[0] is None:
        return file_path_result[1]
    return await _dispatch_operation(
        operation,
        file_path_result[0],
        file_name,
        content,
        change_description,
        include_metadata,
        root,
        managers,
        sections,
    )


async def _resolve_schema_validator(managers: ManagersDict) -> SchemaValidator | None:
    """Resolve schema validator from managers if available."""
    try:
        return await get_manager(managers, "schema_validator", SchemaValidator)
    except (KeyError, TypeError, AttributeError):
        return None


async def _dispatch_operation(
    operation: FileOperation,
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    include_metadata: bool,
    root: Path,
    managers: ManagersDict,
    sections: list[str] | None,
) -> str:
    """Dispatch operation to appropriate handler."""
    if operation == FileOperation.READ:
        return await _dispatch_read_operation(
            file_path, file_name, root, managers, include_metadata, sections
        )
    if operation == FileOperation.WRITE:
        return await _dispatch_write_operation(
            file_path, file_name, content, change_description, managers, root
        )
    if operation == FileOperation.METADATA:
        return await handle_metadata_operation(file_path, file_name, managers.index)
    return build_invalid_operation_error(operation.value)


async def _dispatch_read_operation(
    file_path: Path,
    file_name: str,
    root: Path,
    managers: ManagersDict,
    include_metadata: bool,
    sections: list[str] | None,
) -> str:
    """Dispatch read operation."""
    return await handle_read_operation(
        file_path,
        file_name,
        root,
        managers.fs,
        managers.index,
        include_metadata,
        sections,
    )


async def _dispatch_write_operation(
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    managers: ManagersDict,
    root: Path,
) -> str:
    """Dispatch write operation."""
    if content is None:
        return json.dumps(
            {"status": "error", "error": "Content is required for write operation"},
            indent=2,
        )
    schema_validator = await _resolve_schema_validator(managers)
    return await handle_write_operation(
        file_path,
        file_name,
        content,
        change_description,
        managers.fs,
        managers.index,
        managers.tokens,
        managers.versions,
        schema_validator,
        project_root=root,
    )
