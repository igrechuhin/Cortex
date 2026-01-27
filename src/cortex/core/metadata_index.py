"""Metadata index management with JSON storage and corruption recovery."""

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import cast

from .async_file_utils import open_async_text_file
from .exceptions import IndexCorruptedError
from .retry import retry_async

# Type alias for section metadata - accepts various dict types with
# str/int/object values
SectionType = Mapping[str, str | int | object]


def _normalize_sections(
    sections: Sequence[SectionType | object],
) -> list[SectionType]:
    """Normalize sections to SectionType (dict-like) format.

    Converts SectionMetadata objects to dicts if needed.
    """
    from cortex.core.models import SectionMetadata

    normalized: list[SectionType] = []
    for section in sections:
        if isinstance(section, SectionMetadata):
            normalized.append(section.model_dump(mode="json"))
        elif isinstance(section, Mapping):
            normalized.append(cast(SectionType, section))
        else:
            normalized.append(_extract_section_mapping(section))
    return normalized


def _extract_section_mapping(section: object) -> SectionType:
    """Best-effort conversion of a section to a mapping."""
    try:
        raw = vars(section)
    except TypeError:
        return cast(SectionType, {})
    return cast(SectionType, raw)


def _try_model_dump(value: object) -> dict[str, object] | None:
    """Best-effort call to Pydantic-style model_dump()."""
    model_dump_raw: object = getattr(value, "model_dump", None)
    if not callable(model_dump_raw):
        return None

    try:
        dumped = model_dump_raw(mode="json")
    except TypeError:
        return None
    if isinstance(dumped, dict):
        return cast(dict[str, object], dumped)
    return None


