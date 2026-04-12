"""File metadata operations: metrics, version snapshots, metadata updates.

Used by manage_file (read/write/metadata) and by internal write flow.
Kept separate to keep crud_operations under size limits.
"""

import asyncio
import json
from collections.abc import Awaitable
from pathlib import Path
from typing import Protocol, cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import (
    DetailedFileMetadata,
    ModelDict,
    OperationStatus,
    VersionMetadata,
)
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.tools.files.section_operations import extract_sections


class _ExistsPath(Protocol):
    def exists(self) -> bool | Awaitable[bool]: ...


async def _path_exists(file_path: _ExistsPath) -> bool:
    """Return True if path exists; supports mocked async .exists() in tests."""
    try:
        result = file_path.exists()
    except Exception:
        return False
    if asyncio.iscoroutine(result):
        return bool(await result)
    return bool(result)


def _metadata_error_missing_file(file_name: str) -> str:
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": f"File {file_name} does not exist",
            "file_name": file_name,
        },
        indent=2,
    )


def _metadata_warning_no_metadata(file_name: str) -> str:
    return json.dumps(
        {
            "status": "warning",
            "file_name": file_name,
            "metadata": None,
            "message": f"No metadata found for {file_name}",
        },
        indent=2,
    )


def _metadata_success(
    file_name: str, file_exists: bool, metadata: DetailedFileMetadata
) -> str:
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "file_name": file_name,
            "file_exists": file_exists,
            "metadata": metadata.model_dump(mode="json"),
        },
        indent=2,
    )


def compute_file_metrics(
    content: str, fs_manager: FileSystemManager, token_counter: TokenCounter
) -> ModelDict:
    """Compute file size, token count, and hash."""
    content_bytes = content.encode("utf-8")
    return {
        "size_bytes": len(content_bytes),
        "token_count": token_counter.count_tokens(content),
        "content_hash": fs_manager.compute_hash(content),
    }


async def create_version_snapshot(
    file_path: Path,
    content: str,
    file_metrics: ModelDict,
    version_manager: VersionManager,
    change_description: str | None,
) -> VersionMetadata:
    """Create version snapshot."""
    file_name = file_path.name
    version = await version_manager.get_version_count(file_name)
    snapshot = await version_manager.create_snapshot(
        file_path,
        version=version + 1,
        content=content,
        size_bytes=cast(int, file_metrics.get("size_bytes", 0)),
        token_count=cast(int, file_metrics.get("token_count", 0)),
        content_hash=cast(str, file_metrics.get("content_hash", "")),
        change_type="modified",
        change_description=change_description or "Updated via MCP",
    )
    return snapshot


async def update_file_metadata(
    file_name: str,
    file_path: Path,
    content: str,
    file_metrics: ModelDict,
    metadata_index: MetadataIndex,
    version_info: VersionMetadata,
    token_counter: TokenCounter | None = None,
) -> None:
    """Update file metadata and version history."""
    sections_raw = extract_sections(content, token_counter=token_counter)
    sections = [section.model_dump(mode="json") for section in sections_raw]
    await metadata_index.update_file_metadata(
        file_name,
        path=file_path,
        exists=True,
        size_bytes=cast(int, file_metrics.get("size_bytes", 0)),
        token_count=cast(int, file_metrics.get("token_count", 0)),
        content_hash=cast(str, file_metrics.get("content_hash", "")),
        sections=sections,
        change_source="internal",
    )
    await metadata_index.add_version_to_history(
        file_name, version_info.model_dump(mode="json")
    )


async def handle_metadata_operation(
    file_path: Path, file_name: str, metadata_index: MetadataIndex
) -> str:
    """Handle metadata operation. Returns JSON response string."""
    metadata_raw = await metadata_index.get_file_metadata(file_name)
    metadata = metadata_raw if isinstance(metadata_raw, DetailedFileMetadata) else None
    file_exists = await _path_exists(file_path)

    # Prefer returning index metadata even if the underlying file is missing.
    # This makes metadata queries resilient to partial filesystem state and
    # supports tests that mock the index without creating on-disk files.
    if metadata is not None:
        return _metadata_success(file_name, file_exists, metadata)

    if not file_exists:
        return _metadata_error_missing_file(file_name)

    return _metadata_warning_no_metadata(file_name)
