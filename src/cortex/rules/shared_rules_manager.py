"""
Shared Rules Manager for MCP Memory Bank.

This module manages shared rules repositories using git submodules, enabling
cross-project rule sharing with automatic synchronization and context-aware loading.
"""

import asyncio
from datetime import datetime
from pathlib import Path

from ..core.retry import retry_async
from ..core.security import InputValidator
from .context_detector import ContextDetector
from .rules_loader import RulesLoader
from .rules_merger import RulesMerger
from .rules_repository import RulesRepository


class SharedRulesManager:
    """
    Manage shared rules repository with git integration.

    Features:
    - Git submodule initialization and synchronization
    - Rules manifest parsing and validation
    - Context detection for intelligent rule loading
    - Merge strategies for local and shared rules
    - Automatic rule updates with git commit/push
    """

    def __init__(
        self,
        project_root: Path,
        shared_rules_folder: str = ".shared-rules",
        local_rules_folder: str = ".cursorrules",
    ):
        """
        Initialize shared rules manager.

        Args:
            project_root: Root directory of the project
            shared_rules_folder: Path to shared rules folder (submodule)
            local_rules_folder: Path to local project rules
        """
        self.project_root: Path = Path(project_root)
        self.shared_rules_path: Path = self.project_root / shared_rules_folder
        self.local_rules_path: Path = self.project_root / local_rules_folder

        self._repository: RulesRepository | None = None
        self.loader: RulesLoader = RulesLoader(self.shared_rules_path)
        self.merger: RulesMerger = RulesMerger()
        self.context_detector: ContextDetector = ContextDetector()

    @property
    def repository(self) -> RulesRepository:
        """Get repository instance, creating it if needed."""
        if self._repository is None:

            async def git_runner(cmd: list[str]) -> dict[str, object]:
                # Always call through self.run_git_command to allow test mocking
                # Note: run_git_command delegates to _run_git_command_impl by default
                # but tests can replace it
                return await self.run_git_command(cmd)

            self._repository = RulesRepository(
                self.project_root, self.shared_rules_path, git_runner
            )
        return self._repository

    async def _run_git_command_impl(self, cmd: list[str]) -> dict[str, object]:
        """
        Internal git command implementation with retry logic.

        This is injected into the repository to allow test mocking via
        manager.run_git_command while avoiding infinite recursion.

        Args:
            cmd: Command and arguments as list

        Returns:
            Dict with success status, stdout, stderr
        """

        async def git_operation() -> dict[str, object]:
            try:
                cmd_filtered = [c for c in cmd if c]

                process = await asyncio.create_subprocess_exec(
                    *cmd_filtered,
                    cwd=str(self.project_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await process.communicate()

                return {
                    "success": process.returncode == 0,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "returncode": process.returncode,
                }

            except Exception as e:
                return {"success": False, "error": str(e), "stdout": "", "stderr": ""}

        # Retry git operations with longer delay
        return await retry_async(
            git_operation,
            max_retries=2,
            base_delay=1.0,
            exceptions=(OSError, ConnectionError, TimeoutError),
        )

    @property
    def manifest(self) -> dict[str, object] | None:
        """Get current manifest."""
        return self.loader.manifest

    @manifest.setter
    def manifest(self, value: dict[str, object] | None) -> None:
        """Set manifest value."""
        self.loader.manifest = value

    @property
    def last_sync(self) -> datetime | None:
        """Get last sync timestamp."""
        return self.repository.last_sync

    async def initialize_shared_rules(
        self, repo_url: str, force: bool = False, timeout: int = 30
    ) -> dict[str, object]:
        """
        Initialize shared rules as git submodule.

        Args:
            repo_url: Git repository URL for shared rules
            force: Force re-initialization even if exists
            timeout: Timeout in seconds for git operations

        Returns:
            Dict with initialization status and details
        """
        # Validate git URL before using it
        try:
            validated_url = InputValidator.validate_git_url(repo_url)
        except ValueError as e:
            return {
                "status": "error",
                "error": f"Invalid git URL: {e}",
                "action": "initialize_shared_rules",
            }

        result = await self.repository.initialize_submodule(validated_url, force)

        if result["status"] == "success":
            _ = await self.loader.load_manifest()
            result["initial_sync"] = True
            result["categories_found"] = self.loader.get_categories()

        return result

    async def sync_shared_rules(
        self, pull: bool = True, push: bool = False
    ) -> dict[str, object]:
        """
        Sync shared rules repository with remote.

        Args:
            pull: Pull latest changes from remote
            push: Push local changes to remote

        Returns:
            Dict with sync status and changes
        """
        result = await self.repository.sync_repository(pull, push)

        if result["status"] == "success" and pull:
            _ = await self.loader.load_manifest()

        return result

    async def load_rules_manifest(self) -> dict[str, object] | None:
        """
        Load and parse rules-manifest.json.

        Returns:
            Parsed manifest dict or None if not found
        """
        return await self.loader.load_manifest()

    async def detect_context(
        self, task_description: str, project_files: list[Path] | None = None
    ) -> dict[str, object]:
        """
        Detect context for intelligent rule loading.

        Args:
            task_description: Description of the current task
            project_files: List of project files for extension detection

        Returns:
            Dict with detected context information
        """
        return self.context_detector.detect_context(task_description, project_files)

    async def get_relevant_categories(self, context: dict[str, object]) -> list[str]:
        """
        Get relevant rule categories based on detected context.

        Args:
            context: Context dict from detect_context()

        Returns:
            List of category names to load
        """
        return self.context_detector.get_relevant_categories(context)

    async def load_category(self, category: str) -> list[dict[str, object]]:
        """
        Load all rules from a specific category.

        Args:
            category: Category name (e.g., "python", "generic")

        Returns:
            List of rule dicts with content and metadata
        """
        return await self.loader.load_category(category)

    async def merge_rules(
        self,
        shared_rules: list[dict[str, object]],
        local_rules: list[dict[str, object]],
        priority: str = "local_overrides_shared",
    ) -> list[dict[str, object]]:
        """
        Merge shared and local rules based on priority strategy.

        Args:
            shared_rules: Rules from shared repository
            local_rules: Rules from local project
            priority: "local_overrides_shared" or "shared_overrides_local"

        Returns:
            Merged list of rules
        """
        return await self.merger.merge_rules(shared_rules, local_rules, priority)

    async def update_shared_rule(
        self, category: str, file: str, content: str, commit_message: str
    ) -> dict[str, object]:
        """
        Update a shared rule and commit/push to remote.

        Args:
            category: Category name (e.g., "python")
            file: Rule filename
            content: New content for the rule
            commit_message: Git commit message

        Returns:
            Dict with update status
        """
        try:
            if not self.shared_rules_path.exists():
                return {"status": "error", "error": "Shared rules not initialized"}

            rule_path = await self.loader.create_rule_file(category, file, content)
            result = await self.repository.update_file(rule_path, commit_message)

            if result["status"] == "success":
                result["category"] = category
                result["file"] = file
                result["message"] = commit_message

            return result

        except Exception as e:
            return {"status": "error", "error": str(e), "action": "update_shared_rule"}

    async def create_shared_rule(
        self, category: str, filename: str, content: str, metadata: dict[str, object]
    ) -> dict[str, object]:
        """
        Create a new shared rule and update manifest.

        Args:
            category: Category name
            filename: New rule filename
            content: Rule content
            metadata: Rule metadata (priority, keywords, etc.)

        Returns:
            Dict with creation status
        """
        try:
            result = await self.update_shared_rule(
                category=category,
                file=filename,
                content=content,
                commit_message=f"Add new rule: {category}/{filename}",
            )

            if result["status"] != "success":
                return result

            await self._update_manifest_for_new_rule(category, filename, metadata)

            return {
                "status": "success",
                "category": category,
                "filename": filename,
                "manifest_updated": self.loader.manifest is not None,
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "action": "create_shared_rule"}

    async def _update_manifest_for_new_rule(
        self, category: str, filename: str, metadata: dict[str, object]
    ) -> None:
        """Update manifest for a new rule."""
        if not self.loader.manifest:
            _ = await self.loader.load_manifest()

        if self.loader.manifest:
            updated_manifest = self.merger.add_rule_to_manifest(
                self.loader.manifest, category, filename, metadata
            )
            await self.loader.save_manifest(updated_manifest)

            manifest_path = self.shared_rules_path / "rules-manifest.json"
            _ = await self.repository.update_file(
                manifest_path,
                f"Update manifest for new rule: {category}/{filename}",
            )

    async def run_git_command(self, cmd: list[str]) -> dict[str, object]:
        """
        Run a git command asynchronously.

        Args:
            cmd: Command and arguments as list

        Returns:
            Dict with success status, stdout, stderr
        """
        return await self._run_git_command_impl(cmd)
