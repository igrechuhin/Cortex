"""Metadata index management with JSON storage and corruption recovery."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from cortex.core.models import DetailedFileMetadata, SectionMetadata
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

from .exceptions import IndexCorruptedError
from .metadata_cache import (
    add_version_to_history_impl,
    cleanup_stale_entries_impl,
    convert_version_meta_to_dict_impl,
    finalize_file_metadata_update_impl,
    get_files_dict_from_data,
    increment_read_count_impl,
    prepare_and_update_file_metadata_impl,
    recalculate_totals_impl,
    remove_file_impl,
    update_usage_analytics_impl,
)
from .metadata_queries import (
    create_empty_index_impl,
    file_exists_in_index_data,
    get_all_files_metadata_from_data,
    get_dependency_graph_from_data,
    get_expected_hash_from_metadata,
    get_file_metadata_from_data,
    get_stats_from_data,
    list_all_files_from_data,
    load_index_async,
    recover_index_async,
    save_index_async,
    validate_index_consistency_from_data,
    validate_schema_impl,
)

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


def _extract_section_mapping(
    section: SectionMetadata | SectionType | object,
) -> SectionType:
    """Best-effort conversion of a section to a mapping."""
    if isinstance(section, SectionMetadata):
        return cast(SectionType, section.model_dump(mode="json"))
    if isinstance(section, Mapping):
        return cast(SectionType, section)
    try:
        raw = vars(section)
    except TypeError:
        return cast(SectionType, {})
    return cast(SectionType, raw)


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
        self.cortex_dir: Path = get_cortex_path(
            self.project_root, CortexResourceType.CORTEX_DIR
        )
        self.index_path: Path = get_cortex_path(
            self.project_root, CortexResourceType.INDEX
        )
        self.memory_bank_dir: Path = get_cortex_path(
            self.project_root, CortexResourceType.MEMORY_BANK
        )
        self._data: dict[str, object] | None = None

    def _strip_version_history_from_index(self) -> bool:
        """
        Strip legacy version_history arrays from index data.

        Returns True if any entries were modified.
        """
        if self._data is None:
            return False
        files = self._data.get("files", {})
        if not isinstance(files, dict):
            return False
        files_typed = cast(dict[str, object], files)
        changed = False
        for meta in files_typed.values():
            if not isinstance(meta, dict):
                continue
            meta_typed = cast(dict[str, object], meta)
            if "version_history" in meta_typed:
                del meta_typed["version_history"]
                changed = True
        return changed

    def _make_path_relative(self, path: Path) -> str:
        """
        Normalize a filesystem path to be relative to project_root for index storage.

        This keeps .cortex/index.json machine-portable across different absolute
        locations as long as the project structure under project_root is the same.
        """
        try:
            return str(path.relative_to(self.project_root))
        except ValueError:
            # Fallback for legacy or out-of-tree paths; store as-is.
            return str(path)

    def _normalize_paths_in_index(self) -> bool:
        """
        Normalize stored file paths to be relative to project_root where possible.

        This migrates older indices that stored absolute paths so that
        .cortex/index.json remains portable across machines.
        """
        if self._data is None:
            return False
        files = self._data.get("files", {})
        if not isinstance(files, dict):
            return False
        files_typed = cast(dict[str, object], files)
        changed = False
        for meta in files_typed.values():
            if not isinstance(meta, dict):
                continue
            meta_typed = cast(dict[str, object], meta)
            raw_path = meta_typed.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                continue
            new_path = self._make_path_relative(Path(raw_path))
            if new_path != raw_path:
                meta_typed["path"] = new_path
                changed = True
        return changed

    def _normalize_top_level_paths(self) -> bool:
        """
        Normalize project_root and memory_bank_dir fields to be relative.

        This migrates legacy indices that stored absolute paths so that
        .cortex/index.json stays machine-portable.
        """
        if self._data is None:
            return False
        changed = False

        project_root_raw = self._data.get("project_root")
        if (
            isinstance(project_root_raw, str)
            and project_root_raw
            and project_root_raw != "."
        ):
            self._data["project_root"] = "."
            changed = True

        memory_bank_dir_raw = self._data.get("memory_bank_dir")
        if isinstance(memory_bank_dir_raw, str) and memory_bank_dir_raw:
            new_mb = memory_bank_dir_raw
            try:
                new_mb = str(Path(memory_bank_dir_raw).relative_to(self.project_root))
            except ValueError:
                # If it cannot be made relative, keep existing value.
                new_mb = memory_bank_dir_raw
            if new_mb != memory_bank_dir_raw:
                self._data["memory_bank_dir"] = new_mb
                changed = True

        return changed

    async def load(self) -> dict[str, object]:
        """
        Load metadata index with corruption recovery.

        Returns:
            Index data as dictionary

        Raises:
            IndexCorruptedError: If index is corrupted and cannot be recovered
        """
        try:
            self._data = await load_index_async(
                self.index_path,
                self.memory_bank_dir,
                self.project_root,
                self.SCHEMA_VERSION,
            )
        except (json.JSONDecodeError, IndexCorruptedError):
            self._data = await recover_index_async(
                self.index_path,
                self.project_root,
                self.memory_bank_dir,
                self.SCHEMA_VERSION,
            )
        changed = False
        if self._strip_version_history_from_index():
            changed = True
        if self._normalize_paths_in_index():
            changed = True
        if self._normalize_top_level_paths():
            changed = True
        if changed:
            await self.save()
        return self._data

    async def save(self):
        """Save metadata index with atomic write and retry logic."""
        await save_index_async(self._data, self.index_path)

    def create_empty_index(self) -> dict[str, object]:
        """Create a new empty index with proper structure."""
        return create_empty_index_impl(
            self.project_root, self.memory_bank_dir, self.SCHEMA_VERSION
        )

    def validate_schema(self, data: dict[str, object]) -> bool:
        """Validate index schema. Returns True if valid."""
        return validate_schema_impl(data)

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
        files_dict = get_files_dict_from_data(self._data)
        # Store path relative to project_root so index.json is machine-portable.
        relative_path = Path(self._make_path_relative(path))
        file_meta, now = prepare_and_update_file_metadata_impl(
            files_dict,
            file_name,
            relative_path,
            exists,
            change_source,
            [SectionMetadata.model_validate(s) for s in _normalize_sections(sections)],
            size_bytes,
            token_count,
            content_hash,
        )
        finalize_file_metadata_update_impl(
            self._data, files_dict, file_name, file_meta, change_source, now
        )
        await self.save()

    def _get_files_dict(self) -> dict[str, object]:
        """Get files dictionary from index data."""
        return get_files_dict_from_data(self._data)

    async def add_version_to_history(
        self, file_name: str, version_meta: dict[str, object] | object
    ):
        """
        Add a version entry to file's history.

        Args:
            file_name: Name of file
            version_meta: Version metadata dict or VersionMetadata object
        """
        version_meta_dict = convert_version_meta_to_dict_impl(version_meta)
        if version_meta_dict is None:
            return

        if self._data is None:
            _ = await self.load()

        if self._data is None:
            return

        add_version_to_history_impl(self._data, file_name, version_meta_dict)
        await self.save()

    async def increment_read_count(self, file_name: str):
        """
        Increment read count for a file.

        Args:
            file_name: Name of file
        """
        if self._data is None:
            _ = await self.load()
        if increment_read_count_impl(self._data, file_name):
            await self.save()

    async def recalculate_totals(self):
        """Recalculate total statistics."""
        recalculate_totals_impl(self._data)

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

    async def get_file_metadata(self, file_name: str) -> DetailedFileMetadata | None:
        """
        Get metadata for a specific file.

        Args:
            file_name: Name of file

        Returns:
            File metadata model or None if not found
        """
        if self._data is None:
            _ = await self.load()
        return get_file_metadata_from_data(self._data, file_name)

    async def get_expected_hash(self, file_name: str) -> str | None:
        """
        Get expected content hash for a file.

        Args:
            file_name: Name of file

        Returns:
            Content hash string or None if not found
        """
        metadata = await self.get_file_metadata(file_name)
        return get_expected_hash_from_metadata(metadata)

    async def get_all_files_metadata(self) -> dict[str, dict[str, object]]:
        """
        Get metadata for all files.

        Returns:
            Dict mapping file names to metadata
        """
        if self._data is None:
            _ = await self.load()
        return get_all_files_metadata_from_data(self._data)

    async def list_all_files(self) -> list[str]:
        """
        List all file names in the index.

        Returns:
            List of file names
        """
        if self._data is None:
            _ = await self.load()
        return list_all_files_from_data(self._data)

    async def get_stats(self) -> dict[str, object]:
        """
        Get overall statistics.

        Returns:
            Dict with totals and analytics
        """
        if self._data is None:
            _ = await self.load()
        return get_stats_from_data(self._data)

    async def get_dependency_graph(self) -> dict[str, object]:
        """
        Get dependency graph.

        Returns:
            Dependency graph dict
        """
        if self._data is None:
            _ = await self.load()
        return get_dependency_graph_from_data(self._data)

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
        return file_exists_in_index_data(self._data, file_name)

    async def remove_file(self, file_name: str):
        """
        Remove file from index.

        Args:
            file_name: Name of file to remove
        """
        if self._data is None:
            _ = await self.load()
        if remove_file_impl(self._data, file_name):
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
        return validate_index_consistency_from_data(self._data, self.memory_bank_dir)

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
        n = cleanup_stale_entries_impl(self._data, stale_files, dry_run=False)
        if n:
            await self.save()
        return n

    def get_data(self) -> dict[str, object] | None:
        """Get raw index data (for testing/debugging)."""
        return self._data

    async def update_usage_analytics(self):
        """Update usage analytics with current file access patterns."""
        if self._data is None:
            _ = await self.load()
        if self._data is None:
            return
        update_usage_analytics_impl(self._data)
        await self.save()
