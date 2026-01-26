"""
Synapse Repository Manager for MCP Memory Bank.

This module handles git operations and repository management for Synapse,
including initialization, synchronization, and update operations.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from cortex.core.security import CommitMessageSanitizer
from cortex.rules.models import (
    GitCommandResult,
    SubmoduleInitResult,
    SyncChanges,
    SyncResult,
    UpdateResult,
)


class SynapseRepository:
    """
    Manage git repository operations for Synapse.

    Features:
    - Git submodule initialization and updates
    - Synchronization with remote repository
    - Pull and push operations
    - Change detection via git diff
    """

    def __init__(
        self,
        project_root: Path,
        synapse_path: Path,
        git_command_runner: (
            Callable[[list[str]], Awaitable[GitCommandResult]] | None
        ) = None,
    ):
        """
        Initialize Synapse repository manager.

        Args:
            project_root: Root directory of the project
            synapse_path: Path to Synapse folder (submodule)
            git_command_runner: Optional callable for running git commands (for testing)
        """
        self.project_root: Path = Path(project_root)
        self.synapse_path: Path = synapse_path
        self.last_sync: datetime | None = None
        self.git_command_runner: (
            Callable[[list[str]], Awaitable[GitCommandResult]] | None
        ) = git_command_runner

    async def run_git_command(
        self, cmd: list[str], timeout: int = 30
    ) -> GitCommandResult:
        """
        Run a git command asynchronously with timeout.

        Args:
            cmd: Command and arguments as list
            timeout: Timeout in seconds (default: 30)

        Returns:
            Git command result model
        """
        if self.git_command_runner is not None:
            return await self.git_command_runner(cmd)

        return await self._run_git_command_internal(cmd, timeout)

    def set_git_command_runner(
        self, runner: Callable[[list[str]], Awaitable[GitCommandResult]] | None
    ) -> None:
        """
        Set git command runner for testing.

        Args:
            runner: Optional callable for running git commands
        """
        self.git_command_runner = runner

    async def _run_git_command_internal(
        self, cmd: list[str], timeout: int = 30
    ) -> GitCommandResult:
        """Internal method to run git command."""
        try:
            cmd = [c for c in cmd if c]
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.project_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=timeout,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            return self._build_git_success_response(process, stdout, stderr)
        except TimeoutError:
            return self._build_git_timeout_response(timeout)
        except Exception as e:
            return GitCommandResult(success=False, error=str(e), stdout="", stderr="")

    def _build_git_success_response(
        self, process: asyncio.subprocess.Process, stdout: bytes, stderr: bytes
    ) -> GitCommandResult:
        """Build success response for git command."""
        return GitCommandResult(
            success=process.returncode == 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            returncode=process.returncode,
        )

    def _build_git_timeout_response(self, timeout: int) -> GitCommandResult:
        """Build timeout response for git command."""
        return GitCommandResult(
            success=False,
            error=f"Git command timed out after {timeout}s",
            stdout="",
            stderr="",
        )

    async def initialize_submodule(
        self, repo_url: str, force: bool = False
    ) -> SubmoduleInitResult:
        """
        Initialize Synapse as git submodule.

        Args:
            repo_url: Git repository URL for Synapse
            force: Force re-initialization even if exists

        Returns:
            Submodule initialization result model
        """
        try:
            if self.synapse_path.exists() and not force:
                return await self._update_existing_submodule(repo_url)

            return await self._add_new_submodule(repo_url, force)

        except Exception as e:
            return SubmoduleInitResult(
                status="error",
                error=str(e),
                action="initialize_synapse",
            )

    async def _update_existing_submodule(self, repo_url: str) -> SubmoduleInitResult:
        """Update existing submodule.

        Args:
            repo_url: Git repository URL

        Returns:
            Submodule initialization result model
        """
        result = await self.run_git_command(
            [
                "git",
                "submodule",
                "update",
                "--init",
                "--recursive",
                str(self.synapse_path.relative_to(self.project_root)),
            ]
        )

        if result.success:
            return SubmoduleInitResult(
                status="success",
                action="updated_existing",
                repo_url=repo_url,
                local_path=str(self.synapse_path),
                submodule_added=False,
            )

        return SubmoduleInitResult(
            status="error",
            error=f"Failed to update submodule: {result.error or 'Unknown error'}",
            stdout=result.stdout,
            stderr=result.stderr,
        )

    async def _add_new_submodule(
        self, repo_url: str, force: bool
    ) -> SubmoduleInitResult:
        """Add new submodule.

        Args:
            repo_url: Git repository URL
            force: Force add even if exists

        Returns:
            Submodule initialization result model
        """
        result = await self.run_git_command(
            [
                "git",
                "submodule",
                "add",
                "-f" if force else "",
                repo_url,
                str(self.synapse_path.relative_to(self.project_root)),
            ]
        )

        if not result.success:
            return SubmoduleInitResult(
                status="error",
                error=f"Failed to add submodule: {result.error or 'Unknown error'}",
                stdout=result.stdout,
                stderr=result.stderr,
            )

        _ = await self.run_git_command(
            ["git", "submodule", "update", "--init", "--recursive"]
        )

        return SubmoduleInitResult(
            status="success",
            action="initialized",
            repo_url=repo_url,
            local_path=str(self.synapse_path),
            submodule_added=True,
        )

    async def sync_repository(
        self, pull: bool = True, push: bool = False
    ) -> SyncResult:
        """
        Sync repository with remote.

        Args:
            pull: Pull latest changes from remote
            push: Push local changes to remote

        Returns:
            Sync result model
        """
        try:
            if not self.synapse_path.exists():
                return SyncResult(
                    status="error",
                    error="Synapse folder not found. Run initialize_synapse first.",
                )

            changes = SyncChanges(added=[], modified=[], deleted=[])

            if pull:
                pull_error = await self._pull_changes(changes)
                if pull_error:
                    return pull_error

            pushed = await self._push_changes(push)
            self.last_sync = datetime.now()

            return SyncResult(
                status="success",
                pulled=pull,
                pushed=pushed,
                changes=changes,
            )

        except Exception as e:
            return SyncResult(status="error", error=str(e))

    async def _pull_changes(self, changes: SyncChanges) -> SyncResult | None:
        """Pull changes from remote.

        Args:
            changes: Changes model to update

        Returns:
            Error result if pull fails, None otherwise
        """
        result = await self.run_git_command(
            [
                "git",
                "submodule",
                "update",
                "--remote",
                "--merge",
                str(self.synapse_path.relative_to(self.project_root)),
            ]
        )

        if not result.success:
            return SyncResult(
                status="error",
                error=f"Failed to pull changes: {result.error or 'Unknown error'}",
            )

        await self._parse_diff_changes(changes)
        return None

    async def _parse_diff_changes(self, changes: SyncChanges) -> None:
        """Parse git diff output to track changes.

        Args:
            changes: Changes dictionary to update
        """
        diff_result = await self.run_git_command(
            [
                "git",
                "-C",
                str(self.synapse_path),
                "diff",
                "--name-status",
                "HEAD@{1}",
                "HEAD",
            ]
        )

        # Early exit if no diff output
        if not diff_result.success or not diff_result.stdout:
            return

        # Process each line of diff output
        for line in diff_result.stdout.strip().split("\n"):
            self._process_diff_line(line, changes)

    def _process_diff_line(self, line: str, changes: SyncChanges) -> None:
        """Process a single line from git diff output.

        Args:
            line: Diff output line
            changes: Changes model to update
        """
        # Skip empty lines
        if not line:
            return

        # Parse status and file path
        parts = line.split("\t")
        if len(parts) != 2:
            return

        status, file = parts

        # Map status to change category
        if status == "A":
            changes.added.append(file)
        elif status == "M":
            changes.modified.append(file)
        elif status == "D":
            changes.deleted.append(file)

    async def _push_changes(self, push: bool) -> bool:
        """Push changes to remote.

        Args:
            push: Whether to push changes

        Returns:
            True if push succeeded, False otherwise
        """
        if not push:
            return False

        result = await self.run_git_command(
            ["git", "-C", str(self.synapse_path), "push"]
        )
        return result.success

    async def _git_add_file(self, file_path: Path) -> UpdateResult | None:
        """Add file to git staging area, return error result if failed."""
        add_result = await self.run_git_command(
            [
                "git",
                "-C",
                str(self.synapse_path),
                "add",
                str(file_path.relative_to(self.synapse_path)),
            ]
        )
        if not add_result.success:
            return UpdateResult(
                status="error",
                error=f"Failed to git add: {add_result.error or 'Unknown error'}",
            )
        return None

    async def _git_commit_file(self, commit_message: str) -> tuple[bool, str | None]:
        """Commit staged changes, return (success, commit_hash).

        The commit message is sanitized to prevent command injection attacks.
        """
        # Sanitize commit message to prevent command injection
        sanitized_message = CommitMessageSanitizer.sanitize(commit_message)

        commit_result = await self.run_git_command(
            [
                "git",
                "-C",
                str(self.synapse_path),
                "commit",
                "-m",
                sanitized_message,
            ]
        )
        committed = commit_result.success
        commit_hash = await self._get_commit_hash() if committed else None
        return committed, commit_hash

    async def _git_push_changes(self) -> bool:
        """Push committed changes to remote."""
        push_result = await self.run_git_command(
            ["git", "-C", str(self.synapse_path), "push"]
        )
        return push_result.success

    def _build_update_success_response(
        self, committed: bool, pushed: bool, commit_hash: str | None
    ) -> UpdateResult:
        """Build success response for file update."""
        return UpdateResult(
            status="success",
            committed=committed,
            pushed=pushed,
            commit_hash=commit_hash,
        )

    async def update_file(self, file_path: Path, commit_message: str) -> UpdateResult:
        """
        Add, commit, and push a file change.

        Args:
            file_path: Path to file (relative to synapse_path)
            commit_message: Git commit message

        Returns:
            Update result model
        """
        try:
            error_response = await self._git_add_file(file_path)
            if error_response:
                return error_response

            committed, commit_hash = await self._git_commit_file(commit_message)
            pushed = await self._git_push_changes()

            return self._build_update_success_response(committed, pushed, commit_hash)

        except Exception as e:
            return UpdateResult(status="error", error=str(e))

    async def _get_commit_hash(self) -> str | None:
        """Get current commit hash.

        Returns:
            Commit hash or None if failed
        """
        hash_result = await self.run_git_command(
            ["git", "-C", str(self.synapse_path), "rev-parse", "HEAD"]
        )
        if hash_result.success:
            return hash_result.stdout.strip() if hash_result.stdout else None
        return None
