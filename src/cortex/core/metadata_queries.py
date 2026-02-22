"""Query helpers and I/O for metadata index (read-only and load/save)."""

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import DetailedFileMetadata

from .async_file_utils import open_async_text_file
from .exceptions import IndexCorruptedError
from .retry import retry_async


def validate_index_consistency_from_data(
    data: dict[str, object] | None, memory_bank_dir: Path
) -> list[str]:
    """List stale file names (in index but not on disk).

    Args:
        data: Index data dict
        memory_bank_dir: Path to memory bank directory

    Returns:
        List of stale file names
    """
    if data is None:
        return []
    files_raw = data.get("files", {})
    if not isinstance(files_raw, dict):
        return []
    files_dict = cast(dict[str, object], files_raw)
    return [
        file_name
        for file_name in files_dict
        if not (memory_bank_dir / file_name).exists()
    ]


def get_file_metadata_from_data(
    data: dict[str, object] | None, file_name: str
) -> DetailedFileMetadata | None:
    """Get file metadata for a file from index data.

    Args:
        data: Index data dict
        file_name: Name of file

    Returns:
        File metadata model or None if not found
    """
    if data is None:
        return None
    files = data.get("files", {})
    if not isinstance(files, dict):
        return None
    files_typed = cast(dict[str, object], files)
    result_raw = files_typed.get(file_name)
    if isinstance(result_raw, dict):
        try:
            return DetailedFileMetadata.model_validate(
                cast(dict[str, object], result_raw)
            )
        except Exception:
            return None
    return None


def get_expected_hash_from_metadata(
    metadata: DetailedFileMetadata | None,
) -> str | None:
    """Get content hash from file metadata.

    Args:
        metadata: File metadata model

    Returns:
        Content hash string or None
    """
    if metadata is None:
        return None
    return metadata.content_hash


def get_all_files_metadata_from_data(
    data: dict[str, object] | None,
) -> dict[str, dict[str, object]]:
    """Get metadata for all files from index data.

    Args:
        data: Index data dict

    Returns:
        Dict mapping file names to metadata
    """
    if data is None:
        return {}
    files = data.get("files", {})
    if not isinstance(files, dict):
        return {}
    files_typed = cast(dict[str, object], files)
    return {
        str(k): cast(dict[str, object], v)
        for k, v in files_typed.items()
        if isinstance(v, dict)
    }


def list_all_files_from_data(data: dict[str, object] | None) -> list[str]:
    """List all file names from index data.

    Args:
        data: Index data dict

    Returns:
        List of file names
    """
    if data is None:
        return []
    files_dict = data.get("files", {})
    if not isinstance(files_dict, dict):
        return []
    files_dict_typed = cast(dict[str, object], files_dict)
    return list(files_dict_typed.keys())


def get_stats_from_data(data: dict[str, object] | None) -> dict[str, object]:
    """Get overall statistics from index data.

    Args:
        data: Index data dict

    Returns:
        Dict with totals, usage_analytics, file_count
    """
    if data is None:
        return {"totals": {}, "usage_analytics": {}, "file_count": 0}
    files_raw: object = data.get("files", {})
    file_count = (
        len(cast(dict[str, object], files_raw)) if isinstance(files_raw, dict) else 0
    )
    return {
        "totals": data.get("totals", {}),
        "usage_analytics": data.get("usage_analytics", {}),
        "file_count": file_count,
    }


def get_dependency_graph_from_data(data: dict[str, object] | None) -> dict[str, object]:
    """Get dependency graph from index data.

    Args:
        data: Index data dict

    Returns:
        Dependency graph dict
    """
    if data is None:
        return {}
    return cast(dict[str, object], data.get("dependency_graph", {}))


def validate_schema_impl(data: dict[str, object]) -> bool:
    """Return True if index data has required top-level keys."""
    required = [
        "schema_version",
        "files",
        "dependency_graph",
        "usage_analytics",
        "totals",
    ]
    return all(k in data for k in required)


