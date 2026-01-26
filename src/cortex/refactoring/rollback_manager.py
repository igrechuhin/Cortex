# ruff: noqa: I001
"""
Rollback Manager - Phase 5.3

Handle rollback of refactoring executions with conflict detection.
"""

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.exceptions import FileOperationError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict, VersionMetadata
from cortex.core.version_manager import VersionManager

from .models import (
    RefactoringStatus,
    RollbackFileData,
    RollbackHistoryResult,
    RollbackManagerConfig,
    RollbackRecordModel,
    RollbackRefactoringResult,
)
from .rollback_analysis import FileRollbackAnalysis


# RollbackRecord is now replaced by RollbackRecordModel from models.py
# This alias is kept for backward compatibility during migration
RollbackRecord = RollbackRecordModel


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
        config: RollbackManagerConfig | None = None,
    ):
        self.memory_bank_dir: Path = Path(memory_bank_dir)
        self.fs_manager: FileSystemManager = fs_manager
        self.version_manager: VersionManager = version_manager
        self.metadata_index: MetadataIndex = metadata_index
        if config is None:
            self.config = RollbackManagerConfig()
        else:
            self.config = config

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
            rollback_file_data = self._read_rollback_file()
            self.rollbacks = self._parse_rollbacks_dict(rollback_file_data)
        except Exception as e:
            self._handle_corrupted_history(e)

    def _read_rollback_file(self) -> RollbackFileData:
        """Read and parse rollback file.

        Returns:
            RollbackFileData model with rollback records
        """
        if not self.rollback_file.exists():
            return RollbackFileData(last_updated="", rollbacks={})

        with open(self.rollback_file) as f:
            raw = json.load(f)
            if not isinstance(raw, dict):
                return RollbackFileData(last_updated="", rollbacks={})

            data = cast(ModelDict, raw)
            try:
                if "rollbacks" in data and "last_updated" not in data:
                    legacy: ModelDict = dict(data)
                    legacy["last_updated"] = ""
                    return RollbackFileData.model_validate(legacy)

                return RollbackFileData.model_validate(data)
            except Exception:
                # If validation fails, return empty data
                return RollbackFileData(last_updated="", rollbacks={})

    def _parse_rollbacks_dict(
        self, rollback_file_data: RollbackFileData
    ) -> dict[str, RollbackRecordModel]:
        """Extract rollbacks dictionary from RollbackFileData.

        Args:
            rollback_file_data: RollbackFileData model

        Returns:
            Dictionary mapping rollback IDs to RollbackRecordModel objects
        """
        return rollback_file_data.rollbacks

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
            data = RollbackFileData(
                last_updated=datetime.now().isoformat(),
                rollbacks=self.rollbacks,
            )
            async with open_async_text_file(self.rollback_file, "w", "utf-8") as f:
                _ = await f.write(data.model_dump_json(indent=2))
        except Exception as e:
            raise FileOperationError(f"Failed to save rollback history: {e}") from e

    async def rollback_refactoring(
        self,
        execution_id: str,
        restore_snapshot: bool = True,
        preserve_manual_changes: bool = True,
        dry_run: bool = False,
    ) -> RollbackRefactoringResult:
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
    ) -> RollbackRefactoringResult:
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
            rollback_record.status = RefactoringStatus.FAILED
            rollback_record.error = f"No snapshot found for execution {execution_id}"
            self.rollbacks[rollback_id] = rollback_record
            await self.save_rollbacks()
            return None

        if snapshot_id is None:
            return None

        return snapshot_id

    def _build_failed_response(
        self, rollback_id: str, rollback_record: RollbackRecord
    ) -> RollbackRefactoringResult:
        """Build failed rollback response.

        Args:
            rollback_id: Rollback ID
            rollback_record: Rollback record

        Returns:
            RollbackRefactoringResult with failure status
        """
        return RollbackRefactoringResult(
            status="failed",
            rollback_id=rollback_id,
            execution_id=rollback_record.execution_id,
            error=rollback_record.error or "No snapshot ID found for execution",
        )

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
    ) -> RollbackRefactoringResult:
        """Finalize rollback and return success response.

        Args:
            rollback_id: Rollback ID
            execution_id: Execution ID
            rollback_record: Rollback record
            conflicts: List of conflicts
            dry_run: Whether it was a dry run

        Returns:
            RollbackRefactoringResult with success status
        """
        rollback_record.status = RefactoringStatus.COMPLETED
        rollback_record.completed_at = datetime.now().isoformat()

        self.rollbacks[rollback_id] = rollback_record
        await self.save_rollbacks()

        return RollbackRefactoringResult(
            status="success",
            rollback_id=rollback_id,
            execution_id=execution_id,
            files_restored=(len(rollback_record.files_restored)),
            conflicts_detected=len(conflicts),
            conflicts=conflicts,
            dry_run=dry_run,
        )

    async def _handle_rollback_error(
        self, rollback_id: str, rollback_record: RollbackRecord, error: Exception
    ) -> RollbackRefactoringResult:
        """Handle rollback error.

        Args:
            rollback_id: Rollback ID
            rollback_record: Rollback record
            error: Exception that occurred

        Returns:
            Error response dictionary
        """
        rollback_record.status = RefactoringStatus.FAILED
        rollback_record.error = str(error)
        rollback_record.completed_at = datetime.now().isoformat()

        self.rollbacks[rollback_id] = rollback_record
        await self.save_rollbacks()

        return RollbackRefactoringResult(
            status="failed",
            rollback_id=rollback_id,
            execution_id=rollback_record.execution_id,
            error=str(error),
        )

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

        version_history = _extract_version_history(cast(JsonValue, file_meta))
        if version_history is None:
            return False

        for version_entry in version_history:
            change_description = version_entry.change_description or ""
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
                stored_hash = _extract_content_hash(cast(JsonValue, metadata))
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
    ) -> list[VersionMetadata] | None:
        """
        Get version history for a file.

        Args:
            file_path: Path to file

        Returns:
            Version history list (Pydantic models) or None if not found
        """
        file_meta = await self.metadata_index.get_file_metadata(file_path)
        return _extract_version_history(cast(JsonValue, file_meta))

    def _find_snapshot_version(
        self, version_history: list[VersionMetadata], snapshot_id: str
    ) -> int | None:
        """
        Find version number for a snapshot.

        Args:
            version_history: Version history list (Pydantic models)
            snapshot_id: Snapshot to find

        Returns:
            Version number or None if not found
        """
        for version_entry in version_history:
            change_description = version_entry.change_description or ""
            if not change_description.startswith(
                f"Pre-refactoring snapshot: {snapshot_id}"
            ):
                continue

            return version_entry.version

        return None

    async def _rollback_file_to_version(
        self,
        file_path: str,
        version_history: list[VersionMetadata],
        version: int,
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
        return result is not None

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
            version_history = _extract_version_history(cast(JsonValue, file_meta))
            if version_history is not None:
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
    ) -> RollbackHistoryResult:
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

    async def get_rollback(self, rollback_id: str) -> RollbackRecordModel | None:
        """Get a specific rollback by ID.

        Returns:
            RollbackRecordModel or None if not found
        """
        return self.rollbacks.get(rollback_id)

    async def analyze_rollback_impact(
        self,
        execution_id: str,
    ) -> ModelDict:
        """
        Analyze the impact of rolling back an execution.

        Args:
            execution_id: ID of the execution to analyze

        Returns:
            RollbackImpactResult with impact analysis
        """
        snapshot_id = self.find_snapshot_for_execution(execution_id)
        if not snapshot_id:
            return {
                "status": "error",
                "execution_id": execution_id,
                "total_files": 0,
                "conflicts": 0,
                "conflicts_count": 0,
                "can_rollback_all": False,
                "affected_files": [],
                "conflicts_list": [],
                "message": f"No snapshot found for execution {execution_id}",
                "error": f"No snapshot found for execution {execution_id}",
            }

        affected_files_list = await self.get_affected_files(execution_id, snapshot_id)
        conflicts_list = await self.detect_conflicts(affected_files_list, snapshot_id)
        affected_files = [cast(ModelDict, {"file": f}) for f in affected_files_list]
        conflicts = [cast(ModelDict, {"file": f}) for f in conflicts_list]
        return self._build_rollback_impact_result(
            execution_id, affected_files, conflicts
        )

    def _build_rollback_impact_result(
        self,
        execution_id: str,
        affected_files: list[ModelDict],
        conflicts: list[ModelDict],
    ) -> ModelDict:
        """Build rollback impact result dictionary."""
        affected_files_json = cast(list[JsonValue], affected_files)
        conflicts_json = cast(list[JsonValue], conflicts)
        return {
            "status": "success",
            "execution_id": execution_id,
            "total_files": len(affected_files),
            "conflicts": len(conflicts),
            "conflicts_count": len(conflicts),
            "can_rollback_all": len(conflicts) == 0,
            "affected_files": affected_files_json,
            "conflicts_list": conflicts_json,
            "message": None,
            "error": None,
        }