class MetadataIndex:
    """
    Manages the .cortex/index.json file with:
    - JSON-based storage (human-readable)
    - Atomic writes (write to temp, then rename)
    - Corruption recovery (rebuild from markdown files)
    - Schema validation
    """

    SCHEMA_VERSION: str = "1.0.0"

    def __init__(self, project_root: Path):
        """
        Initialize metadata index manager.

        Args:
            project_root: Root directory of the project
        """
        self.project_root: Path = Path(project_root)
        self.cortex_dir: Path = self.project_root / ".cortex"
        self.index_path: Path = self.cortex_dir / "index.json"
        self.memory_bank_dir: Path = self.cortex_dir / "memory-bank"
        self._data: dict[str, object] | None = None

    async def load(self) -> dict[str, object]:
        """
        Load metadata index with corruption recovery.

        Returns:
            Index data as dictionary

        Raises:
            IndexCorruptedError: If index is corrupted and cannot be recovered
        """
        if not self.index_path.exists():
            # No index yet - create empty one
            self._data = self.create_empty_index()
            await self.save()
            return self._data

        try:
            # Try to load existing index
            async with open_async_text_file(self.index_path, "r", "utf-8") as f:
                content = await f.read()
                self._data = json.loads(content)

            # Validate schema
            if self._data is not None and not self.validate_schema(self._data):
                raise IndexCorruptedError(
                    (
                        "Failed to load memory bank index: Invalid schema "
                        "structure. Cause: Missing required fields in index "
                        f"file at {self.index_path}. Try: Delete "
                        "'.cortex/index.json' and run get_memory_bank_stats() "
                        "to rebuild automatically."
                    )
                )

            if self._data is None:
                self._data = self.create_empty_index()
                await self.save()

            return self._data

        except (json.JSONDecodeError, IndexCorruptedError) as e:
            # Index is corrupted - attempt recovery
            error_msg = self._build_corruption_error_message(e)
            return await self._recover_from_corruption(error_msg)

    def _build_corruption_error_message(
        self, e: json.JSONDecodeError | IndexCorruptedError
    ) -> str:
        """Build error message for corruption recovery."""
        if isinstance(e, json.JSONDecodeError):
            return (
                f"Failed to load memory bank index: Invalid JSON at "
                f"line {e.lineno}. Cause: {e.msg}. Try: Delete "
                f"'.cortex/index.json' file and run any read operation "
                "to rebuild automatically."
            )
        return str(e)

    async def save(self):
        """
        Save metadata index with atomic write and retry logic.
        Writes to temp file first, then renames to ensure atomicity.
        """
        if self._data is None:
            return

        # Update last_updated timestamp
        self._data["last_updated"] = datetime.now().isoformat()

        async def save_operation() -> None:
            # Ensure parent directory exists
            self.index_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file
            temp_path = self.index_path.with_suffix(".tmp")

            async with open_async_text_file(temp_path, "w", "utf-8") as f:
                _ = await f.write(json.dumps(self._data, indent=2))

            # Atomic rename
            _ = temp_path.replace(self.index_path)

        await retry_async(
            save_operation,
            max_retries=3,
            base_delay=0.5,
            exceptions=(OSError, IOError, PermissionError),
        )

    def create_empty_index(self) -> dict[str, object]:
        """Create a new empty index with proper structure."""
        return {
            "schema_version": self.SCHEMA_VERSION,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "memory_bank_dir": str(self.memory_bank_dir),
            "files": {},
            "dependency_graph": {
                "nodes": [],
                "edges": [],
                "progressive_loading_order": [],
            },
            "usage_analytics": {
                "total_reads": 0,
                "total_writes": 0,
                "files_by_read_frequency": [],
                "files_by_write_frequency": [],
                "last_session_start": datetime.now().isoformat(),
                "sessions_count": 0,
            },
            "totals": {
                "total_files": 0,
                "total_size_bytes": 0,
                "total_tokens": 0,
                "last_full_scan": datetime.now().isoformat(),
            },
        }

    def validate_schema(self, data: dict[str, object]) -> bool:
        """
        Validate index schema.

        Args:
            data: Index data to validate

        Returns:
            True if valid
        """
        required_keys = [
            "schema_version",
            "files",
            "dependency_graph",
            "usage_analytics",
            "totals",
        ]

        return all(key in data for key in required_keys)

    async def _recover_from_corruption(
        self, reason: str
    ) -> dict[str, object]:  # noqa: ARG002
        """
        Recover from corrupted index by rebuilding from markdown files.

        Args:
            reason: Reason for corruption

        Returns:
            Rebuilt index data
        """
        # Backup corrupted index
        if self.index_path.exists():
            backup_path = self.index_path.with_suffix(".corrupted")
            _ = self.index_path.rename(backup_path)

        # Create new empty index
        self._data = self.create_empty_index()

        # Note: Actual file scanning will be done by the calling code
        # This just creates the structure

        await self.save()
        return self._data

    def _prepare_file_metadata_update(
        self,
        files_dict: dict[str, object],
        file_name: str,
        path: Path,
        exists: bool,
        change_source: str,
        sections: Sequence[SectionType],
    ) -> tuple[dict[str, object], str, list[SectionType]]:
        """Prepare file metadata for update.

        Args:
            files_dict: Files dictionary from index
            file_name: Name of file
            path: Absolute path to file
            exists: Whether file exists
            change_source: "internal" or "external"
            sections: List of section metadata dicts

        Returns:
            Tuple of (file_meta dict, current timestamp ISO string, normalized sections)
        """
        file_meta = self._get_or_create_file_metadata(
            files_dict, file_name, path, exists, change_source
        )
        now = datetime.now().isoformat()
        normalized_sections = _normalize_sections(sections)
        return file_meta, now, normalized_sections

    async def update_file_metadata(
        self,
        file_name: str,
        path: Path,
        exists: bool,
        size_bytes: int,
        token_count: int,
        content_hash: str,
        sections: Sequence[SectionType],
        change_source: str = "internal",
    ):
        """
        Update metadata for a single file.

        Args:
            file_name: Name of file
            path: Absolute path to file
            exists: Whether file exists
            size_bytes: Size in bytes
            token_count: Token count
            content_hash: SHA-256 hash
            sections: List of section metadata dicts
            change_source: "internal" (via MCP) or "external" (file watcher)
        """
        if self._data is None:
            _ = await self.load()

        files_dict = self._get_files_dict()
        file_meta, now, normalized_sections = self._prepare_file_metadata_update(
            files_dict, file_name, path, exists, change_source, sections
        )

        self._update_file_metadata_fields(
            file_meta,
            exists,
            size_bytes,
            token_count,
            content_hash,
            normalized_sections,
            now,
        )

        await self._finalize_file_metadata_update(
            files_dict, file_name, file_meta, change_source, now
        )

    async def _finalize_file_metadata_update(
        self,
        files_dict: dict[str, object],
        file_name: str,
        file_meta: dict[str, object],
        change_source: str,
        now: str,
    ):
        """Finalize file metadata update and save.

        Args:
            files_dict: Files dictionary from index
            file_name: Name of file
            file_meta: File metadata dictionary
            change_source: "internal" or "external"
            now: Current timestamp ISO string
        """
        if change_source == "internal":
            file_meta["last_read"] = now

        files_dict[file_name] = file_meta
        if self._data is not None:
            self._data["files"] = files_dict

        await self.recalculate_totals()
        await self.save()

    def _get_files_dict(self) -> dict[str, object]:
        """Get files dictionary from index data.

        Returns:
            Files dictionary
        """
        files_dict: dict[str, object] = {}
        if (
            self._data is not None
            and "files" in self._data
            and isinstance(self._data["files"], dict)
        ):
            files_dict_raw = self._data.get("files", {})
            if isinstance(files_dict_raw, dict):
                files_dict_raw_typed = cast(dict[str, object], files_dict_raw)
                for k, v in files_dict_raw_typed.items():
                    files_dict[str(k)] = v
        return files_dict

    def _get_or_create_file_metadata(
        self,
        files_dict: dict[str, object],
        file_name: str,
        path: Path,
        exists: bool,
        change_source: str,
    ) -> dict[str, object]:
        """Get existing file metadata or create new.

        Args:
            files_dict: Files dictionary from index
            file_name: Name of file
            path: Absolute path to file
            exists: Whether file exists
            change_source: "internal" or "external"

        Returns:
            File metadata dictionary
        """
        if file_name in files_dict:
            file_meta_raw = files_dict[file_name]
            if isinstance(file_meta_raw, dict):
                file_meta = cast(dict[str, object], file_meta_raw.copy())
                self._update_file_counters(file_meta, change_source)
                return file_meta

        return self._create_new_file_metadata(path, exists, change_source)

    def _update_file_counters(self, file_meta: dict[str, object], change_source: str):
        """Update read/write counters based on change source.

        Args:
            file_meta: File metadata dictionary
            change_source: "internal" or "external"
        """
        write_count = file_meta.get("write_count", 0)
        read_count = file_meta.get("read_count", 0)

        write_count = int(write_count) if isinstance(write_count, (int, float)) else 0
        read_count = int(read_count) if isinstance(read_count, (int, float)) else 0

        if change_source == "internal":
            file_meta["write_count"] = write_count + 1
        else:
            file_meta["read_count"] = read_count + 1

    def _create_new_file_metadata(
        self, path: Path, exists: bool, change_source: str
    ) -> dict[str, object]:
        """Create new file metadata dictionary.

        Args:
            path: Absolute path to file
            exists: Whether file exists
            change_source: "internal" or "external"

        Returns:
            New file metadata dictionary
        """
        return {
            "path": str(path),
            "exists": exists,
            "read_count": 0,
            "write_count": 1 if change_source == "internal" else 0,
            "current_version": 0,
            "version_history": [],
        }

    def _update_file_metadata_fields(
        self,
        file_meta: dict[str, object],
        exists: bool,
        size_bytes: int,
        token_count: int,
        content_hash: str,
        sections: Sequence[SectionType],
        now: str,
    ):
        """Update basic metadata fields.

        Args:
            file_meta: File metadata dictionary to update
            exists: Whether file exists
            size_bytes: Size in bytes
            token_count: Token count
            content_hash: SHA-256 hash
            sections: List of section metadata dicts
            now: Current timestamp ISO string
        """
        file_meta.update(
            {
                "exists": exists,
                "size_bytes": size_bytes,
                "token_count": token_count,
                "token_model": "cl100k_base",
                "last_modified": now,
                "content_hash": content_hash,
                "sections": sections,
            }
        )

    def _convert_version_meta_to_dict(
        self, version_meta: dict[str, object] | object
    ) -> dict[str, object] | None:
        """Convert version metadata to dict format.

        Args:
            version_meta: Version metadata dict or VersionMetadata object

        Returns:
            Version metadata dict or None if conversion fails
        """
        from cortex.core.models import VersionMetadata

        if isinstance(version_meta, VersionMetadata):
            return version_meta.model_dump(mode="json")
        version_meta_dict = _try_model_dump(version_meta)
        if version_meta_dict is None and isinstance(version_meta, dict):
            return cast(dict[str, object], version_meta)
        return version_meta_dict

    def _get_file_meta_for_version_update(
        self, file_name: str
    ) -> dict[str, object] | None:
        """Get file metadata for version update.

        Args:
            file_name: Name of file

        Returns:
            File metadata dict or None if not found
        """
        if self._data is None:
            return None

        files = self._data.get("files", {})
        if not isinstance(files, dict) or file_name not in files:
            return None

        files_typed = cast(dict[str, object], files)
        file_meta_raw: object = files_typed[file_name]
        if not isinstance(file_meta_raw, dict):
            return None

        return cast(dict[str, object], file_meta_raw)

    async def add_version_to_history(
        self, file_name: str, version_meta: dict[str, object] | object
    ):
        """
        Add a version entry to file's history.

        Args:
            file_name: Name of file
            version_meta: Version metadata dict or VersionMetadata object
        """
        version_meta_dict = self._convert_version_meta_to_dict(version_meta)
        if version_meta_dict is None:
            return

        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return

        file_meta = self._get_file_meta_for_version_update(file_name)
        if file_meta is None:
            return

        file_meta["current_version"] = version_meta_dict["version"]

        if "version_history" not in file_meta:
            file_meta["version_history"] = []

        version_history_raw = file_meta.get("version_history")
        if isinstance(version_history_raw, list):
            version_history = cast(list[dict[str, object]], version_history_raw)
            version_history.append(version_meta_dict)
        else:
            file_meta["version_history"] = [version_meta_dict]

        await self.save()

    async def increment_read_count(self, file_name: str):
        """
        Increment read count for a file.

        Args:
            file_name: Name of file
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return

        files = self._data.get("files", {})
        if isinstance(files, dict) and file_name in files:
            files_typed = cast(dict[str, object], files)
            file_entry_raw: object = files_typed[file_name]
            if isinstance(file_entry_raw, dict):
                file_entry: dict[str, object] = cast(dict[str, object], file_entry_raw)
                read_count_raw: object = file_entry.get("read_count", 0)
                if isinstance(read_count_raw, (int, float)):
                    file_entry["read_count"] = int(read_count_raw) + 1
                else:
                    file_entry["read_count"] = 1
                file_entry["last_read"] = datetime.now().isoformat()

            # Update analytics
            usage_analytics_raw: object = self._data.get("usage_analytics", {})
            if isinstance(usage_analytics_raw, dict):
                usage_analytics: dict[str, object] = cast(
                    dict[str, object], usage_analytics_raw
                )
                total_reads_raw: object = usage_analytics.get("total_reads", 0)
                if isinstance(total_reads_raw, (int, float)):
                    usage_analytics["total_reads"] = int(total_reads_raw) + 1
                else:
                    usage_analytics["total_reads"] = 1

            await self.save()

    async def recalculate_totals(self):
        """Recalculate total statistics."""
        if self._data is None:
            return

        files = self._data.get("files", {})
        if not isinstance(files, dict):
            return

        files_typed = cast(dict[str, object], files)
        total_files = len(files_typed)
        total_size = 0
        for f_raw in files_typed.values():
            if isinstance(f_raw, dict):
                f_dict_size: dict[str, object] = cast(dict[str, object], f_raw)
                size_bytes_raw: object = f_dict_size.get("size_bytes", 0)
                if isinstance(size_bytes_raw, (int, float)):
                    total_size += int(size_bytes_raw)

        total_tokens = 0
        for f_raw in files_typed.values():
            if isinstance(f_raw, dict):
                f_dict_tokens: dict[str, object] = cast(dict[str, object], f_raw)
                token_count_raw: object = f_dict_tokens.get("token_count", 0)
                if isinstance(token_count_raw, (int, float)):
                    total_tokens += int(token_count_raw)

        self._data["totals"] = {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_tokens": total_tokens,
            "last_full_scan": datetime.now().isoformat(),
        }

    async def update_dependency_graph(self, graph_dict: dict[str, object]):
        """
        Update dependency graph in index.

        Args:
            graph_dict: Dependency graph as dict (from DependencyGraph.to_dict())
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return

        self._data["dependency_graph"] = graph_dict
        await self.save()

    async def get_file_metadata(self, file_name: str) -> dict[str, object] | None:
        """
        Get metadata for a specific file.

        Args:
            file_name: Name of file

        Returns:
            File metadata dict or None if not found
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return None

        files = self._data.get("files", {})
        if isinstance(files, dict):
            files_typed = cast(dict[str, object], files)
            result_raw: object = files_typed.get(file_name)
            if isinstance(result_raw, dict):
                return cast(dict[str, object], result_raw)
        return None

    async def get_expected_hash(self, file_name: str) -> str | None:
        """
        Get expected content hash for a file.

        Args:
            file_name: Name of file

        Returns:
            Content hash string or None if not found
        """
        metadata = await self.get_file_metadata(file_name)
        if metadata is None:
            return None

        content_hash_raw: object = metadata.get("content_hash")
        if isinstance(content_hash_raw, str):
            return content_hash_raw
        return None

    async def get_all_files_metadata(self) -> dict[str, dict[str, object]]:
        """
        Get metadata for all files.

        Returns:
            Dict mapping file names to metadata
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return {}

        files = self._data.get("files", {})
        if isinstance(files, dict):
            files_typed = cast(dict[str, object], files)
            return {
                str(k): cast(dict[str, object], v)
                for k, v in files_typed.items()
                if isinstance(v, dict)
            }
        return {}

    async def list_all_files(self) -> list[str]:
        """
        List all file names in the index.

        Returns:
            List of file names
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return []

        files_dict = self._data.get("files", {})
        if isinstance(files_dict, dict):
            files_dict_typed = cast(dict[str, object], files_dict)
            return list(files_dict_typed.keys())
        return []

    async def get_stats(self) -> dict[str, object]:
        """
        Get overall statistics.

        Returns:
            Dict with totals and analytics
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return {"totals": {}, "usage_analytics": {}, "file_count": 0}

        files = self._data.get("files", {})
        if isinstance(files, dict):
            files_typed = cast(dict[str, object], files)
            file_count = len(files_typed)
        else:
            file_count = 0

        return {
            "totals": self._data.get("totals", {}),
            "usage_analytics": self._data.get("usage_analytics", {}),
            "file_count": file_count,
        }

    async def get_dependency_graph(self) -> dict[str, object]:
        """
        Get dependency graph.

        Returns:
            Dependency graph dict
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return {}

        return cast(dict[str, object], self._data.get("dependency_graph", {}))

    async def file_exists_in_index(self, file_name: str) -> bool:
        """
        Check if file exists in index.

        Args:
            file_name: Name of file

        Returns:
            True if file is in index
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return False

        files = self._data.get("files", {})
        return isinstance(files, dict) and file_name in files

    async def remove_file(self, file_name: str):
        """
        Remove file from index.

        Args:
            file_name: Name of file to remove
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return

        files = self._data.get("files", {})
        if isinstance(files, dict) and file_name in files:
            del files[file_name]
            self._data["files"] = files
            await self.recalculate_totals()
            await self.save()

    async def validate_index_consistency(self) -> list[str]:
        """Validate index consistency with filesystem.

        Checks all files in index against actual filesystem and
        identifies stale entries (in index but not on disk).

        Returns:
            List of stale file names (in index but not on disk)
        """
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return []

        stale_files: list[str] = []
        files_raw = self._data.get("files", {})
        if not isinstance(files_raw, dict):
            return []

        files_dict = cast(dict[str, object], files_raw)

        for file_name in files_dict.keys():
            file_path = self.memory_bank_dir / file_name
            if not file_path.exists():
                stale_files.append(file_name)

        return stale_files

    async def cleanup_stale_entries(self, dry_run: bool = False) -> int:
        """Remove stale entries from index.

        Args:
            dry_run: If True, only report what would be cleaned

        Returns:
            Number of entries cleaned
        """
        stale_files = await self.validate_index_consistency()

        if not stale_files:
            return 0

        if dry_run:
            return len(stale_files)

        # Remove stale entries
        if self._data is None:
            return 0

        files_raw = self._data.get("files", {})
        if not isinstance(files_raw, dict):
            return 0

        files_dict = cast(dict[str, object], files_raw)
        for file_name in stale_files:
            if file_name in files_dict:
                del files_dict[file_name]

        self._data["files"] = files_dict
        await self.recalculate_totals()
        await self.save()
        return len(stale_files)

    def get_data(self) -> dict[str, object] | None:
        """Get raw index data (for testing/debugging)."""
        return self._data

    def _extract_read_counts(self, files: dict[str, object]) -> list[dict[str, object]]:
        """Extract read counts from files data.

        Args:
            files: Dictionary of file metadata

        Returns:
            List of file read count dictionaries
        """
        files_by_reads_list: list[dict[str, object]] = []
        for fname, fdata in files.items():
            if isinstance(fdata, dict):
                fdata_typed = cast(dict[str, object], fdata)
                read_count_raw: object = fdata_typed.get("read_count", 0)
                read_count: int = (
                    int(read_count_raw)
                    if isinstance(read_count_raw, (int, float))
                    else 0
                )
                files_by_reads_list.append({"file": str(fname), "reads": read_count})
        return files_by_reads_list

    def _extract_write_counts(
        self, files: dict[str, object]
    ) -> list[dict[str, object]]:
        """Extract write counts from files data.

        Args:
            files: Dictionary of file metadata

        Returns:
            List of file write count dictionaries
        """
        files_by_writes_list: list[dict[str, object]] = []
        for fname, fdata in files.items():
            if isinstance(fdata, dict):
                fdata_typed = cast(dict[str, object], fdata)
                write_count_raw: object = fdata_typed.get("write_count", 0)
                write_count: int = (
                    int(write_count_raw)
                    if isinstance(write_count_raw, (int, float))
                    else 0
                )
                files_by_writes_list.append({"file": str(fname), "writes": write_count})
        return files_by_writes_list

    def _sort_files_by_frequency(
        self, files_list: list[dict[str, object]], frequency_key: str
    ) -> list[dict[str, object]]:
        """Sort files by frequency (reads or writes).

        Args:
            files_list: List of file frequency dictionaries
            frequency_key: Key to sort by ("reads" or "writes")

        Returns:
            Sorted list of file frequency dictionaries
        """

        def get_frequency_key(x: dict[str, object]) -> int:
            freq_val: object = x.get(frequency_key, 0)
            if isinstance(freq_val, (int, float)):
                return int(freq_val)
            return 0

        return sorted(files_list, key=get_frequency_key, reverse=True)

    def _update_analytics_data(
        self,
        files_by_reads: list[dict[str, object]],
        files_by_writes: list[dict[str, object]],
    ) -> None:
        """Update usage analytics data in index.

        Args:
            files_by_reads: Sorted list of files by read frequency
            files_by_writes: Sorted list of files by write frequency
        """
        if self._data is None:
            return
        usage_analytics = self._data.get("usage_analytics", {})
        if isinstance(usage_analytics, dict):
            usage_analytics["files_by_read_frequency"] = files_by_reads[:10]
            usage_analytics["files_by_write_frequency"] = files_by_writes[:10]
            self._data["usage_analytics"] = usage_analytics

    async def update_usage_analytics(self):
        """Update usage analytics with current file access patterns."""
        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return

        files = self._data.get("files", {})
        if not isinstance(files, dict):
            return

        files_typed = cast(dict[str, object], files)
        files_by_reads_list = self._extract_read_counts(files_typed)
        files_by_reads = self._sort_files_by_frequency(files_by_reads_list, "reads")

        files_by_writes_list = self._extract_write_counts(files_typed)
        files_by_writes = self._sort_files_by_frequency(files_by_writes_list, "writes")

        self._update_analytics_data(files_by_reads, files_by_writes)
        await self.save()
