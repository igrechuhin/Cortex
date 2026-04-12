"""Initialize memory-bank constitution.md from the Synapse template."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import OperationStatus
from cortex.core.path_resolver import get_constitution_template_path
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.tools.response_builder import error_response


def _init_constitution_error_payload(message: str, error_type: str) -> str:
    return json.dumps(error_response(error=message, error_type=error_type), indent=2)


def _skipped_already_exists(file_name: str) -> str:
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "file_name": file_name,
            "skipped": True,
            "message": (
                f"{file_name} already exists; left unchanged. Edit the file to "
                "reflect project governance."
            ),
        },
        indent=2,
    )


def _read_template_or_error(root: Path) -> tuple[str | None, str | None]:
    """Return (content, error_json). Exactly one of the pair is non-None."""
    template_path = get_constitution_template_path(root)
    if not template_path.is_file():
        err = _init_constitution_error_payload(
            f"Constitution template not found at {template_path}",
            "FileNotFoundError",
        )
        return None, err
    try:
        return template_path.read_text(encoding="utf-8"), None
    except OSError as e:
        return None, _init_constitution_error_payload(str(e), type(e).__name__)


async def _write_constitution_from_template(
    file_name: str,
    content: str,
    root: Path,
    managers: ManagersDict,
) -> str:
    from cortex.tools.files.crud_flow import execute_memory_bank_write

    fs_manager = await get_manager(managers, "fs", FileSystemManager)
    metadata_index = await get_manager(managers, "index", MetadataIndex)
    token_counter = await get_manager(managers, "tokens", TokenCounter)
    version_manager = await get_manager(managers, "versions", VersionManager)
    return await execute_memory_bank_write(
        root,
        file_name,
        content,
        "Initialized constitution from Synapse template",
        fs_manager,
        metadata_index,
        token_counter,
        version_manager,
    )


async def handle_init_constitution_operation(
    file_path: Path,
    file_name: str,
    root: Path,
    managers: ManagersDict,
) -> str:
    """Copy Synapse constitution template into memory bank when missing."""
    # AI: Isolated module so crud_flow stays within file/function size limits.
    if file_name != MemoryBankFile.CONSTITUTION:
        return _init_constitution_error_payload(
            (
                f"init_constitution applies only to {MemoryBankFile.CONSTITUTION!r}; "
                f"got {file_name!r}"
            ),
            "ValueError",
        )
    if file_path.exists():
        return _skipped_already_exists(file_name)

    content, err = _read_template_or_error(root)
    if err is not None:
        return err
    assert content is not None
    return await _write_constitution_from_template(file_name, content, root, managers)