def _extract_version_history(file_meta: JsonValue) -> list[VersionMetadata] | None:
    if file_meta is None:
        return None

    if isinstance(file_meta, dict):
        file_meta_dict = cast(ModelDict, file_meta)
        history_raw = file_meta_dict.get("version_history")
        if not isinstance(history_raw, list):
            return None
        history_list: list[VersionMetadata] = []
        for item in cast(list[JsonValue], history_raw):
            if isinstance(item, dict):
                history_list.append(VersionMetadata.model_validate(item))
        return history_list

    version_history_attr = getattr(file_meta, "version_history", None)
    if not isinstance(version_history_attr, list):
        return None

    history_list: list[VersionMetadata] = []
    for item in cast(list[JsonValue], version_history_attr):
        if isinstance(item, VersionMetadata):
            history_list.append(item)
        elif isinstance(item, dict):
            history_list.append(VersionMetadata.model_validate(item))
    return history_list


def _extract_content_hash(file_meta: JsonValue) -> str | None:
    if file_meta is None:
        return None
    if isinstance(file_meta, dict):
        return _extract_hash_from_dict(cast(ModelDict, file_meta))
    return _extract_hash_from_object(file_meta)


def _extract_hash_from_dict(file_meta_dict: ModelDict) -> str | None:
    """Extract content hash from dictionary."""
    content_hash = file_meta_dict.get("content_hash")
    return str(content_hash) if isinstance(content_hash, str) else None


