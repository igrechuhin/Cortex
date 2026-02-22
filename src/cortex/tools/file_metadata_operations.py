"""File metadata operations: metrics, version snapshots, metadata updates.

Used by manage_file (read/write/metadata) and by internal write flow.
Kept separate to keep file_crud_operations under size limits.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict, VersionMetadata
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.tools.file_section_operations import extract_sections


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
    if not file_path.exists():
        return json.dumps(
            {
                "status": "error",
                "error": f"File {file_name} does not exist",
                "file_name": file_name,
            },
            indent=2,
        )

    metadata = await metadata_index.get_file_metadata(file_name)
    if not metadata:
        return json.dumps(
            {
                "status": "warning",
                "file_name": file_name,
                "metadata": None,
                "message": f"No metadata found for {file_name}",
            },
            indent=2,
        )

    return json.dumps(
        {
            "status": "success",
            "file_name": file_name,
            "metadata": metadata,
        },
        indent=2,
    )
