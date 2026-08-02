"""Helpers for manage_file: validation, logging, dispatch, manager resolution.

Extracted from file_operations to keep file size under limit.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from cortex.core.constants import (
    MAX_MANAGE_FILE_CONTENT_BYTES,
    MAX_SECTIONS_LIST_SIZE,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.file_system import FileSystemManager
from cortex.core.models import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import (
    get_current_managers,
    get_current_project_root,
    get_or_resolve_project_root,
)
from cortex.managers.initialization import get_managers
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.memory.timeline import MemoryTimelineInput, memory_timeline_handle
from cortex.tools.files.artifact_operations import file_artifact_from_payload
from cortex.tools.files.constitution_init_flow import handle_init_constitution_operation
from cortex.tools.files.crud_flow import (
    handle_read_operation,
    handle_rollback_operation,
    handle_write_operation,
)
from cortex.tools.files.crud_flow import (
    validate_file_path as _validate_file_path_impl,
)
from cortex.tools.files.metadata_operations import handle_metadata_operation
from cortex.tools.files.operation_helpers import (
    GOAL_FILE_OPERATIONS,
    SCHEMA_FILE_OPERATIONS,
    SEARCH_FILE_OPERATIONS,
    FileOperation,
    build_invalid_operation_error,
    validate_manage_file_operation,
)
from cortex.tools.files.plan_draft_file_ops import (
    execute_plan_draft_operation,
    validate_discard_draft_content,
)
from cortex.tools.files.session_goal_file_ops import execute_session_goal_operation
from cortex.tools.response_builder import error_response
from cortex.validation.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


def _temporal_db_path(root: Path) -> Path:
    return root / ".cortex" / "temporal.db"


def _parse_json_content(content: str | None) -> dict[str, str] | None:
    if content is None:
        return None
    try:
        parsed_obj: object = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_obj, dict):
        return None
    parsed_dict = cast(dict[object, object], parsed_obj)
    typed_dict: dict[str, str] = {}
    for raw_key, raw_value in parsed_dict.items():
        typed_dict[str(raw_key)] = str(raw_value)
    return typed_dict


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


def _validate_set_goal_content_present(content: str | None) -> str | None:
    if content is None or not str(content).strip():
        return json.dumps(
            error_response(
                error="content is required for set_goal (JSON with goal, optional plan_slug)",
                error_type="ValueError",
            ),
            indent=2,
        )
    return None


def _validate_write_content_byte_limit(content: str) -> str | None:
    size_bytes = len(content.encode("utf-8"))
    if size_bytes > MAX_MANAGE_FILE_CONTENT_BYTES:
        return json.dumps(
            error_response(
                error=(
                    f"Content too large: {size_bytes} bytes exceeds "
                    f"limit of {MAX_MANAGE_FILE_CONTENT_BYTES} bytes"
                ),
                error_type="ValueError",
            ),
            indent=2,
        )
    return None


def _validate_sections_list_limit(sections: list[str]) -> str | None:
    if len(sections) > MAX_SECTIONS_LIST_SIZE:
        return json.dumps(
            error_response(
                error=(
                    f"Sections list too long: {len(sections)} items exceeds "
                    f"limit of {MAX_SECTIONS_LIST_SIZE}"
                ),
                error_type="ValueError",
            ),
            indent=2,
        )
    return None


def _validate_manage_file_input_limits(
    content: str | None, sections: list[str] | None, operation: FileOperation
) -> str | None:
    """Validate content and sections input limits. Returns error JSON or None."""
    if operation == FileOperation.SET_GOAL:
        return _validate_set_goal_content_present(content)
    if operation == FileOperation.FORK_SCHEMA:
        return _validate_set_goal_content_present(content)
    if operation == FileOperation.WRITE and content is not None:
        size_err = _validate_write_content_byte_limit(content)
        if size_err is not None:
            return size_err
    if operation == FileOperation.DISCARD_DRAFT:
        return validate_discard_draft_content(content)
    if sections is not None:
        return _validate_sections_list_limit(sections)
    return None


def _resolve_manage_file_name(parsed_op: FileOperation, file_name: str | None) -> str:
    if parsed_op in GOAL_FILE_OPERATIONS:
        return file_name or "_session_goal"
    if parsed_op in SCHEMA_FILE_OPERATIONS:
        return "_workflow_schemas"
    if parsed_op in SEARCH_FILE_OPERATIONS:
        return "_search"
    assert file_name is not None
    return file_name


# fmt: off
async def manage_file_validate_and_run(ctx: MCPContext | None, file_name: str | None, operation: str | None, content: str | None, include_metadata: bool, change_description: str | None, sections: list[str] | None, version: int | None = None, skip_classification: bool = False) -> str:
# fmt: on
    parsed_op, err = validate_manage_file_operation(operation, file_name, version)
    if err is not None:
        await _log_validation_failure(ctx, file_name, operation)
        return err
    assert parsed_op is not None
    resolved_name = _resolve_manage_file_name(parsed_op, file_name)
    limits_err = _validate_manage_file_input_limits(content, sections, parsed_op)
    if limits_err is not None:
        await _log_validation_failure(ctx, resolved_name, operation)
        return limits_err
    return await _run_validated_manage_file(
        ctx,
        resolved_name,
        parsed_op,
        content,
        include_metadata,
        change_description,
        sections,
        version,
        skip_classification,
    )


async def _run_validated_manage_file(
    ctx: MCPContext | None,
    file_name: str,
    parsed_op: FileOperation,
    content: str | None,
    include_metadata: bool,
    change_description: str | None,
    sections: list[str] | None,
    version: int | None,
    skip_classification: bool,
) -> str:
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
        version,
        skip_classification,
    )


def _manage_file_error_response(exc: Exception) -> str:
    """Build JSON error response for manage_file failures."""
    return json.dumps(
        error_response(error=str(exc), error_type=type(exc).__name__),
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


async def log_result_by_status(
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
    version: int | None = None,
    skip_classification: bool = False,
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
            version,
            skip_classification,
        )
        await log_result_by_status(ctx, file_name, parsed_op, result)
        return result
    except Exception as e:
        await _log_manage_file_result(ctx, file_name, parsed_op, e)
        return _manage_file_error_response(e)


async def get_managers_for_root(root: Path) -> tuple[ManagersDict, FileSystemManager]:
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


# fmt: off
async def execute_file_operation(root: Path, file_name: str, operation: FileOperation, content: str | None, include_metadata: bool, change_description: str | None, sections: list[str] | None, version: int | None = None, skip_classification: bool = False) -> str:
# fmt: on
    if operation in SCHEMA_FILE_OPERATIONS:
        from cortex.tools.files.workflow_schema_file_ops import (
            execute_workflow_schema_operation,
        )
        return await execute_workflow_schema_operation(root, operation, content)
    if _is_plan_draft_file_operation(operation):
        return execute_plan_draft_operation(root, operation, content)
    managers, fs_manager = await get_managers_for_root(root)
    if operation in GOAL_FILE_OPERATIONS:
        return await execute_session_goal_operation(root, operation, content, managers)
    if _is_explore_log_operation(operation):
        return await _dispatch_explore_log_operation(
            operation, root, file_name, content, change_description, managers, sections, version
        )
    if operation in SEARCH_FILE_OPERATIONS:
        return _search_memory_bank(root, content)
    return await _dispatch_standard_file_operation(
        root,
        file_name,
        operation,
        content,
        include_metadata,
        change_description,
        sections,
        version,
        managers,
        fs_manager,
        skip_classification,
    )


async def _dispatch_standard_file_operation(
    root: Path,
    file_name: str,
    operation: FileOperation,
    content: str | None,
    include_metadata: bool,
    change_description: str | None,
    sections: list[str] | None,
    version: int | None,
    managers: ManagersDict,
    fs_manager: FileSystemManager,
    skip_classification: bool,
) -> str:
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
        version,
        skip_classification,
    )


def _is_plan_draft_file_operation(operation: FileOperation) -> bool:
    return operation in (
        FileOperation.LIST_DRAFTS,
        FileOperation.DISCARD_DRAFT,
    )


def _is_explore_log_operation(operation: FileOperation) -> bool:
    return operation in (
        FileOperation.LIST_EXPLORE_LOGS,
        FileOperation.CLEAR_EXPLORE_LOGS,
        FileOperation.LIST_SHAPE_LOGS,
        FileOperation.CLEAR_SHAPE_LOGS,
    )


async def _dispatch_explore_log_operation(
    operation: FileOperation,
    root: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    managers: ManagersDict,
    sections: list[str] | None,
    version: int | None,
) -> str:
    return await _dispatch_operation(
        operation,
        root,
        file_name,
        content,
        change_description,
        False,
        root,
        managers,
        sections,
        version,
    )


async def resolve_schema_validator(managers: ManagersDict) -> SchemaValidator | None:
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
    version: int | None = None,
    skip_classification: bool = False,
) -> str:
    """Dispatch operation to appropriate handler."""
    delegated = await _dispatch_known_operation(
        operation,
        file_path,
        file_name,
        content,
        change_description,
        include_metadata,
        root,
        managers,
        sections,
        version,
        skip_classification,
    )
    if delegated is not None:
        return delegated
    return build_invalid_operation_error(operation.value)


async def _dispatch_known_operation(
    operation: FileOperation,
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    include_metadata: bool,
    root: Path,
    managers: ManagersDict,
    sections: list[str] | None,
    version: int | None,
    skip_classification: bool,
) -> str | None:
    """Dispatch known operations and return None for unsupported operation."""
    primary = await _dispatch_primary_operation(
        operation,
        file_path,
        file_name,
        content,
        change_description,
        include_metadata,
        root,
        managers,
        sections,
        skip_classification,
    )
    if primary is not None:
        return primary
    return await _dispatch_secondary_operation(
        operation, file_path, file_name, content, root, managers, version
    )


async def _dispatch_primary_operation(
    operation: FileOperation,
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    include_metadata: bool,
    root: Path,
    managers: ManagersDict,
    sections: list[str] | None,
    skip_classification: bool,
) -> str | None:
    """Dispatch read/write/metadata operations."""
    if operation == FileOperation.READ:
        return await _dispatch_read_operation(
            file_path, file_name, root, managers, include_metadata, sections
        )
    if operation == FileOperation.WRITE:
        return await _dispatch_write_operation(
            file_path,
            file_name,
            content,
            change_description,
            managers,
            root,
            skip_classification,
        )
    if operation == FileOperation.READ_BY_TYPE:
        return _dispatch_read_by_type_operation(root, file_name, content)
    if operation == FileOperation.METADATA:
        return await handle_metadata_operation(file_path, file_name, managers.index)
    return None


async def _dispatch_secondary_operation(
    operation: FileOperation,
    file_path: Path,
    file_name: str,
    content: str | None,
    root: Path,
    managers: ManagersDict,
    version: int | None,
) -> str | None:
    """Dispatch rollback/init/file_artifact operations."""
    if operation == FileOperation.ROLLBACK:
        assert version is not None
        return await handle_rollback_operation(file_name, version, root)
    if operation == FileOperation.INIT_CONSTITUTION:
        return await handle_init_constitution_operation(
            file_path, file_name, root, managers
        )
    if operation == FileOperation.FILE_ARTIFACT:
        return await file_artifact_from_payload(
            memory_bank_dir=get_cortex_path(root, CortexResourceType.MEMORY_BANK),
            payload=content,
        )
    pre_plan_result = _dispatch_pre_plan_log_operation(operation, root)
    if pre_plan_result is not None:
        return pre_plan_result
    if operation == FileOperation.INVALIDATE_FACT:
        return _invalidate_temporal_fact(root, content)
    if operation == FileOperation.MEMORY_TIMELINE:
        return _memory_timeline(root, content)
    return None


def _dispatch_pre_plan_log_operation(
    operation: FileOperation, root: Path
) -> str | None:
    """Handle list/clear for the ephemeral explore and shape log directories."""
    if operation == FileOperation.LIST_EXPLORE_LOGS:
        return _list_pre_plan_logs(root, "explore")
    if operation == FileOperation.CLEAR_EXPLORE_LOGS:
        return _clear_pre_plan_logs(root, "explore")
    if operation == FileOperation.LIST_SHAPE_LOGS:
        return _list_pre_plan_logs(root, "shape")
    if operation == FileOperation.CLEAR_SHAPE_LOGS:
        return _clear_pre_plan_logs(root, "shape")
    return None


def _pre_plan_logs_dir(root: Path, subdir: str) -> Path:
    """Directory holding ephemeral pre-plan logs ('explore' or 'shape')."""
    return get_cortex_path(root, CortexResourceType.PLANS) / subdir


def _list_pre_plan_logs(root: Path, subdir: str) -> str:
    explore_dir = _pre_plan_logs_dir(root, subdir)
    if not explore_dir.exists():
        return json.dumps({"status": OperationStatus.SUCCESS.value, "logs": [], "count": 0}, indent=2)
    logs = [
        str(path.relative_to(root))
        for path in sorted(explore_dir.glob("*.md"))
        if path.is_file()
    ]
    return json.dumps({"status": OperationStatus.SUCCESS.value, "logs": logs, "count": len(logs)}, indent=2)


def _clear_pre_plan_logs(root: Path, subdir: str) -> str:
    explore_dir = _pre_plan_logs_dir(root, subdir)
    if not explore_dir.exists():
        return json.dumps({"status": OperationStatus.SUCCESS.value, "deleted": [], "count": 0}, indent=2)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    deleted: list[str] = []
    for path in sorted(explore_dir.glob("*.md")):
        if not path.is_file():
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            path.unlink(missing_ok=True)
            deleted.append(str(path.relative_to(root)))
    return json.dumps(
        {"status": OperationStatus.SUCCESS.value, "deleted": deleted, "count": len(deleted)}, indent=2
    )


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
    skip_classification: bool,
) -> str:
    """Dispatch write operation."""
    if content is None:
        return json.dumps(
            error_response(error="Content is required for write operation"),
            indent=2,
        )
    schema_validator = await resolve_schema_validator(managers)
    final_content = _classify_write_content(content, skip_classification)
    result = await handle_write_operation(
        file_path,
        file_name,
        final_content,
        change_description,
        managers.fs,
        managers.index,
        managers.tokens,
        managers.versions,
        schema_validator,
        project_root=root,
    )
    index_temporal_file(root, file_path, result)
    return result


def index_temporal_file(root: Path, file_path: Path, result: str) -> None:
    # AI: Index only confirmed successful writes so failed write attempts never create false timeline facts.
    try:
        payload_obj: object = json.loads(result)
    except json.JSONDecodeError:
        return
    if not isinstance(payload_obj, dict):
        return
    payload_dict = cast(dict[str, object], payload_obj)
    status = payload_dict.get("status")
    if status != "success":
        return
    from cortex.memory.temporal_indexer import TemporalIndexer
    from cortex.memory.temporal_store import TemporalMemoryStore

    indexer = TemporalIndexer(TemporalMemoryStore(_temporal_db_path(root)), root)
    _ = indexer.index_file(file_path)


def _invalidate_temporal_fact(root: Path, content: str | None) -> str:
    payload = _parse_json_content(content)
    if payload is None:
        return json.dumps(error_response(error="invalidate_fact requires JSON content"), indent=2)
    required = ("subject", "predicate", "object", "ended")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return json.dumps(error_response(error=f"Missing fields: {', '.join(missing)}"), indent=2)
    from cortex.memory.temporal_store import TemporalMemoryStore

    store = TemporalMemoryStore(_temporal_db_path(root))
    changed = store.invalidate(
        subject=payload["subject"],
        predicate=payload["predicate"],
        object=payload["object"],
        ended=payload["ended"],
    )
    return json.dumps({"status": "success", "invalidated": changed}, indent=2)


def _memory_timeline(root: Path, content: str | None) -> str:
    payload = _parse_json_content(content)
    input_data = MemoryTimelineInput.model_validate(payload or {})
    result = memory_timeline_handle(input_data, root)
    return result.model_dump_json(indent=2)


def _search_memory_bank(root: Path, content: str | None) -> str:
    """Handle operation='search': BM25 ranked retrieval over .cortex/ markdown."""
    if not content:
        return json.dumps(error_response(error="content is required (JSON with 'query')"), indent=2)
    from cortex.retrieval.memory_searcher import MemoryBankSearcher, SearchInput

    try:
        raw: object = json.loads(content)
        params = SearchInput.model_validate(raw)
    except Exception as exc:
        return json.dumps(error_response(error=f"invalid search content: {exc}"), indent=2)
    if not params.query.strip():
        return json.dumps(error_response(error="'query' must be non-empty"), indent=2)
    results = MemoryBankSearcher(root).search(
        params.query, top_k=params.top_k, file_filter=params.file_filter
    )
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "results": [r.model_dump() for r in results],
            "count": len(results),
        },
        indent=2,
    )


def _classify_write_content(content: str, skip_classification: bool) -> str:
    if skip_classification or "<!-- memory_type:" in content:
        return content
    from cortex.memory.memory_types import classify_text

    memory_type = classify_text(content).value
    return f"<!-- memory_type: {memory_type} -->\n{content}"


def _dispatch_read_by_type_operation(
    root: Path, file_name: str, content: str | None
) -> str:
    from cortex.memory.memory_types import MemoryType
    from cortex.memory.typed_reader import TypedMemoryReader

    payload = _parse_json_content(content) or {}
    requested_file = payload.get("file_name", file_name)
    memory_type_raw = payload.get("memory_type", "")
    try:
        memory_type = MemoryType(memory_type_raw.lower())
    except ValueError:
        return json.dumps(
            error_response(error=f"Invalid memory_type: {memory_type_raw}"), indent=2
        )
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    entries = TypedMemoryReader().read_by_type(memory_bank_dir / requested_file, memory_type)
    return json.dumps(
        {"status": OperationStatus.SUCCESS.value, "entries": [e.model_dump() for e in entries]},
        indent=2,
    )
