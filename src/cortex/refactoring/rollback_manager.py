# ruff: noqa: I001
"""
Rollback Manager - Phase 5.3

Handle rollback of refactoring executions with conflict detection.
Delegates to version_snapshots, rollback_execution, rollback_conflicts,
rollback_history_operations, rollback_initialization, rollback_history_loader.
"""

from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.exceptions import FileOperationError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.version_manager import VersionManager

from .models import (
    RefactoringStatus,
    RollbackRefactoringStatus,
    RollbackHistoryResult,
    RollbackManagerConfig,
    RollbackRecordModel,
    RollbackRefactoringResult,
)
from .rollback_analysis import FileRollbackAnalysis
from .rollback_conflicts import detect_rollback_conflicts
from .rollback_execution import backup_current_version, execute_rollback
from .rollback_history_loader import (
    load_rollbacks,
    save_rollbacks as save_rollbacks_disk,
)
from .rollback_history_operations import (
    build_rollback_history_result,
    calculate_rollback_statistics,
    filter_rollbacks_by_date,
)
from .rollback_initialization import initialize_rollback
from .version_snapshots import (
    find_snapshot_for_execution_sync,
    get_affected_files as get_affected_files_impl,
)

# RollbackRecord is now replaced by RollbackRecordModel from models.py
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
        self.config: RollbackManagerConfig = (
            config if config is not None else RollbackManagerConfig()
        )
        self.rollback_file: Path = self.memory_bank_dir.parent / "rollbacks.json"
        self.rollbacks: dict[str, RollbackRecord] = {}
        self._load_rollbacks()

    def _load_rollbacks(self) -> None:
        """Load rollback history from disk via rollback_history_loader."""
        self.rollbacks = load_rollbacks(self.rollback_file)

    async def save_rollbacks(self) -> None:
        """Save rollback history to disk."""
        try:
            await save_rollbacks_disk(self.rollback_file, self.rollbacks)
        except Exception as e:
            raise FileOperationError(f"Failed to save rollback history: {e}") from e

    def find_snapshot_for_execution(self, execution_id: str) -> str | None:
        """Find snapshot ID for an execution."""
        return find_snapshot_for_execution_sync(execution_id)

    async def get_affected_files(
        self,
        execution_id: str,
        snapshot_id: str,
    ) -> list[str]:
        """Get list of files affected by an execution."""
        return await get_affected_files_impl(
            self.memory_bank_dir,
            execution_id,
            snapshot_id,
            self.metadata_index,
        )

    async def rollback_refactoring(
        self,
        execution_id: str,
        restore_snapshot: bool = True,
        preserve_manual_changes: bool = True,
        dry_run: bool = False,
    ) -> RollbackRefactoringResult:
        """Rollback a refactoring execution."""
        rollback_id, rollback_record = initialize_rollback(
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

    async def _validate_and_get_snapshot(
        self,
        execution_id: str,
        restore_snapshot: bool,
        rollback_id: str,
        rollback_record: RollbackRecord,
    ) -> str | None:
        """Validate and get snapshot ID for execution."""
        snapshot_id = self.find_snapshot_for_execution(execution_id)

        if not snapshot_id and restore_snapshot:
            rollback_record.status = RefactoringStatus.FAILED
            rollback_record.error = f"No snapshot found for execution {execution_id}"
            self.rollbacks[rollback_id] = rollback_record
            await self.save_rollbacks()
            return None

        return snapshot_id

    def _build_failed_response(
        self, rollback_id: str, rollback_record: RollbackRecord
    ) -> RollbackRefactoringResult:
        """Build failed rollback response."""
        return RollbackRefactoringResult(
            status=RollbackRefactoringStatus.FAILED,
            rollback_id=rollback_id,
            execution_id=rollback_record.execution_id,
            error=rollback_record.error or "No snapshot ID found for execution",
        )

    async def _execute_rollback_workflow(
        self,
        execution_id: str,
        snapshot_id: str,
        preserve_manual_changes: bool,
        dry_run: bool,
        rollback_id: str,
        rollback_record: RollbackRecord,
    ) -> RollbackRefactoringResult:
        """Execute the rollback workflow."""
        affected_files = await self.get_affected_files(execution_id, snapshot_id)
        conflicts = await self.detect_conflicts(
            affected_files, snapshot_id, preserve_manual_changes
        )
        rollback_record.conflicts_detected = conflicts

        if dry_run:
            restored_files = affected_files
        else:
            restored_files = await self.restore_files(
                affected_files, snapshot_id, preserve_manual_changes, conflicts
            )
        rollback_record.files_restored = restored_files

        return await self._finalize_rollback(
            rollback_id, execution_id, rollback_record, conflicts, dry_run
        )

    async def _finalize_rollback(
        self,
        rollback_id: str,
        execution_id: str,
        rollback_record: RollbackRecord,
        conflicts: list[str],
        dry_run: bool,
    ) -> RollbackRefactoringResult:
        """Finalize rollback and return success response."""
        rollback_record.status = RefactoringStatus.COMPLETED
        rollback_record.completed_at = datetime.now().isoformat()
        self.rollbacks[rollback_id] = rollback_record
        await self.save_rollbacks()
        return RollbackRefactoringResult(
            status=RollbackRefactoringStatus.SUCCESS,
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
        """Handle rollback error."""
        rollback_record.status = RefactoringStatus.FAILED
        rollback_record.error = str(error)
        rollback_record.completed_at = datetime.now().isoformat()
        self.rollbacks[rollback_id] = rollback_record
        await self.save_rollbacks()
        return RollbackRefactoringResult(
            status=RollbackRefactoringStatus.FAILED,
            rollback_id=rollback_id,
            execution_id=rollback_record.execution_id,
            error=str(error),
        )

    async def detect_conflicts(
        self,
        affected_files: list[str],
        snapshot_id: str,
        preserve_manual_changes: bool = True,
    ) -> list[str]:
        """Detect conflicts between current state and snapshot."""
        return await detect_rollback_conflicts(
            preserve_manual_changes,
            affected_files,
            snapshot_id,
            self.memory_bank_dir,
            self.fs_manager,
            self.metadata_index,
        )

    async def restore_files(
        self,
        affected_files: list[str],
        snapshot_id: str,
        preserve_manual_changes: bool,
        conflicts: list[str],
    ) -> list[str]:
        """Restore files from snapshot (delegates to rollback_execution)."""
        return await execute_rollback(
            dry_run=False,
            affected_files=affected_files,
            snapshot_id=snapshot_id,
            preserve_manual_changes=preserve_manual_changes,
            conflicts=conflicts,
            memory_bank_dir=self.memory_bank_dir,
            fs_manager=self.fs_manager,
            version_manager=self.version_manager,
            metadata_index=self.metadata_index,
            backup_fn=lambda path: self.backup_current_version(path),
        )

    async def backup_current_version(self, file_path: str) -> None:
        """Backup current version before rollback."""
        await backup_current_version(
            file_path,
            self.memory_bank_dir,
            self.fs_manager,
            self.version_manager,
            self.metadata_index,
        )

    async def get_rollback_history(
        self,
        time_range_days: int = 90,
    ) -> RollbackHistoryResult:
        """Get rollback history with statistics."""
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=time_range_days)
        filtered_rollbacks = filter_rollbacks_by_date(
            self.rollbacks.values(), cutoff_date
        )
        stats = calculate_rollback_statistics(filtered_rollbacks)
        return build_rollback_history_result(time_range_days, filtered_rollbacks, stats)

    async def get_rollback(self, rollback_id: str) -> RollbackRecordModel | None:
        """Get a specific rollback by ID."""
        return self.rollbacks.get(rollback_id)

    async def analyze_rollback_impact(self, execution_id: str) -> ModelDict:
        """Analyze the impact of rolling back an execution."""
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
        from cortex.core.models import JsonValue

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
