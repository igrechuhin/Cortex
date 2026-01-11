"""
Rollback Manager - Phase 5.3

Handle rollback of refactoring executions with conflict detection.
"""

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.exceptions import FileOperationError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.version_manager import VersionManager


@dataclass
class RollbackRecord:
    """Record of a rollback operation."""

    rollback_id: str
    execution_id: str
    created_at: str
    completed_at: str | None = None
    status: str = "pending"  # "pending", "completed", "failed"
    files_restored: list[str] | None = None
    conflicts_detected: list[str] | None = None
    preserve_manual_edits: bool = True
    error: str | None = None

    def __post_init__(self):
        if self.files_restored is None:
            self.files_restored = []
        if self.conflicts_detected is None:
            self.conflicts_detected = []

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
        return asdict(self)


class RollbackManager:
    """
    Manage rollback of refactoring executions.

    Features:
    - Restore files from version snapshots
    - Detect conflicts with manual edits
    - Partial rollback support
    - Preserve manual changes where possible
    - Rollback history tracking
    """

    def __init__(
        self,
        memory_bank_dir: Path,
        fs_manager: FileSystemManager,
        version_manager: VersionManager,
        metadata_index: MetadataIndex,
        config: dict[str, object] | None = None,
    ):
        self.memory_bank_dir: Path = Path(memory_bank_dir)
        self.fs_manager: FileSystemManager = fs_manager
        self.version_manager: VersionManager = version_manager
        self.metadata_index: MetadataIndex = metadata_index
        self.config: dict[str, object] = config or {}

        # Rollback history file
        self.rollback_file: Path = self.memory_bank_dir.parent / "rollbacks.json"
        self.rollbacks: dict[str, RollbackRecord] = {}

        # Load existing rollback history
        self._load_rollbacks()

    def _load_rollbacks(self) -> None:
        """
        Load rollback history from disk.

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        if not self.rollback_file.exists():
            return

        try:
            rollbacks_dict = self._read_rollback_file()
            self.rollbacks = self._parse_rollbacks_dict(rollbacks_dict)
        except Exception as e:
            self._handle_corrupted_history(e)

    def _read_rollback_file(self) -> dict[str, object]:
        """Read and extract rollbacks dictionary from file.

        Returns:
            Dictionary of rollback data
        """
        with open(self.rollback_file) as f:
            data: dict[str, object] = cast(dict[str, object], json.load(f))
            return cast(dict[str, object], data.get("rollbacks", {}))

    def _parse_rollbacks_dict(
        self, rollbacks_dict: dict[str, object]
    ) -> dict[str, RollbackRecord]:
        """Parse rollbacks dictionary into RollbackRecord objects.

        Args:
            rollbacks_dict: Dictionary of rollback data

        Returns:
            Dictionary mapping rollback IDs to RollbackRecord objects
        """
        rollbacks: dict[str, RollbackRecord] = {}
        for rollback_id, rollback_data in rollbacks_dict.items():
            rollback_data_dict: dict[str, object] = cast(
                dict[str, object], rollback_data
            )
            rollbacks[str(rollback_id)] = self._create_rollback_from_dict(
                rollback_data_dict
            )
        return rollbacks

    def _create_rollback_from_dict(
        self, rollback_data: dict[str, object]
    ) -> RollbackRecord:
        """Create RollbackRecord from dictionary data.

        Args:
            rollback_data: Dictionary containing rollback field data

        Returns:
            RollbackRecord instance
        """
        return RollbackRecord(
            rollback_id=cast(str, rollback_data.get("rollback_id", "")),
            execution_id=cast(str, rollback_data.get("execution_id", "")),
            created_at=cast(str, rollback_data.get("created_at", "")),
            completed_at=cast(str | None, rollback_data.get("completed_at")),
            status=cast(str, rollback_data.get("status", "pending")),
            files_restored=cast(list[str] | None, rollback_data.get("files_restored")),
            conflicts_detected=cast(
                list[str] | None, rollback_data.get("conflicts_detected")
            ),
            preserve_manual_edits=cast(
                bool, rollback_data.get("preserve_manual_edits", True)
            ),
            error=cast(str | None, rollback_data.get("error")),
        )

    def _handle_corrupted_history(self, error: Exception) -> None:
        """Handle corrupted rollback history by starting fresh.

        Args:
            error: The exception that occurred during loading
        """
        from cortex.core.logging_config import logger

        logger.warning(f"Rollback history corrupted, starting fresh: {error}")
        self.rollbacks = {}

    async def save_rollbacks(self):
        """Save rollback history to disk."""
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "rollbacks": {
                    rollback_id: rollback.to_dict()
                    for rollback_id, rollback in self.rollbacks.items()
                },
            }
            async with open_async_text_file(self.rollback_file, "w", "utf-8") as f:
                _ = await f.write(json.dumps(data, indent=2))
        except Exception as e:
            raise FileOperationError(f"Failed to save rollback history: {e}") from e

    async def rollback_refactoring(
        self,
        execution_id: str,
        restore_snapshot: bool = True,
        preserve_manual_changes: bool = True,
        dry_run: bool = False,
    ) -> dict[str, object]:
        """
        Rollback a refactoring execution.

        Args:
            execution_id: ID of the execution to rollback
            restore_snapshot: If True, restore from snapshot
            preserve_manual_changes: If True, try to preserve manual edits
            dry_run: If True, simulate without making changes

        Returns:
            Rollback results
        """
        rollback_id, rollback_record = self._initialize_rollback(
            execution_id, preserve_manual_changes
        )

        try:
            snapshot_id = await self._validate_and_get_snapshot(
                execution_id, restore_snapshot, rollback_id, rollback_record
            )
            if snapshot_id is None:
                return self._build_failed_response(rollback_id, rollback_record)

            return await self._execute_rollback_workflow(
                execution_id,
                snapshot_id,
                preserve_manual_changes,
                dry_run,
                rollback_id,
                rollback_record,
            )

        except Exception as e:
            return await self._handle_rollback_error(rollback_id, rollback_record, e)

    async def _execute_rollback_workflow(
        self,
        execution_id: str,
        snapshot_id: str,
        preserve_manual_changes: bool,
        dry_run: bool,
        rollback_id: str,
        rollback_record: RollbackRecord,
    ) -> dict[str, object]:
        """Execute the rollback workflow.

        Args:
            execution_id: ID of the execution to rollback
            snapshot_id: ID of the snapshot to restore
            preserve_manual_changes: If True, try to preserve manual edits
            dry_run: If True, simulate without making changes
            rollback_id: Rollback ID
            rollback_record: Rollback record object

        Returns:
            Rollback results
        """
        affected_files = await self.get_affected_files(execution_id, snapshot_id)
        conflicts = await self._detect_rollback_conflicts(
            preserve_manual_changes, affected_files, snapshot_id, rollback_record
        )

        restored_files: list[str] = await self._execute_rollback(
            dry_run, affected_files, snapshot_id, preserve_manual_changes, conflicts
        )
        rollback_record.files_restored = restored_files

        return await self._finalize_rollback(
            rollback_id, execution_id, rollback_record, conflicts, dry_run
        )

    def _initialize_rollback(
        self, execution_id: str, preserve_manual_changes: bool
    ) -> tuple[str, RollbackRecord]:
        """Initialize rollback by creating ID and record.

        Args:
            execution_id: Execution ID
            preserve_manual_changes: Whether to preserve manual changes

        Returns:
            Tuple of (rollback_id, rollback_record)
        """
        rollback_id = self._generate_rollback_id(execution_id)
        rollback_record = self._create_rollback_record(
            rollback_id, execution_id, preserve_manual_changes
        )
        return rollback_id, rollback_record

    def _generate_rollback_id(self, execution_id: str) -> str:
        """Generate unique rollback ID.

        Args:
            execution_id: Execution ID

        Returns:
            Rollback ID
        """
        return f"rollback-{execution_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _create_rollback_record(
        self, rollback_id: str, execution_id: str, preserve_manual_changes: bool
    ) -> RollbackRecord:
        """Create rollback record.

        Args:
            rollback_id: Rollback ID
            execution_id: Execution ID
            preserve_manual_changes: Whether to preserve manual changes

        Returns:
            Rollback record
        """
        return RollbackRecord(
            rollback_id=rollback_id,
            execution_id=execution_id,
            created_at=datetime.now().isoformat(),
            preserve_manual_edits=preserve_manual_changes,
        )

    async def _validate_and_get_snapshot(
        self,
        execution_id: str,
        restore_snapshot: bool,
        rollback_id: str,
        rollback_record: RollbackRecord,
    ) -> str | None:
        """Validate and get snapshot ID for execution.

        Args:
            execution_id: Execution ID
            restore_snapshot: Whether to restore from snapshot
            rollback_id: Rollback ID
            rollback_record: Rollback record to update

        Returns:
            Snapshot ID or None if validation fails
        """
        snapshot_id = self.find_snapshot_for_execution(execution_id)

        if not snapshot_id and restore_snapshot:
            rollback_record.status = "failed"
            rollback_record.error = f"No snapshot found for execution {execution_id}"
            self.rollbacks[rollback_id] = rollback_record
            await self.save_rollbacks()
            return None

        if snapshot_id is None:
            return None

        return snapshot_id

    def _build_failed_response(
        self, rollback_id: str, rollback_record: RollbackRecord
    ) -> dict[str, object]:
        """Build failed rollback response.

        Args:
            rollback_id: Rollback ID
            rollback_record: Rollback record

        Returns:
            Failed response dictionary
        """
        return {
            "status": "failed",
            "rollback_id": rollback_id,
            "error": rollback_record.error or "No snapshot ID found for execution",
        }

    async def _detect_rollback_conflicts(
        self,
        preserve_manual_changes: bool,
        affected_files: list[str],
        snapshot_id: str,
        rollback_record: RollbackRecord,
    ) -> list[str]:
        """Detect conflicts for rollback.

        Args:
            preserve_manual_changes: Whether to preserve manual changes
            affected_files: List of affected files
            snapshot_id: Snapshot ID
            rollback_record: Rollback record to update

        Returns:
            List of conflicts
        """
        conflicts: list[str] = []
        if preserve_manual_changes:
            conflicts = await self.detect_conflicts(affected_files, snapshot_id)
            rollback_record.conflicts_detected = conflicts
        return conflicts

    async def _execute_rollback(
        self,
        dry_run: bool,
        affected_files: list[str],
        snapshot_id: str,
        preserve_manual_changes: bool,
        conflicts: list[str],
    ) -> list[str]:
        """Execute rollback operation.

        Args:
            dry_run: Whether to simulate
            affected_files: List of affected files
            snapshot_id: Snapshot ID
            preserve_manual_changes: Whether to preserve manual changes
            conflicts: List of conflicts

        Returns:
            List of restored files
        """
        if not dry_run:
            return await self.restore_files(
                affected_files, snapshot_id, preserve_manual_changes, conflicts
            )
        return affected_files

    async def _finalize_rollback(
        self,
        rollback_id: str,
        execution_id: str,
        rollback_record: RollbackRecord,
        conflicts: list[str],
        dry_run: bool,
    ) -> dict[str, object]:
        """Finalize rollback and return success response.

        Args:
            rollback_id: Rollback ID
            execution_id: Execution ID
            rollback_record: Rollback record
            conflicts: List of conflicts
            dry_run: Whether it was a dry run

        Returns:
            Success response dictionary
        """
        rollback_record.status = "completed"
        rollback_record.completed_at = datetime.now().isoformat()

        self.rollbacks[rollback_id] = rollback_record
        await self.save_rollbacks()

        return {
            "status": "success",
            "rollback_id": rollback_id,
            "execution_id": execution_id,
            "files_restored": (
                len(rollback_record.files_restored)
                if rollback_record.files_restored is not None
                else 0
            ),
            "conflicts_detected": len(conflicts),
            "conflicts": conflicts,
            "dry_run": dry_run,
        }

    async def _handle_rollback_error(
        self, rollback_id: str, rollback_record: RollbackRecord, error: Exception
    ) -> dict[str, object]:
        """Handle rollback error.

        Args:
            rollback_id: Rollback ID
            rollback_record: Rollback record
            error: Exception that occurred

        Returns:
            Error response dictionary
        """
        rollback_record.status = "failed"
        rollback_record.error = str(error)
        rollback_record.completed_at = datetime.now().isoformat()

        self.rollbacks[rollback_id] = rollback_record
        await self.save_rollbacks()

        return {
            "status": "failed",
            "rollback_id": rollback_id,
            "error": str(error),
        }

    def find_snapshot_for_execution(self, execution_id: str) -> str | None:
        """Find snapshot ID for an execution."""
        # This would typically come from the execution record
        # For now, we'll construct it from the execution_id
        # In practice, the RefactoringExecutor would store this
        if "exec-" in execution_id:
            # Extract timestamp from execution_id
            # Format: exec-{suggestion_id}-{timestamp}
            parts = execution_id.split("-")
            if len(parts) >= 3:
                timestamp = parts[-1]
                return f"refactoring-{timestamp}"
        return None

    async def get_affected_files(
        self,
        execution_id: str,  # noqa: ARG002
        snapshot_id: str,
    ) -> list[str]:
        """Get list of files affected by an execution."""
        if not snapshot_id:
            return []

        affected_files: list[str] = []
        for file_path in self.memory_bank_dir.glob("**/*.md"):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.memory_bank_dir)
                if await self._file_has_snapshot(str(rel_path), snapshot_id):
                    affected_files.append(str(rel_path))

        return affected_files

    async def _file_has_snapshot(self, rel_path: str, snapshot_id: str) -> bool:
        """Check if file has snapshot with matching ID."""
        file_meta = await self.metadata_index.get_file_metadata(rel_path)

        if not isinstance(file_meta, dict):
            return False

        versions_raw = file_meta.get("version_history", [])
        if not isinstance(versions_raw, list):
            return False

        versions_list: list[dict[str, object]] = cast(
            list[dict[str, object]], versions_raw
        )
        for version in versions_list:
            change_description_raw = version.get("change_description", "")
            change_description = (
                str(change_description_raw)
                if change_description_raw is not None
                else ""
            )
            if change_description.startswith(
                f"Pre-refactoring snapshot: {snapshot_id}"
            ):
                return True

        return False

    async def detect_conflicts(
        self,
        affected_files: list[str],
        snapshot_id: str,
    ) -> list[str]:
        """
        Detect conflicts between current state and snapshot.

        A conflict occurs when:
        - File has been manually edited since snapshot
        - File structure has changed
        """
        conflicts: list[str] = []

        for file_path in affected_files:
            full_path = self.memory_bank_dir / file_path

            if not full_path.exists():
                conflicts.append(f"{file_path} - File was deleted after refactoring")
                continue

            # Get current content hash
            content, _ = await self.fs_manager.read_file(full_path)
            current_hash = self.fs_manager.compute_hash(content)

            # Get metadata to check for external modifications
            metadata = await self.metadata_index.get_file_metadata(file_path)
            if metadata:
                stored_hash = metadata.get("content_hash")
                if stored_hash and stored_hash != current_hash:
                    conflicts.append(f"{file_path} - File has been manually edited")

        return conflicts

    async def restore_files(
        self,
        affected_files: list[str],
        snapshot_id: str,
        preserve_manual_changes: bool,
        conflicts: list[str],
    ) -> list[str]:
        """
        Restore files from snapshot.

        Args:
            affected_files: List of files to restore
            snapshot_id: Snapshot to restore from
            preserve_manual_changes: Whether to preserve manual edits
            conflicts: List of detected conflicts

        Returns:
            List of successfully restored files
        """
        restored_files: list[str] = []

        for file_path in affected_files:
            # Skip files with conflicts if preserving manual changes
            if await self._should_skip_conflicted_file(
                file_path, preserve_manual_changes, conflicts
            ):
                continue

            # Restore from snapshot
            restored = await self._restore_single_file(file_path, snapshot_id)
            if restored:
                restored_files.append(file_path)

        return restored_files

    async def _should_skip_conflicted_file(
        self, file_path: str, preserve_manual_changes: bool, conflicts: list[str]
    ) -> bool:
        """
        Check if file should be skipped due to conflicts.

        Args:
            file_path: Path to file
            preserve_manual_changes: Whether to preserve manual edits
            conflicts: List of detected conflicts

        Returns:
            True if file should be skipped
        """
        if not preserve_manual_changes:
            return False

        has_conflict = any(file_path in conflict for conflict in conflicts)
        if has_conflict:
            # Create a backup of the current version
            await self.backup_current_version(file_path)
            return True

        return False

    async def _restore_single_file(self, file_path: str, snapshot_id: str) -> bool:
        """
        Restore a single file from snapshot.

        Args:
            file_path: Path to file
            snapshot_id: Snapshot to restore from

        Returns:
            True if file was successfully restored
        """
        try:
            # Get version history from metadata
            version_history = await self._get_version_history(file_path)
            if version_history is None:
                return False

            # Find snapshot version
            snapshot_version = self._find_snapshot_version(version_history, snapshot_id)
            if snapshot_version is None:
                return False

            # Rollback to this version
            return await self._rollback_file_to_version(
                file_path, version_history, snapshot_version
            )

        except Exception as e:
            # Log error but continue with other files
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to restore file {file_path} during rollback: {e}")
            return False

    async def _get_version_history(
        self, file_path: str
    ) -> list[dict[str, object]] | None:
        """
        Get version history for a file.

        Args:
            file_path: Path to file

        Returns:
            Version history list or None if not found
        """
        file_meta = await self.metadata_index.get_file_metadata(file_path)
        if not isinstance(file_meta, dict):
            return None

        version_history_raw = file_meta.get("version_history", [])
        if not isinstance(version_history_raw, list):
            return None

        return cast(list[dict[str, object]], version_history_raw)

    def _find_snapshot_version(
        self, version_history: list[dict[str, object]], snapshot_id: str
    ) -> int | None:
        """
        Find version number for a snapshot.

        Args:
            version_history: Version history list
            snapshot_id: Snapshot to find

        Returns:
            Version number or None if not found
        """
        for version in version_history:
            change_description_raw = version.get("change_description", "")
            change_description = (
                str(change_description_raw)
                if change_description_raw is not None
                else ""
            )

            if change_description.startswith(
                f"Pre-refactoring snapshot: {snapshot_id}"
            ):
                version_num_raw = version.get("version")
                version_num: int | float | None = (
                    version_num_raw
                    if isinstance(version_num_raw, (int, float))
                    else None
                )
                if version_num is not None:
                    return int(version_num)

        return None

    async def _rollback_file_to_version(
        self, file_path: str, version_history: list[dict[str, object]], version: int
    ) -> bool:
        """
        Execute rollback to a specific version.

        Args:
            file_path: Path to file
            version_history: Version history list
            version: Version number to rollback to

        Returns:
            True if rollback was successful
        """
        result = await self.version_manager.rollback_to_version(
            file_path, version_history, version
        )
        return bool(result and result.get("status") == "success")

    async def backup_current_version(self, file_path: str):
        """Backup current version before rollback."""
        full_path = self.memory_bank_dir / file_path
        if not full_path.exists():
            return

        try:
            content, _ = await self.fs_manager.read_file(full_path)
            content_hash = self.fs_manager.compute_hash(content)
            size_bytes = len(content.encode("utf-8"))

            # Get current version count
            file_meta = await self.metadata_index.get_file_metadata(file_path)
            version_count = 0
            if file_meta:
                version_history_raw = file_meta.get("version_history", [])
                if isinstance(version_history_raw, list):
                    version_history: list[object] = cast(
                        list[object], version_history_raw
                    )
                    version_count = len(version_history)

            _ = await self.version_manager.create_snapshot(
                full_path,
                version=version_count + 1,
                content=content,
                size_bytes=size_bytes,
                token_count=0,  # Will be calculated if needed
                content_hash=content_hash,
                change_type="manual_backup",
                change_description=f"Pre-rollback backup: {datetime.now().isoformat()}",
            )
        except Exception as e:
            # Ignore backup errors - don't block rollback
            from cortex.core.logging_config import logger

            logger.debug(f"Failed to create pre-rollback backup for {file_path}: {e}")

    async def get_rollback_history(
        self,
        time_range_days: int = 90,
    ) -> dict[str, object]:
        """
        Get rollback history.

        Args:
            time_range_days: Number of days to include

        Returns:
            Rollback history with statistics
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=time_range_days)
        filtered_rollbacks = _filter_rollbacks_by_date(
            self.rollbacks.values(), cutoff_date
        )
        stats = _calculate_rollback_statistics(filtered_rollbacks)
        return _build_rollback_history_result(
            time_range_days, filtered_rollbacks, stats
        )

    async def get_rollback(self, rollback_id: str) -> dict[str, object] | None:
        """Get a specific rollback by ID."""
        rollback = self.rollbacks.get(rollback_id)
        if rollback:
            return rollback.to_dict()
        return None

    async def analyze_rollback_impact(
        self,
        execution_id: str,
    ) -> dict[str, object]:
        """
        Analyze the impact of rolling back an execution.

        Args:
            execution_id: ID of the execution to analyze

        Returns:
            Impact analysis
        """
        snapshot_id = self.find_snapshot_for_execution(execution_id)
        if not snapshot_id:
            return {
                "status": "error",
                "message": f"No snapshot found for execution {execution_id}",
            }

        affected_files = await self.get_affected_files(execution_id, snapshot_id)
        conflicts = await self.detect_conflicts(affected_files, snapshot_id)
        file_analysis = await self._analyze_files_for_rollback(
            affected_files, conflicts
        )

        return {
            "status": "success",
            "execution_id": execution_id,
            "snapshot_id": snapshot_id,
            "total_files": len(affected_files),
            "conflicts": len(conflicts),
            "can_rollback_all": len(conflicts) == 0,
            "files": file_analysis,
            "conflicts_detail": conflicts,
        }

    async def _analyze_files_for_rollback(
        self, affected_files: list[str], conflicts: list[str]
    ) -> list[dict[str, object]]:
        """Analyze each file for rollback impact."""
        file_analysis: list[dict[str, object]] = []
        for file_path in affected_files:
            analysis = self._analyze_single_file_rollback(file_path, conflicts)
            file_analysis.append(analysis)
        return file_analysis

    def _analyze_single_file_rollback(
        self, file_path: str, conflicts: list[str]
    ) -> dict[str, object]:
        """Analyze a single file for rollback."""
        full_path = self.memory_bank_dir / file_path
        has_conflict = any(file_path in conflict for conflict in conflicts)

        analysis: dict[str, object] = {
            "file": file_path,
            "exists": full_path.exists(),
            "has_conflict": has_conflict,
            "can_restore": True,
        }

        if has_conflict:
            analysis["can_restore"] = False
            analysis["reason"] = "File has been manually edited"

        return analysis


