#!/usr/bin/env python3
"""File change handlers and health monitoring for manager initialization."""

from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter


async def handle_file_change(file_path: Path, event_type: str) -> None:
    """Callback for file watcher to handle external file changes.

    This function is called when files are modified externally (outside MCP).
    It updates metadata and creates version snapshots if needed.

    Args:
        file_path: Path to changed file
        event_type: Type of change ('created', 'modified', 'deleted')
    """
    try:
        project_root = file_path.parent.parent  # memory-bank/file.md -> project_root
        from cortex.managers.initialization import get_managers

        mgrs = await get_managers(project_root)

        file_name = file_path.name
        # Core managers are marked as Required in ManagersDict
        metadata_index = mgrs.index
        fs_manager = mgrs.fs
        token_counter = mgrs.tokens

        if event_type == "deleted":
            await _handle_deleted_file(metadata_index, file_name, file_path)
        else:
            await _handle_modified_file(
                metadata_index, fs_manager, token_counter, file_name, file_path
            )
    except Exception:
        # Silently fail - don't disrupt file watcher
        pass


async def _handle_deleted_file(
    metadata_index: MetadataIndex, file_name: str, file_path: Path
) -> None:
    """Handle deleted file event."""
    await metadata_index.update_file_metadata(
        file_name=file_name,
        path=file_path,
        exists=False,
        size_bytes=0,
        token_count=0,
        content_hash="",
        sections=[],
        change_source="external",
    )


async def _handle_modified_file(
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
    file_name: str,
    file_path: Path,
) -> None:
    """Handle created or modified file event."""
    content, content_hash = await fs_manager.read_file(file_path)
    sections = fs_manager.parse_sections(content)
    token_count = token_counter.count_tokens(content)

    await metadata_index.update_file_metadata(
        file_name=file_name,
        path=file_path,
        exists=True,
        size_bytes=len(content.encode("utf-8")),
        token_count=token_count,
        content_hash=content_hash,
        sections=sections,
        change_source="external",
    )