def _extract_hash_from_object(file_meta: JsonValue) -> str | None:
    """Extract content hash from object."""
    content_hash_attr = getattr(file_meta, "content_hash", None)
    return str(content_hash_attr) if isinstance(content_hash_attr, str) else None

    async def _analyze_files_for_rollback(
        self, affected_files: list[str], conflicts: list[str]
    ) -> list[FileRollbackAnalysis]:
        """Analyze each file for rollback impact."""
        return [
            self._analyze_single_file_rollback(file_path, conflicts)
            for file_path in affected_files
        ]

    def _analyze_single_file_rollback(
        self, file_path: str, conflicts: list[str]
    ) -> FileRollbackAnalysis:
        """Analyze a single file for rollback."""
        full_path = self.memory_bank_dir / file_path
        has_conflict = any(file_path in conflict for conflict in conflicts)

        can_restore = not has_conflict
        reason = "File has been manually edited" if has_conflict else None

        return FileRollbackAnalysis(
            file=file_path,
            exists=full_path.exists(),
            has_conflict=has_conflict,
            can_restore=can_restore,
            reason=reason,
        )


def _filter_rollbacks_by_date(
    rollbacks: Iterable[RollbackRecordModel], cutoff_date: datetime
) -> list[RollbackRecordModel]:
    """Filter rollbacks by date cutoff."""
    filtered: list[RollbackRecordModel] = []
    for rollback in rollbacks:
        rollback_date = datetime.fromisoformat(rollback.created_at)
        if rollback_date >= cutoff_date:
            filtered.append(rollback)
    return filtered


def _calculate_rollback_statistics(
    filtered_rollbacks: list[RollbackRecordModel],
) -> dict[str, int | float]:
    """Calculate rollback statistics."""
    total = len(filtered_rollbacks)
    successful = len(
        [r for r in filtered_rollbacks if r.status == RefactoringStatus.COMPLETED]
    )
    failed = len(
        [r for r in filtered_rollbacks if r.status == RefactoringStatus.FAILED]
    )
    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "success_rate": successful / total if total > 0 else 0,
    }


def _build_rollback_history_result(
    time_range_days: int,
    filtered_rollbacks: list[RollbackRecordModel],
    stats: dict[str, int | float],
) -> RollbackHistoryResult:
    """Build rollback history result model."""

    # Sort by created_at descending (newest first)
    sorted_rollbacks = sorted(
        filtered_rollbacks,
        key=lambda r: r.created_at,
        reverse=True,
    )

    return RollbackHistoryResult(
        time_range_days=time_range_days,
        total_rollbacks=int(stats["total"]),
        successful=int(stats["successful"]),
        failed=int(stats["failed"]),
        rollbacks=sorted_rollbacks,
    )