def _filter_rollbacks_by_date(
    rollbacks: Iterable[RollbackRecord], cutoff_date: datetime
) -> list[dict[str, object]]:
    """Filter rollbacks by date cutoff."""
    filtered: list[dict[str, object]] = []
    for rollback in rollbacks:
        rollback_date = datetime.fromisoformat(rollback.created_at)
        if rollback_date >= cutoff_date:
            filtered.append(rollback.to_dict())
    return filtered


def _calculate_rollback_statistics(
    filtered_rollbacks: list[dict[str, object]],
) -> dict[str, int | float]:
    """Calculate rollback statistics."""
    total = len(filtered_rollbacks)
    successful = len(
        [r for r in filtered_rollbacks if cast(str, r.get("status", "")) == "completed"]
    )
    failed = len(
        [r for r in filtered_rollbacks if cast(str, r.get("status", "")) == "failed"]
    )
    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "success_rate": successful / total if total > 0 else 0,
    }


def _build_rollback_history_result(
    time_range_days: int,
    filtered_rollbacks: list[dict[str, object]],
    stats: dict[str, int | float],
) -> dict[str, object]:
    """Build rollback history result dictionary."""

    def get_created_at(r: dict[str, object]) -> str:
        """Extract created_at from rollback dict."""
        created_at_raw = r.get("created_at", "")
        return str(created_at_raw) if created_at_raw is not None else ""

    return {
        "time_range_days": time_range_days,
        "total_rollbacks": stats["total"],
        "successful": stats["successful"],
        "failed": stats["failed"],
        "success_rate": stats["success_rate"],
        "rollbacks": sorted(
            filtered_rollbacks,
            key=get_created_at,
            reverse=True,
        ),
    }
