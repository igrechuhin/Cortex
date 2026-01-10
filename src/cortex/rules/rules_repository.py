"""
Rules Repository Manager for MCP Memory Bank.

This module handles git operations and repository management for shared rules,
including initialization, synchronization, and update operations.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import cast


class RulesRepository:
    """
    Manage git repository operations for shared rules.

    Features:
    - Git submodule initialization and updates
    - Synchronization with remote repository
    - Pull and push operations
    - Change detection via git diff
    """

    def __init__(
        self,
        project_root: Path,
        shared_rules_path: Path,
        git_command_runner: (
            Callable[[list[str]], Awaitable[dict[str, object]]] | None
        ) = None,
    ):
        """
        Initialize rules repository manager.

        Args:
            project_root: Root directory of the project
            shared_rules_path: Path to shared rules folder (submodule)
            git_command_runner: Optional callable for running git commands (for testing)
        """
        self.project_root: Path = Path(project_root)
        self.shared_rules_path: Path = shared_rules_path
        self.last_sync: datetime | None = None
        self._git_command_runner: (
            Callable[[list[str]], Awaitable[dict[str, object]]] | None
        ) = git_command_runner

    async def run_git_command(
        self, cmd: list[str], timeout: int = 30
    ) -> dict[str, object]:
        """
        Run a git command asynchronously with timeout.

        Args:
            cmd: Command and arguments as list
            timeout: Timeout in seconds (default: 30)

        Returns:
            Dict with success status, stdout, stderr
        """
        if self._git_command_runner is not None:
            return await self._git_command_runner(cmd)

        return await self._run_git_command_internal(cmd, timeout)

    def set_git_command_runner(
        self, runner: Callable[[list[str]], Awaitable[dict[str, object]]] | None
    ) -> None:
        """
        Set git command runner for testing.

        Args:
            runner: Optional callable for running git commands
        """
        self._git_command_runner = runner

    async def _run_git_command_internal(
        self, cmd: list[str], timeout: int = 30
    ) -> dict[str, object]:
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
        except asyncio.TimeoutError:
            return self._build_git_timeout_response(timeout)
        except Exception as e:
            return {"success": False, "error": str(e), "stdout": "", "stderr": ""}

    def _build_git_success_response(
        self, process: asyncio.subprocess.Process, stdout: bytes, stderr: bytes
    ) -> dict[str, object]:
        """Build success response for git command."""
        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "returncode": process.returncode,
        }

    def _build_git_timeout_response(self, timeout: int) -> dict[str, object]:
        """Build timeout response for git command."""
        return {
            "success": False,
            "error": f"Git command timed out after {timeout}s",
            "stdout": "",
            "stderr": "",
        }

    async def initialize_submodule(
        self, repo_url: str, force: bool = False
    ) -> dict[str, object]:
        """
        Initialize shared rules as git submodule.

        Args:
            repo_url: Git repository URL for shared rules
            force: Force re-initialization even if exists

        Returns:
            Dict with initialization status and details
        """
        try:
            if self.shared_rules_path.exists() and not force:
                return await self._update_existing_submodule(repo_url)

            return await self._add_new_submodule(repo_url, force)

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "action": "initialize_shared_rules",
            }

    async def _update_existing_submodule(self, repo_url: str) -> dict[str, object]:
        """Update existing submodule.

        Args:
            repo_url: Git repository URL

        Returns:
            Success response dict
        """
        result = await self.run_git_command(
            [
                "git",
                "submodule",
                "update",
                "--init",
                "--recursive",
                str(self.shared_rules_path.relative_to(self.project_root)),
            ]
        )

        if result["success"]:
            return {
                "status": "success",
                "action": "updated_existing",
                "repo_url": repo_url,
                "local_path": str(self.shared_rules_path),
                "submodule_added": False,
            }

        return {
            "status": "error",
            "error": f"Failed to update submodule: {result.get('error', 'Unknown error')}",
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }

    async def _add_new_submodule(self, repo_url: str, force: bool) -> dict[str, object]:
        """Add new submodule.

        Args:
            repo_url: Git repository URL
            force: Force add even if exists

        Returns:
            Success or error response dict
        """
        result = await self.run_git_command(
            [
                "git",
                "submodule",
                "add",
                "-f" if force else "",
                repo_url,
                str(self.shared_rules_path.relative_to(self.project_root)),
            ]
        )

        if not result["success"]:
            return {
                "status": "error",
                "error": f"Failed to add submodule: {result.get('error', 'Unknown error')}",
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
            }

        _ = await self.run_git_command(
            ["git", "submodule", "update", "--init", "--recursive"]
        )

        return {
            "status": "success",
            "action": "initialized",
            "repo_url": repo_url,
            "local_path": str(self.shared_rules_path),
            "submodule_added": True,
        }

    async def sync_repository(
        self, pull: bool = True, push: bool = False
    ) -> dict[str, object]:
        """
        Sync repository with remote.

        Args:
            pull: Pull latest changes from remote
            push: Push local changes to remote

        Returns:
            Dict with sync status and changes
        """
        try:
            if not self.shared_rules_path.exists():
                return {
                    "status": "error",
                    "error": "Shared rules folder not found. Run initialize_shared_rules first.",
                }

            changes: dict[str, list[str]] = {"added": [], "modified": [], "deleted": []}

            if pull:
                pull_error = await self._pull_changes(changes)
                if pull_error:
                    return pull_error

            pushed = await self._push_changes(push)
            self.last_sync = datetime.now()

            return {
                "status": "success",
                "pulled": pull,
                "pushed": pushed,
                "changes": changes,
                "reindex_triggered": bool(
                    changes["added"] or changes["modified"] or changes["deleted"]
                ),
                "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "action": "sync_shared_rules"}

    async def _pull_changes(
        self, changes: dict[str, list[str]]
    ) -> dict[str, object] | None:
        """Pull changes from remote.

        Args:
            changes: Changes dictionary to update

        Returns:
            Error dict if pull fails, None otherwise
        """
        result = await self.run_git_command(
            [
                "git",
                "submodule",
                "update",
                "--remote",
                "--merge",
                str(self.shared_rules_path.relative_to(self.project_root)),
            ]
        )

        if not result["success"]:
            return {
                "status": "error",
                "error": f"Failed to pull changes: {result.get('error', 'Unknown error')}",
            }

        await self._parse_diff_changes(changes)
        return None

    async def _parse_diff_changes(self, changes: dict[str, list[str]]) -> None:
        """Parse git diff output to track changes.

        Args:
            changes: Changes dictionary to update
        """
        diff_result = await self.run_git_command(
            [
                "git",
                "-C",
                str(self.shared_rules_path),
                "diff",
                "--name-status",
                "HEAD@{1}",
                "HEAD",
            ]
        )

        # Early exit if no diff output
        if not diff_result["success"] or not diff_result["stdout"]:
            return

        # Process each line of diff output
        stdout_str = (
            str(diff_result["stdout"]) if isinstance(diff_result["stdout"], str) else ""
        )
        for line in stdout_str.strip().split("\n"):
            self._process_diff_line(line, changes)

    def _process_diff_line(self, line: str, changes: dict[str, list[str]]) -> None:
        """Process a single line from git diff output.

        Args:
            line: Diff output line
            changes: Changes dictionary to update
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
        status_map = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
        }

        category = status_map.get(status)
        if category:
            changes[category].append(file)

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
            ["git", "-C", str(self.shared_rules_path), "push"]
        )
        return cast(bool, result.get("success", False))

    async def _git_add_file(self, file_path: Path) -> dict[str, object] | None:
        """Add file to git staging area, return error dict if failed."""
        add_result = await self.run_git_command(
            [
                "git",
                "-C",
                str(self.shared_rules_path),
                "add",
                str(file_path.relative_to(self.shared_rules_path)),
            ]
        )
        if not add_result["success"]:
            return {
                "status": "error",
                "error": f"Failed to git add: {add_result.get('error', 'Unknown error')}",
            }
        return None

    async def _git_commit_file(self, commit_message: str) -> tuple[bool, str | None]:
        """Commit staged changes, return (success, commit_hash)."""
        commit_result = await self.run_git_command(
            [
                "git",
                "-C",
                str(self.shared_rules_path),
                "commit",
                "-m",
                commit_message,
            ]
        )
        committed = cast(bool, commit_result["success"])
        commit_hash = await self._get_commit_hash() if committed else None
        return committed, commit_hash

    async def _git_push_changes(self) -> bool:
        """Push committed changes to remote."""
        push_result = await self.run_git_command(
            ["git", "-C", str(self.shared_rules_path), "push"]
        )
        return cast(bool, push_result["success"])

    def _build_update_success_response(
        self, committed: bool, pushed: bool, commit_hash: str | None
    ) -> dict[str, object]:
        """Build success response for file update."""
        return {
            "status": "success",
            "committed": committed,
            "pushed": pushed,
            "commit_hash": commit_hash,
        }

    async def update_file(
        self, file_path: Path, commit_message: str
    ) -> dict[str, object]:
        """
        Add, commit, and push a file change.

        Args:
            file_path: Path to file (relative to shared_rules_path)
            commit_message: Git commit message

        Returns:
            Dict with update status
        """
        try:
            error_response = await self._git_add_file(file_path)
            if error_response:
                return error_response

            committed, commit_hash = await self._git_commit_file(commit_message)
            pushed = await self._git_push_changes()

            return self._build_update_success_response(committed, pushed, commit_hash)

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _get_commit_hash(self) -> str | None:
        """Get current commit hash.

        Returns:
            Commit hash or None if failed
        """
        hash_result = await self.run_git_command(
            ["git", "-C", str(self.shared_rules_path), "rev-parse", "HEAD"]
        )
        if hash_result["success"]:
            stdout_value = hash_result["stdout"]
            return (
                str(stdout_value).strip()
                if isinstance(stdout_value, str)
                else str(stdout_value).strip() if stdout_value else None
            )
        return None