def _dependency_graph_skeleton() -> dict[str, object]:
    """Empty dependency graph structure."""
    return {"nodes": [], "edges": [], "progressive_loading_order": []}


def _usage_analytics_skeleton(now: str) -> dict[str, object]:
    """Empty usage analytics structure."""
    return {
        "total_reads": 0,
        "total_writes": 0,
        "files_by_read_frequency": [],
        "files_by_write_frequency": [],
        "last_session_start": now,
        "sessions_count": 0,
    }


def _totals_skeleton(now: str) -> dict[str, object]:
    """Empty totals structure."""
    return {
        "total_files": 0,
        "total_size_bytes": 0,
        "total_tokens": 0,
        "last_full_scan": now,
    }


def _empty_index_dict(
    now: str,
    project_root: Path,
    memory_bank_dir: Path,
    schema_version: str,
) -> dict[str, object]:
    """Build the dict structure for an empty index."""
    return {
        "schema_version": schema_version,
        "created_at": now,
        "last_updated": now,
        "project_root": str(project_root),
        "memory_bank_dir": str(memory_bank_dir),
        "files": {},
        "dependency_graph": _dependency_graph_skeleton(),
        "usage_analytics": _usage_analytics_skeleton(now),
        "totals": _totals_skeleton(now),
    }


def create_empty_index_impl(
    project_root: Path,
    memory_bank_dir: Path,
    schema_version: str = "1.0.0",
) -> dict[str, object]:
    """Build empty index dict. Used by load/recover."""
    now = datetime.now().isoformat()
    return _empty_index_dict(now, project_root, memory_bank_dir, schema_version)


async def save_index_async(data: dict[str, object] | None, index_path: Path) -> None:
    """Write index data to disk with atomic rename and retry. No-op if data is None."""
    if data is None:
        return
    data["last_updated"] = datetime.now().isoformat()

    async def _write() -> None:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = index_path.with_suffix(".tmp")
        async with open_async_text_file(temp_path, "w", "utf-8") as f:
            _ = await f.write(json.dumps(data, indent=2))
        _ = temp_path.replace(index_path)

    await retry_async(
        _write,
        max_retries=3,
        base_delay=0.5,
        exceptions=(OSError, IOError, PermissionError),
    )


async def load_index_async(
    index_path: Path,
    memory_bank_dir: Path,
    project_root: Path,
    schema_version: str,
) -> dict[str, object]:
    """Load index from disk; create empty if missing; validate schema. Raises on corruption."""
    if not index_path.exists():
        data = create_empty_index_impl(project_root, memory_bank_dir, schema_version)
        await save_index_async(data, index_path)
        return data
    async with open_async_text_file(index_path, "r", "utf-8") as f:
        content = await f.read()
    data = json.loads(content)
    if data is not None and not validate_schema_impl(data):
        msg = (
            "Failed to load memory bank index: Invalid schema structure. Cause: "
            f"Missing required fields in index file at {index_path}. Try: Delete "
            "'.cortex/index.json' and run get_memory_bank_stats() to rebuild automatically."
        )
        raise IndexCorruptedError(msg)
    if data is None:
        data = create_empty_index_impl(project_root, memory_bank_dir, schema_version)
        await save_index_async(data, index_path)
    return data


async def recover_index_async(
    index_path: Path,
    project_root: Path,
    memory_bank_dir: Path,
    schema_version: str,
) -> dict[str, object]:
    """Backup corrupted index, create empty index, save and return it."""
    if index_path.exists():
        backup_path = index_path.with_suffix(".corrupted")
        _ = index_path.rename(backup_path)
    data = create_empty_index_impl(project_root, memory_bank_dir, schema_version)
    await save_index_async(data, index_path)
    return data


def file_exists_in_index_data(data: dict[str, object] | None, file_name: str) -> bool:
    """Check if file exists in index data.

    Args:
        data: Index data dict
        file_name: Name of file

    Returns:
        True if file is in index
    """
    if data is None:
        return False
    files = data.get("files", {})
    return isinstance(files, dict) and file_name in files
