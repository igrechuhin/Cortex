"""Version history management with snapshot storage and rollback capabilities."""

from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from cortex.core.models import (
    DiskUsageInfo,
    FormattedVersionMetadata,
    ModelDict,
    VersionMetadata,
)

from .async_file_utils import open_async_text_file


def _as_version_metadata(version_meta: VersionMetadata | ModelDict) -> VersionMetadata:
    """Normalize VersionMetadata-like values to VersionMetadata."""
    if isinstance(version_meta, VersionMetadata):
        return version_meta
    return VersionMetadata.model_validate(version_meta)


def _short_content_hash(content_hash: str) -> str:
    """Shorten a long content hash for display."""
    return content_hash[:16] + "..." if len(content_hash) > 16 else content_hash


class VersionManager:
    """
    Manages version history for memory bank files.
    - Full file snapshots (not diffs) for simplicity
    - Automatic pruning to keep last N versions
    - Rollback capability
    """

    def __init__(self, project_root: Path, keep_versions: int = 10):
        """
        Initialize version manager.

        Args:
            project_root: Root directory of the project
            keep_versions: Number of versions to keep per file (default: 10)
        """
        self.project_root: Path = Path(project_root)
        self.history_dir: Path = self.project_root / ".cortex" / "history"
        self.keep_versions: int = keep_versions

    async def create_snapshot(
        self,
        file_path: Path,
        version: int,
        content: str,
        size_bytes: int,
        token_count: int,
        content_hash: str,
        change_type: Literal[
            "created", "modified", "rollback", "manual_backup"
        ] = "modified",
        changed_sections: list[str] | None = None,
        change_description: str | None = None,
    ) -> VersionMetadata:
        """
        Create a version snapshot for a file.

        Args:
            file_path: Path to the original file
            version: Version number
            content: File content to snapshot
            size_bytes: Size of content in bytes
            token_count: Token count
            content_hash: SHA-256 hash of content
            change_type: Type of change (created, modified, rollback)
            changed_sections: List of section headings that changed
            change_description: Optional description of changes

        Returns:
            Version metadata dict
        """
        self.history_dir.mkdir(parents=True, exist_ok=True)

        snapshot_path = await self._write_snapshot_file(file_path, version, content)
        version_meta = self._build_version_metadata(
            version,
            content_hash,
            size_bytes,
            token_count,
            change_type,
            snapshot_path,
            changed_sections,
            change_description,
        )

        await self.prune_versions(file_path.name)

        return version_meta

    async def _write_snapshot_file(
        self, file_path: Path, version: int, content: str
    ) -> Path:
        """Write snapshot file and return its path."""
        file_name = file_path.name
        snapshot_name = f"{file_name.replace('.md', '')}_v{version}.md"
        snapshot_path = self.history_dir / snapshot_name

        async with open_async_text_file(snapshot_path, "w", "utf-8") as f:
            _ = await f.write(content)

        return snapshot_path

    def _build_version_metadata(
        self,
        version: int,
        content_hash: str,
        size_bytes: int,
        token_count: int,
        change_type: Literal["created", "modified", "rollback", "manual_backup"],
        snapshot_path: Path,
        changed_sections: list[str] | None,
        change_description: str | None,
    ) -> VersionMetadata:
        """Build version metadata model."""
        from cortex.core.models import VersionMetadata

        return VersionMetadata(
            version=version,
            timestamp=datetime.now().isoformat(),
            content_hash=content_hash,
            size_bytes=size_bytes,
            token_count=token_count,
            change_type=change_type,
            snapshot_path=str(snapshot_path.relative_to(self.project_root)),
            changed_sections=changed_sections or [],
            change_description=change_description,
        )

    async def get_snapshot_content(self, snapshot_path: Path) -> str:
        """
        Read content from a version snapshot.

        Args:
            snapshot_path: Path to snapshot file (relative or absolute)

        Returns:
            Snapshot content

        Raises:
            FileNotFoundError: If snapshot doesn't exist
        """
        # Handle relative paths
        if not snapshot_path.is_absolute():
            snapshot_path = self.project_root / snapshot_path

        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

        async with open_async_text_file(snapshot_path, "r", "utf-8") as f:
            return await f.read()

    async def rollback_to_version(
        self,
        file_name: str,  # noqa: ARG002
        version_history: list[VersionMetadata],
        target_version: int,
    ) -> ModelDict | None:
        """
        Get snapshot content for rollback (does not modify files directly).

        Args:
            file_name: Name of file to rollback
            version_history: List of version metadata
            target_version: Version number to rollback to

        Returns:
            Snapshot info with content and metadata, or None if version not found
        """
        # Find target version in history
        target_version_meta: VersionMetadata | None = None
        for v in version_history:
            if v.version == target_version:
                target_version_meta = v
                break

        if not target_version_meta:
            return None

        # Read snapshot content
        snapshot_path_raw = target_version_meta.snapshot_path
        if not snapshot_path_raw:
            return None

        snapshot_path = Path(snapshot_path_raw)
        try:
            content = await self.get_snapshot_content(snapshot_path)
            metadata = cast(ModelDict, target_version_meta.model_dump(mode="json"))
            return {"content": content, "metadata": metadata}
        except FileNotFoundError:
            return None

    async def prune_versions(self, file_name: str):
        """
        Remove old version snapshots, keeping only the last N versions.

        Args:
            file_name: Name of file to prune versions for
        """
        if not self.history_dir.exists():
            return

        # Find all snapshots for this file
        base_name = file_name.replace(".md", "")
        pattern = f"{base_name}_v*.md"
        snapshots = sorted(self.history_dir.glob(pattern))

        # Keep only the most recent keep_versions snapshots
        if len(snapshots) > self.keep_versions:
            # Delete oldest snapshots
            for old_snapshot in snapshots[: -self.keep_versions]:
                try:
                    old_snapshot.unlink()
                except OSError:
                    # Snapshot inaccessible - skip
                    pass

    async def get_version_count(self, file_name: str) -> int:
        """
        Get number of versions stored for a file.

        Args:
            file_name: Name of file

        Returns:
            Number of versions
        """
        if not self.history_dir.exists():
            return 0

        base_name = file_name.replace(".md", "")
        pattern = f"{base_name}_v*.md"
        snapshots = list(self.history_dir.glob(pattern))
        return len(snapshots)

    async def get_disk_usage(self) -> DiskUsageInfo:
        """
        Get disk space used by version history.

        Returns:
            Disk usage information
        """
        if not self.history_dir.exists():
            return DiskUsageInfo(total_bytes=0, file_count=0)

        total_bytes = 0
        file_count = 0

        for snapshot in self.history_dir.glob("*.md"):
            try:
                total_bytes += snapshot.stat().st_size
                file_count += 1
            except OSError:
                # Snapshot inaccessible - skip
                pass

        return DiskUsageInfo(total_bytes=total_bytes, file_count=file_count)

    async def cleanup_orphaned_snapshots(self, valid_files: list[str]):
        """
        Remove snapshots for files that no longer exist in memory bank.

        Args:
            valid_files: List of current memory bank file names
        """
        if not self.history_dir.exists():
            return

        # Build set of valid base names
        valid_base_names = {f.replace(".md", "") for f in valid_files}

        # Check all snapshots
        for snapshot in self.history_dir.glob("*_v*.md"):
            if self._is_orphaned_snapshot(snapshot, valid_base_names):
                self._remove_snapshot(snapshot)

    def _is_orphaned_snapshot(self, snapshot: Path, valid_base_names: set[str]) -> bool:
        """Check if snapshot is orphaned (file no longer exists).

        Args:
            snapshot: Path to snapshot file
            valid_base_names: Set of valid base file names

        Returns:
            True if snapshot is orphaned
        """
        snapshot_name = snapshot.stem  # filename_v1
        parts = snapshot_name.rsplit("_v", 1)

        if len(parts) != 2:
            return False

        base_name = parts[0]
        return base_name not in valid_base_names

    def _remove_snapshot(self, snapshot: Path) -> None:
        """Remove an orphaned snapshot file.

        Args:
            snapshot: Path to snapshot file to remove
        """
        try:
            snapshot.unlink()
        except OSError:
            pass

    async def export_version_history(
        self,
        file_name: str,
        version_history: list[VersionMetadata | ModelDict],
        limit: int = 10,
    ) -> list[ModelDict]:
        """
        Export version history with human-readable formatting.

        Args:
            file_name: Name of file
            version_history: List of version metadata
            limit: Maximum number of versions to return (most recent)

        Returns:
            List of formatted version metadata
        """

        sorted_history = sorted(
            version_history, key=lambda v: _as_version_metadata(v).version, reverse=True
        )
        limited_history = sorted_history[:limit]

        formatted: list[ModelDict] = []
        for raw_meta in limited_history:
            meta = _as_version_metadata(raw_meta)
            entry = FormattedVersionMetadata(
                version=meta.version,
                timestamp=meta.timestamp,
                change_type=meta.change_type,
                size_bytes=meta.size_bytes,
                token_count=meta.token_count,
                content_hash=_short_content_hash(meta.content_hash),
                changed_sections=list(meta.changed_sections),
                description=meta.change_description,
            )
            formatted.append(entry.model_dump(mode="json"))

        return formatted

    def get_snapshot_path(self, file_name: str, version: int) -> Path:
        """
        Get path to a specific version snapshot.

        Args:
            file_name: Name of file
            version: Version number

        Returns:
            Path to snapshot file
        """
        base_name = file_name.replace(".md", "")
        snapshot_name = f"{base_name}_v{version}.md"
        return self.history_dir / snapshot_name
