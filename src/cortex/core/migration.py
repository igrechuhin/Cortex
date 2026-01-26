"""Automatic migration from template-only to hybrid storage format."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import cast

from .dependency_graph import DependencyGraph
from .exceptions import MigrationFailedError
from .file_system import FileSystemManager
from .metadata_index import MetadataIndex
from .models import (
    BackupInfo,
    MigrationInfo,
    MigrationResult,
    SectionMetadata,
    VerificationResult,
    VersionMetadata,
)
from .token_counter import TokenCounter
from .version_manager import VersionManager


class MigrationManager:
    """
    Handles automatic migration from template-only to hybrid storage.
    - Detects need for migration
    - Creates backups
    - Builds initial metadata
    - Supports rollback on failure
    """

    def __init__(self, project_root: Path):
        """
        Initialize migration manager.

        Args:
            project_root: Root directory of the project
        """
        self.project_root: Path = Path(project_root)
        self.cortex_dir: Path = self.project_root / ".cortex"
        self.memory_bank_dir: Path = self.cortex_dir / "memory-bank"
        self.index_path: Path = self.cortex_dir / "index.json"

    async def detect_migration_needed(self) -> bool:
        """
        Detect if project needs migration.

        Criteria:
        - Has .cortex/memory-bank/ directory with .md files
        - Does NOT have .cortex/index.json file

        Returns:
            True if migration is needed
        """
        if not self.memory_bank_dir.exists():
            return False

        if self.index_path.exists():
            return False

        # Check if directory has any .md files
        md_files = list(self.memory_bank_dir.glob("*.md"))
        return len(md_files) > 0

    async def get_migration_info(self) -> MigrationInfo:
        """
        Get information about what will be migrated.

        Returns:
            MigrationInfo with migration details
        """
        if not self.memory_bank_dir.exists():
            return MigrationInfo(
                needs_migration=False,
                reason="No .cortex/memory-bank directory found",
            )

        md_files = list(self.memory_bank_dir.glob("*.md"))
        if len(md_files) == 0:
            return MigrationInfo(
                needs_migration=False,
                reason="No markdown files found in .cortex/memory-bank directory",
            )

        if self.index_path.exists():
            return MigrationInfo(
                needs_migration=False,
                reason="Already migrated (.cortex/index.json exists)",
            )

        total_size = sum(f.stat().st_size for f in md_files)

        return MigrationInfo(
            needs_migration=True,
            files_found=len(md_files),
            file_names=[f.name for f in md_files],
            total_size_bytes=total_size,
            estimated_tokens=total_size // 4,  # Rough estimate (4 bytes per token)
            backup_location=str(
                self.project_root
                / f".cortex-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ),
        )

    async def migrate(self, auto_backup: bool = True) -> MigrationResult:
        """
        Perform automatic migration with backup and rollback capability.

        Steps:
        1. Create backup of existing memory-bank/
        2. Scan all .md files
        3. Build initial metadata index
        4. Create version history snapshots
        5. Compute dependency graph
        6. Create .cortex/index.json
        7. Verify migration success

        Args:
            auto_backup: Whether to create backup (default: True)

        Returns:
            Migration report with status and details
        """
        backup_dir = None
        try:
            backup_dir = await self._create_migration_backup(auto_backup)
            md_files = list(self.memory_bank_dir.glob("*.md"))

            await self._process_migration_files(md_files)
            await self._build_migration_dependency_graph()

            verification = await self.verify_migration(md_files)
            if not verification.success:
                raise MigrationFailedError(
                    verification.error or "Migration verification failed",
                    str(backup_dir) if backup_dir else None,
                )

            return self._build_migration_result(md_files, backup_dir, verification)
        except Exception as e:
            if backup_dir:
                await self._handle_migration_error(e, backup_dir)
            raise

    def _initialize_migration_managers(
        self,
    ) -> dict[
        str,
        FileSystemManager
        | TokenCounter
        | MetadataIndex
        | VersionManager
        | DependencyGraph,
    ]:
        """Initialize managers for migration.

        Returns:
            Dictionary of initialized managers
        """
        return {
            "fs": FileSystemManager(self.project_root),
            "token": TokenCounter(),
            "index": MetadataIndex(self.project_root),
            "version": VersionManager(self.project_root),
            "graph": DependencyGraph(),
        }

    async def _process_all_files(
        self,
        md_files: list[Path],
        managers: dict[
            str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager
        ],
    ) -> None:
        """Process all markdown files for migration.

        Args:
            md_files: List of markdown files to process
            managers: Dictionary of managers
        """
        fs_manager = cast(FileSystemManager, managers["fs"])
        token_counter = cast(TokenCounter, managers["token"])
        metadata_index = cast(MetadataIndex, managers["index"])
        version_manager = cast(VersionManager, managers["version"])

        _ = await metadata_index.load()

        for md_file in md_files:
            await self._process_single_file(
                md_file, fs_manager, token_counter, metadata_index, version_manager
            )

    async def _process_single_file(
        self,
        md_file: Path,
        fs_manager: FileSystemManager,
        token_counter: TokenCounter,
        metadata_index: MetadataIndex,
        version_manager: VersionManager,
    ) -> None:
        """Process a single markdown file for migration.

        Args:
            md_file: Path to markdown file
            fs_manager: File system manager
            token_counter: Token counter
            metadata_index: Metadata index
            version_manager: Version manager
        """
        content, content_hash = await fs_manager.read_file(md_file)
        sections = fs_manager.parse_sections(content)
        token_count = token_counter.count_tokens(content)
        size_bytes = len(content.encode("utf-8"))

        await self._update_file_metadata_for_migration(
            metadata_index, md_file, size_bytes, token_count, content_hash, sections
        )

        version_meta = await self._create_initial_snapshot(
            version_manager, md_file, content, size_bytes, token_count, content_hash
        )

        await metadata_index.add_version_to_history(
            md_file.name, version_meta.model_dump(mode="json")
        )

    async def _update_file_metadata_for_migration(
        self,
        metadata_index: MetadataIndex,
        md_file: Path,
        size_bytes: int,
        token_count: int,
        content_hash: str,
        sections: list[SectionMetadata],
    ) -> None:
        """Update file metadata for migration."""
        sections_dict = [section.model_dump(mode="json") for section in sections]
        await metadata_index.update_file_metadata(
            file_name=md_file.name,
            path=md_file,
            exists=True,
            size_bytes=size_bytes,
            token_count=token_count,
            content_hash=content_hash,
            sections=sections_dict,
            change_source="migration",
        )

    async def _create_initial_snapshot(
        self,
        version_manager: VersionManager,
        md_file: Path,
        content: str,
        size_bytes: int,
        token_count: int,
        content_hash: str,
    ) -> VersionMetadata:
        """Create initial snapshot for migrated file."""

        return await version_manager.create_snapshot(
            file_path=md_file,
            version=1,
            content=content,
            size_bytes=size_bytes,
            token_count=token_count,
            content_hash=content_hash,
            change_type="created",
            change_description="Initial version from migration",
        )

    async def _build_and_save_dependency_graph(
        self,
        managers: dict[str, DependencyGraph | MetadataIndex],
    ) -> None:
        """Build and save dependency graph.

        Args:
            managers: Dictionary of managers
        """
        dep_graph = cast(DependencyGraph, managers["graph"])
        metadata_index = cast(MetadataIndex, managers["index"])
        graph_export = dep_graph.to_dict()
        # Handle both Pydantic models and dicts (for tests with mocks)
        if hasattr(graph_export, "model_dump"):
            graph_dict = graph_export.model_dump(mode="json")
        elif isinstance(graph_export, dict):
            graph_dict = cast(dict[str, object], graph_export)
        else:
            graph_dict = {}
        await metadata_index.update_dependency_graph(graph_dict)

    async def _handle_migration_error(
        self, error: Exception, backup_dir: Path | None
    ) -> None:
        """Handle migration error with rollback.

        Args:
            error: Exception that occurred
            backup_dir: Backup directory path if available
        """
        if backup_dir and backup_dir.exists():
            try:
                await self.rollback(backup_dir)
            except Exception as rollback_error:
                from cortex.core.logging_config import logger

                logger.warning(f"Rollback failed: {rollback_error}")

        raise MigrationFailedError(
            str(error), str(backup_dir) if backup_dir else None
        ) from error

    async def create_backup(self) -> Path:
        """
        Create timestamped backup of memory-bank directory.

        Returns:
            Path to backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.project_root / f".cortex-backup-{timestamp}"

        if self.memory_bank_dir.exists():
            _ = shutil.copytree(self.memory_bank_dir, backup_dir)

        return backup_dir

    async def rollback(self, backup_dir: Path):
        """
        Restore from backup if migration fails.

        Args:
            backup_dir: Path to backup directory
        """
        # Remove failed migration artifacts
        if self.index_path.exists():
            self.index_path.unlink()

        history_dir = self.cortex_dir / "history"
        if history_dir.exists():
            shutil.rmtree(history_dir)

        # Restore from backup
        if backup_dir.exists() and self.memory_bank_dir.exists():
            shutil.rmtree(self.memory_bank_dir)
            _ = shutil.copytree(backup_dir, self.memory_bank_dir)

    async def verify_migration(self, md_files: list[Path]) -> VerificationResult:
        """
        Verify migration completed successfully.

        Args:
            md_files: List of markdown files that were migrated

        Returns:
            VerificationResult with verification status
        """
        # Check index exists
        if not self.index_path.exists():
            return VerificationResult(success=False, error="Index file not created")

        # Check history directory exists
        history_dir = self.cortex_dir / "history"
        if not history_dir.exists():
            return VerificationResult(
                success=False, error="History directory not created"
            )

        # Load and validate index
        try:
            metadata_index = MetadataIndex(self.project_root)
            _ = await metadata_index.load()

            index_check = await self._verify_files_in_index(metadata_index, md_files)
            if not index_check.success:
                return index_check

            snapshot_check = await self._verify_snapshots_exist(md_files)
            if not snapshot_check.success:
                return snapshot_check

            return VerificationResult(
                success=True,
                files_verified=len(md_files),
                index_valid=True,
                snapshots_created=True,
            )

        except Exception as e:
            return VerificationResult(
                success=False,
                error=f"Verification failed: {e}",
            )

    async def _verify_files_in_index(
        self, metadata_index: MetadataIndex, md_files: list[Path]
    ) -> VerificationResult:
        """Verify all files are in the index."""
        for md_file in md_files:
            if not await metadata_index.file_exists_in_index(md_file.name):
                return VerificationResult(
                    success=False,
                    error=f"File {md_file.name} not found in index",
                )
        return VerificationResult(success=True)

    async def _verify_snapshots_exist(self, md_files: list[Path]) -> VerificationResult:
        """Verify snapshots exist for all files."""
        version_manager = VersionManager(self.project_root)
        for md_file in md_files:
            snapshot_path = version_manager.get_snapshot_path(md_file.name, 1)
            if not snapshot_path.exists():
                return VerificationResult(
                    success=False,
                    error=f"Snapshot not found for {md_file.name}",
                )
        return VerificationResult(success=True)

    async def cleanup_old_backups(self, keep_last: int = 3):
        """
        Clean up old backup directories, keeping only the most recent ones.

        Args:
            keep_last: Number of backups to keep (default: 3)
        """
        backup_dirs = sorted(self.project_root.glob(".cortex-backup-*"))

        if len(backup_dirs) > keep_last:
            for old_backup in backup_dirs[:-keep_last]:
                try:
                    shutil.rmtree(old_backup)
                except OSError:
                    # Backup directory inaccessible - skip
                    pass

    async def get_backup_list(self) -> list[BackupInfo]:
        """
        Get list of available backups.

        Returns:
            List of backup info models
        """
        backup_dirs = sorted(self.project_root.glob(".cortex-backup-*"))

        backups: list[BackupInfo] = []
        for backup_dir in backup_dirs:
            # Extract timestamp from directory name
            timestamp_str = backup_dir.name.replace(".cortex-backup-", "")

            try:
                created_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                created_time = None

            # Get size
            total_size = sum(
                f.stat().st_size for f in backup_dir.glob("**/*") if f.is_file()
            )

            backups.append(
                BackupInfo(
                    path=str(backup_dir),
                    timestamp=timestamp_str,
                    created=created_time.isoformat() if created_time else None,
                    size_bytes=total_size,
                )
            )

        return backups

    async def _create_migration_backup(self, auto_backup: bool) -> Path | None:
        """Create backup for migration if requested."""
        return await self.create_backup() if auto_backup else None

    async def _process_migration_files(self, md_files: list[Path]) -> None:
        """Process all migration files."""
        managers = self._initialize_migration_managers()
        process_managers: dict[
            str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager
        ] = {
            k: cast(
                FileSystemManager | TokenCounter | MetadataIndex | VersionManager, v
            )
            for k, v in managers.items()
            if k != "graph"
        }
        await self._process_all_files(md_files, process_managers)

    async def _build_migration_dependency_graph(self) -> None:
        """Build and save dependency graph during migration."""
        managers = self._initialize_migration_managers()
        graph_managers: dict[str, DependencyGraph | MetadataIndex] = {
            "graph": cast(DependencyGraph, managers["graph"]),
            "index": cast(MetadataIndex, managers["index"]),
        }
        await self._build_and_save_dependency_graph(graph_managers)

    def _build_migration_result(
        self,
        md_files: list[Path],
        backup_dir: Path | None,
        verification: VerificationResult,
    ) -> MigrationResult:
        """Build migration result model."""
        return MigrationResult(
            status="success",
            files_migrated=len(md_files),
            backup_location=str(backup_dir) if backup_dir else None,
            details=verification,
        )
