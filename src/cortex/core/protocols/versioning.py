#!/usr/bin/env python3
"""Version management protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for version management,
enabling structural subtyping for better abstraction and reduced circular
dependencies.
"""

from typing import Protocol


class VersionManagerProtocol(Protocol):
    """Protocol for version management using structural subtyping (PEP 544).

    This protocol defines the interface for creating file version snapshots,
    tracking version history, and rolling back to previous versions. Version
    management provides safety and auditability for content changes. Any class
    implementing these methods automatically satisfies this protocol.

    Used by:
        - VersionManager: File-based version storage with metadata
        - FileSystemManager: For automatic versioning on writes
        - RollbackManager: For restoring previous content versions
        - MCP Tools: For version history queries and rollbacks

    Example implementation:
        ```python
        import json
        from datetime import datetime
        from cortex.core.async_file_utils import open_async_text_file

        class SimpleVersionManager:
            def __init__(self, versions_dir: Path):
                self.versions_dir = versions_dir
                self.versions_dir.mkdir(exist_ok=True)

            async def create_snapshot(
                self, file_name: str, content: str, metadata: dict[str, object] | None = None
            ) -> str:
                snapshot_id = f"{file_name}_{datetime.utcnow().isoformat()}"
                snapshot_path = self.versions_dir / f"{snapshot_id}.snapshot"

                snapshot_data = {
                    "snapshot_id": snapshot_id,
                    "file_name": file_name,
                    "content": content,
                    "timestamp": datetime.utcnow().isoformat(),
                    "metadata": metadata or {},
                }

                async with open_async_text_file(snapshot_path, "w", "utf-8") as f:
                    await f.write(json.dumps(snapshot_data))

                return snapshot_id

            async def get_version_history(self, file_name: str) -> list[dict[str, object]]:
                history = []
                for snapshot_file in self.versions_dir.glob(f"{file_name}_*.snapshot"):
                    async with open_async_text_file(snapshot_file, "r", "utf-8") as f:
                        data = json.loads(await f.read())
                        history.append({
                            "snapshot_id": data["snapshot_id"],
                            "timestamp": data["timestamp"],
                            "metadata": data["metadata"],
                        })
                return sorted(history, key=lambda x: x["timestamp"], reverse=True)

            async def rollback_to_version(self, snapshot_id: str) -> dict[str, object]:
                snapshot_path = self.versions_dir / f"{snapshot_id}.snapshot"
                async with open_async_text_file(snapshot_path, "r", "utf-8") as f:
                    data = json.loads(await f.read())
                return {
                    "file_name": data["file_name"],
                    "content": data["content"],
                    "restored_from": snapshot_id,
                }

        # SimpleVersionManager automatically satisfies VersionManagerProtocol
        ```

    Note:
        - Snapshots include metadata for auditability
        - Version history ordered by timestamp
        - Rollback restores exact file state
    """

    async def create_snapshot(
        self, file_name: str, content: str, metadata: dict[str, object] | None = None
    ) -> str:
        """Create version snapshot.

        Args:
            file_name: Name of file
            content: File content
            metadata: Optional metadata

        Returns:
            Snapshot ID
        """
        ...

    async def get_version_history(self, file_name: str) -> list[dict[str, object]]:
        """Get version history for file.

        Args:
            file_name: Name of file

        Returns:
            List of version entries
        """
        ...

    async def rollback_to_version(self, snapshot_id: str) -> dict[str, object]:
        """Rollback file to specific version.

        Args:
            snapshot_id: Snapshot to rollback to

        Returns:
            Restored file info
        """
        ...


__all__ = [
    "VersionManagerProtocol",
]
