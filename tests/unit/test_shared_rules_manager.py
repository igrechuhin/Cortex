"""Unit tests for SharedRulesManager - Phase 6"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cortex.rules.context_detector import ContextDetector
from cortex.rules.shared_rules_manager import SharedRulesManager


class TestSharedRulesManagerInitialization:
    """Test SharedRulesManager initialization."""

    def test_initialization_sets_up_paths(self, temp_project_root: Path):
        """Test manager initializes with correct paths."""
        # Arrange & Act
        manager = SharedRulesManager(
            project_root=temp_project_root,
            shared_rules_folder=".shared-rules",
            local_rules_folder=".cursorrules",
        )

        # Assert
        assert manager.project_root == temp_project_root
        assert manager.shared_rules_path == temp_project_root / ".shared-rules"
        assert manager.local_rules_path == temp_project_root / ".cursorrules"
        assert manager.manifest is None
        assert manager.last_sync is None
        assert isinstance(manager.context_detector, ContextDetector)

    def test_initialization_with_custom_folders(self, temp_project_root: Path):
        """Test initialization with custom folder names."""
        # Arrange & Act
        manager = SharedRulesManager(
            project_root=temp_project_root,
            shared_rules_folder="rules/shared",
            local_rules_folder="rules/local",
        )

        # Assert
        assert manager.shared_rules_path == temp_project_root / "rules/shared"
        assert manager.local_rules_path == temp_project_root / "rules/local"


class TestInitializeSharedRules:
    """Test shared rules initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_new_submodule(self, temp_project_root: Path):
        """Test initializing new git submodule."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        repo_url = "https://github.com/example/shared-rules.git"

        # Mock git command
        manager.run_git_command = AsyncMock(
            return_value={"success": True, "stdout": "", "stderr": ""}
        )

        # Create manifest
        manifest_path = manager.shared_rules_path
        manifest_path.mkdir(parents=True, exist_ok=True)
        manifest_file = manifest_path / "rules-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {"generic": {"rules": []}},
        }
        _ = manifest_file.write_text(json.dumps(manifest_data))

        # Act
        result = await manager.initialize_shared_rules(repo_url, force=False)

        # Assert
        assert result["status"] == "success"
        assert result["repo_url"] == repo_url

    @pytest.mark.asyncio
    async def test_initialize_updates_existing_submodule(self, temp_project_root: Path):
        """Test updating existing submodule."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        repo_url = "https://github.com/example/shared-rules.git"

        # Create existing directory
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {"python": {"rules": []}, "generic": {"rules": []}},
        }
        _ = manifest_file.write_text(json.dumps(manifest_data))

        # Mock git command
        manager.run_git_command = AsyncMock(
            return_value={"success": True, "stdout": "", "stderr": ""}
        )

        # Act
        result = await manager.initialize_shared_rules(repo_url, force=False)

        # Assert
        assert result["status"] == "success"
        assert result["action"] == "updated_existing"
        categories_found = result.get("categories_found")
        assert isinstance(categories_found, list)
        assert "python" in categories_found
        assert "generic" in categories_found

    @pytest.mark.asyncio
    async def test_initialize_with_force_reinitializes(self, temp_project_root: Path):
        """Test force re-initialization."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        repo_url = "https://github.com/example/shared-rules.git"

        # Create existing directory
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        # Mock git commands
        manager.run_git_command = AsyncMock(
            return_value={"success": True, "stdout": "", "stderr": ""}
        )

        # Create manifest
        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        _ = manifest_file.write_text(json.dumps({"version": "1.0", "categories": {}}))

        # Act
        result = await manager.initialize_shared_rules(repo_url, force=True)

        # Assert
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_initialize_handles_git_failure(self, temp_project_root: Path):
        """Test handling git command failure."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        repo_url = "https://github.com/example/shared-rules.git"

        # Mock git command failure
        manager.run_git_command = AsyncMock(
            return_value={
                "success": False,
                "error": "Repository not found",
                "stdout": "",
                "stderr": "",
            }
        )

        # Act
        result = await manager.initialize_shared_rules(repo_url, force=False)

        # Assert
        assert result["status"] == "error"
        assert "error" in result


class TestSyncSharedRules:
    """Test shared rules synchronization."""

    @pytest.mark.asyncio
    async def test_sync_pulls_changes(self, temp_project_root: Path):
        """Test syncing pulls changes from remote."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {"generic": {"rules": []}},
        }
        _ = manifest_file.write_text(json.dumps(manifest_data))

        # Mock git commands
        manager.run_git_command = AsyncMock(
            return_value={"success": True, "stdout": "", "stderr": ""}
        )

        # Act
        result = await manager.sync_shared_rules(pull=True, push=False)

        # Assert
        assert result["status"] == "success"
        assert result["pulled"] is True
        assert result["pushed"] is False

    @pytest.mark.asyncio
    async def test_sync_pushes_changes(self, temp_project_root: Path):
        """Test syncing pushes changes to remote."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        _ = manifest_file.write_text(json.dumps({"version": "1.0", "categories": {}}))

        # Mock git commands
        manager.run_git_command = AsyncMock(
            return_value={"success": True, "stdout": "", "stderr": ""}
        )

        # Act
        result = await manager.sync_shared_rules(pull=False, push=True)

        # Assert
        assert result["status"] == "success"
        assert result["pushed"] is True

    @pytest.mark.asyncio
    async def test_sync_detects_changes(self, temp_project_root: Path):
        """Test sync detects added/modified/deleted files."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        _ = manifest_file.write_text(json.dumps({"version": "1.0", "categories": {}}))

        # Mock git commands
        diff_output = "A\tpython/style.md\nM\tgeneric/best-practices.md\nD\told-file.md"
        manager.run_git_command = AsyncMock(
            side_effect=[
                {"success": True, "stdout": "", "stderr": ""},  # submodule update
                {
                    "success": True,
                    "stdout": diff_output,
                    "stderr": "",
                },  # diff
            ]
        )

        # Act
        result = await manager.sync_shared_rules(pull=True, push=False)

        # Assert
        assert result["status"] == "success"
        changes = result.get("changes")
        assert isinstance(changes, dict)
        assert "python/style.md" in changes["added"]
        assert "generic/best-practices.md" in changes["modified"]
        assert "old-file.md" in changes["deleted"]

    @pytest.mark.asyncio
    async def test_sync_without_submodule_returns_error(self, temp_project_root: Path):
        """Test sync fails gracefully if submodule not initialized."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        # Act
        result = await manager.sync_shared_rules(pull=True, push=False)

        # Assert
        assert result["status"] == "error"
        error_msg = result.get("error")
        assert isinstance(error_msg, str)
        assert "not found" in error_msg or "not initialized" in error_msg


class TestLoadRulesManifest:
    """Test rules manifest loading."""

    @pytest.mark.asyncio
    async def test_load_manifest_parses_json(self, temp_project_root: Path):
        """Test loading and parsing manifest file."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {"description": "Python rules", "rules": []},
                "generic": {"description": "Generic rules", "rules": []},
            },
        }
        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        _ = manifest_file.write_text(json.dumps(manifest_data))

        # Act
        result = await manager.load_rules_manifest()

        # Assert
        assert result is not None
        assert result["version"] == "1.0"
        categories = result.get("categories")
        assert isinstance(categories, dict)
        assert "python" in categories
        assert "generic" in categories
        assert manager.manifest == result

    @pytest.mark.asyncio
    async def test_load_manifest_returns_none_if_not_found(
        self, temp_project_root: Path
    ):
        """Test loading returns None if manifest doesn't exist."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        # Act
        result = await manager.load_rules_manifest()

        # Assert
        assert result is None
        assert manager.manifest is None

    @pytest.mark.asyncio
    async def test_load_manifest_handles_invalid_json(self, temp_project_root: Path):
        """Test loading handles invalid JSON gracefully."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        _ = manifest_file.write_text("{ invalid json }")

        # Act
        result = await manager.load_rules_manifest()

        # Assert
        assert result is None
        assert manager.manifest is None


class TestDetectContext:
    """Test context detection delegation."""

    @pytest.mark.asyncio
    async def test_detect_context_delegates_to_detector(self, temp_project_root: Path):
        """Test context detection delegates to ContextDetector."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        task = "Write Python tests"

        # Act
        context = await manager.detect_context(task)

        # Assert
        assert "detected_languages" in context
        assert "detected_frameworks" in context
        assert "categories_to_load" in context

    @pytest.mark.asyncio
    async def test_detect_context_with_files(self, temp_project_root: Path):
        """Test context detection with project files."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        files = [Path("src/main.py"), Path("src/utils.py")]

        # Act
        context = await manager.detect_context("Test task", project_files=files)

        # Assert
        languages = context.get("detected_languages")
        assert isinstance(languages, list)
        assert "python" in languages


class TestGetRelevantCategories:
    """Test getting relevant categories."""

    @pytest.mark.asyncio
    async def test_get_relevant_categories_delegates(self, temp_project_root: Path):
        """Test getting relevant categories delegates to detector."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        context: dict[str, object] = {
            "languages": {"python"},
            "frameworks": {"django"},
            "task_type": "testing",
            "categories_to_load": {"generic", "python", "django", "testing"},
        }

        # Act
        categories = await manager.get_relevant_categories(context)

        # Assert
        assert "generic" in categories
        assert "python" in categories
        assert "django" in categories
        assert "testing" in categories


class TestLoadCategory:
    """Test loading rules from a category."""

    @pytest.mark.asyncio
    async def test_load_category_loads_rules(self, temp_project_root: Path):
        """Test loading rules from a category."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        # Create category directory and rule file
        python_dir = manager.shared_rules_path / "python"
        python_dir.mkdir(parents=True, exist_ok=True)
        rule_file = python_dir / "style.md"
        _ = rule_file.write_text("# Python Style Guide\n\nUse PEP 8.")

        # Create manifest
        manifest_data = {
            "version": "1.0",
            "categories": {
                "python": {
                    "rules": [
                        {
                            "file": "style.md",
                            "priority": 80,
                            "keywords": ["style", "pep8"],
                        }
                    ]
                }
            },
        }
        manager.manifest = cast(dict[str, object], manifest_data)

        # Act
        rules = await manager.load_category("python")

        # Assert
        assert len(rules) == 1
        assert rules[0]["category"] == "python"
        assert rules[0]["file"] == "style.md"
        assert rules[0]["priority"] == 80
        content = rules[0].get("content")
        assert isinstance(content, str)
        assert "PEP 8" in content
        assert rules[0]["source"] == "shared"

    @pytest.mark.asyncio
    async def test_load_category_returns_empty_if_not_found(
        self, temp_project_root: Path
    ):
        """Test loading returns empty list for nonexistent category."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.manifest = {"version": "1.0", "categories": {}}

        # Act
        rules = await manager.load_category("nonexistent")

        # Assert
        assert rules == []

    @pytest.mark.asyncio
    async def test_load_category_loads_manifest_if_needed(
        self, temp_project_root: Path
    ):
        """Test loading category loads manifest if not already loaded."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {"generic": {"rules": []}},
        }
        _ = manifest_file.write_text(json.dumps(manifest_data))

        # Act
        _ = await manager.load_category("generic")

        # Assert
        assert manager.manifest is not None
        categories = manager.manifest.get("categories")
        assert isinstance(categories, dict)
        assert "generic" in categories

    @pytest.mark.asyncio
    async def test_load_category_skips_missing_files(self, temp_project_root: Path):
        """Test loading skips rules with missing files."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        # Create category directory
        python_dir = manager.shared_rules_path / "python"
        python_dir.mkdir(parents=True, exist_ok=True)

        # Create manifest with missing file reference
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {"rules": [{"file": "missing.md", "priority": 50}]}
            },
        }
        manager.manifest = manifest_data

        # Act
        rules = await manager.load_category("python")

        # Assert
        assert rules == []


class TestMergeRules:
    """Test merging shared and local rules."""

    @pytest.mark.asyncio
    async def test_merge_local_overrides_shared(self, temp_project_root: Path):
        """Test local rules override shared rules."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        shared_rules: list[dict[str, object]] = [
            {"file": "style.md", "priority": 50, "source": "shared"},
            {"file": "patterns.md", "priority": 60, "source": "shared"},
        ]

        local_rules: list[dict[str, object]] = [
            {"file": "style.md", "priority": 90, "source": "local"},
        ]

        # Act
        merged = await manager.merge_rules(
            shared_rules, local_rules, priority="local_overrides_shared"
        )

        # Assert
        assert len(merged) == 2
        # Local style.md should override shared
        style_rules = [r for r in merged if r["file"] == "style.md"]
        assert len(style_rules) == 1
        assert style_rules[0]["source"] == "local"

    @pytest.mark.asyncio
    async def test_merge_shared_overrides_local(self, temp_project_root: Path):
        """Test shared rules override local rules."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        shared_rules: list[dict[str, object]] = [
            {"file": "security.md", "priority": 95, "source": "shared"},
        ]

        local_rules: list[dict[str, object]] = [
            {"file": "security.md", "priority": 70, "source": "local"},
        ]

        # Act
        merged = await manager.merge_rules(
            shared_rules, local_rules, priority="shared_overrides_local"
        )

        # Assert
        assert len(merged) == 1
        assert merged[0]["source"] == "shared"

    @pytest.mark.asyncio
    async def test_merge_priority_based(self, temp_project_root: Path):
        """Test priority-based merging."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        shared_rules: list[dict[str, object]] = [
            {"file": "rule1.md", "priority": 80, "source": "shared"},
        ]

        local_rules: list[dict[str, object]] = [
            {"file": "rule2.md", "priority": 90, "source": "local"},
        ]

        # Act
        merged = await manager.merge_rules(
            shared_rules, local_rules, priority="priority"
        )

        # Assert
        assert len(merged) == 2
        # Should be sorted by priority (highest first)
        assert merged[0]["priority"] == 90
        assert merged[1]["priority"] == 80

    @pytest.mark.asyncio
    async def test_merge_handles_empty_lists(self, temp_project_root: Path):
        """Test merging handles empty rule lists."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        # Act
        merged = await manager.merge_rules([], [], priority="local_overrides_shared")

        # Assert
        assert merged == []


class TestUpdateSharedRule:
    """Test updating shared rules."""

    @pytest.mark.asyncio
    async def test_update_shared_rule_creates_file(self, temp_project_root: Path):
        """Test updating shared rule creates file if needed."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        # Create category directory
        python_dir = manager.shared_rules_path / "python"
        python_dir.mkdir(parents=True, exist_ok=True)

        # Mock git commands
        manager.run_git_command = AsyncMock(
            return_value={"success": True, "stdout": "", "stderr": ""}
        )

        # Act
        result = await manager.update_shared_rule(
            category="python",
            file="new-rule.md",
            content="# New Rule\n\nContent here.",
            commit_message="Add new Python rule",
        )

        # Assert
        assert result["status"] == "success"
        rule_path = python_dir / "new-rule.md"
        assert rule_path.exists()

    @pytest.mark.asyncio
    async def test_update_shared_rule_modifies_existing(self, temp_project_root: Path):
        """Test updating existing rule file."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        # Create category and existing rule
        python_dir = manager.shared_rules_path / "python"
        python_dir.mkdir(parents=True, exist_ok=True)
        rule_file = python_dir / "existing.md"
        _ = rule_file.write_text("# Old Content")

        # Mock git commands
        manager.run_git_command = AsyncMock(
            return_value={"success": True, "stdout": "", "stderr": ""}
        )

        # Act
        result = await manager.update_shared_rule(
            category="python",
            file="existing.md",
            content="# Updated Content",
            commit_message="Update existing rule",
        )

        # Assert
        assert result["status"] == "success"
        assert "Updated Content" in rule_file.read_text()

    @pytest.mark.asyncio
    async def test_update_shared_rule_commits_and_pushes(self, temp_project_root: Path):
        """Test updating rule commits and pushes changes."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        generic_dir = manager.shared_rules_path / "generic"
        generic_dir.mkdir(parents=True, exist_ok=True)

        # Mock git commands
        git_calls: list[list[str]] = []

        async def mock_git_command(cmd: list[str]) -> dict[str, object]:
            git_calls.append(cmd)
            return {"success": True, "stdout": "", "stderr": ""}

        manager.run_git_command = mock_git_command

        # Act
        result = await manager.update_shared_rule(
            category="generic",
            file="test.md",
            content="# Test",
            commit_message="Add test rule",
        )

        # Assert
        assert result["status"] == "success"
        # Should have add, commit, push commands
        assert len(git_calls) >= 3
        cmd_strings: list[str] = [" ".join(cmd) for cmd in git_calls]
        assert any("add" in cmd_str for cmd_str in cmd_strings)
        assert any("commit" in cmd_str for cmd_str in cmd_strings)
        assert any("push" in cmd_str for cmd_str in cmd_strings)


class TestCreateSharedRule:
    """Test creating new shared rules."""

    @pytest.mark.asyncio
    async def test_create_shared_rule_creates_new_file(self, temp_project_root: Path):
        """Test creating a brand new shared rule."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {"python": {"rules": []}},
        }
        _ = manifest_file.write_text(json.dumps(manifest_data))
        manager.manifest = manifest_data

        # Create category directory
        python_dir = manager.shared_rules_path / "python"
        python_dir.mkdir(parents=True, exist_ok=True)

        # Mock git commands
        manager.run_git_command = AsyncMock(
            return_value={"success": True, "stdout": "", "stderr": ""}
        )

        # Act
        result = await manager.create_shared_rule(
            category="python",
            filename="new-rule.md",
            content="# New Rule",
            metadata={"priority": 75, "keywords": ["testing", "pytest"]},
        )

        # Assert
        assert result["status"] == "success"
        rule_path = python_dir / "new-rule.md"
        assert rule_path.exists()

        # Check manifest was updated
        updated_manifest = json.loads(manifest_file.read_text())
        python_rules = updated_manifest["categories"]["python"]["rules"]
        assert len(python_rules) == 1
        assert python_rules[0]["file"] == "new-rule.md"
        assert python_rules[0]["priority"] == 75


class TestRunGitCommand:
    """Test git command execution."""

    @pytest.mark.asyncio
    async def test_run_git_command_executes_successfully(self, temp_project_root: Path):
        """Test running git command successfully."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        # Mock asyncio.create_subprocess_exec
        mock_process = Mock()
        mock_process.communicate = AsyncMock(return_value=(b"Success output", b""))
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            # Act
            result = await manager.run_git_command(["git", "status"])

            # Assert
            assert result["success"] is True
            stdout = result.get("stdout")
            assert isinstance(stdout, str)
            assert "Success output" in stdout

    @pytest.mark.asyncio
    async def test_run_git_command_handles_failure(self, temp_project_root: Path):
        """Test running git command handles failure."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        # Mock asyncio.create_subprocess_exec
        mock_process = Mock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error occurred"))
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            # Act
            result = await manager.run_git_command(["git", "invalid-command"])

            # Assert
            assert result["success"] is False
            stderr = result.get("stderr")
            assert isinstance(stderr, str)
            assert "Error occurred" in stderr
            # When git command fails, we get returncode and stderr but not "error" key
            assert result.get("returncode") == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_load_category_with_corrupted_manifest(self, temp_project_root: Path):
        """Test loading category with invalid manifest data."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.manifest = {"version": "1.0", "categories": "not-a-dict"}

        # Act
        rules = await manager.load_category("python")

        # Assert
        assert rules == []

    @pytest.mark.asyncio
    async def test_merge_rules_with_missing_priority(self, temp_project_root: Path):
        """Test merging rules with missing priority field."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)

        shared_rules: list[dict[str, object]] = [
            {"file": "rule1.md", "source": "shared"}
        ]
        local_rules: list[dict[str, object]] = [{"file": "rule2.md", "source": "local"}]

        # Act - should handle missing priority gracefully
        merged = await manager.merge_rules(
            shared_rules, local_rules, priority="priority"
        )

        # Assert
        assert len(merged) == 2

    @pytest.mark.asyncio
    async def test_sync_with_empty_diff_output(self, temp_project_root: Path):
        """Test sync handles empty diff output."""
        # Arrange
        manager = SharedRulesManager(project_root=temp_project_root)
        manager.shared_rules_path.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest_file = manager.shared_rules_path / "rules-manifest.json"
        _ = manifest_file.write_text(json.dumps({"version": "1.0", "categories": {}}))

        # Mock git commands with empty diff
        manager.run_git_command = AsyncMock(
            side_effect=[
                {"success": True, "stdout": "", "stderr": ""},  # submodule update
                {"success": True, "stdout": "", "stderr": ""},  # pull
                {"success": True, "stdout": "", "stderr": ""},  # diff (empty)
            ]
        )

        # Act
        result = await manager.sync_shared_rules(pull=True, push=False)

        # Assert
        assert result["status"] == "success"
        changes_raw = result.get("changes")
        assert isinstance(changes_raw, dict)
        changes: dict[str, list[str]] = cast(dict[str, list[str]], changes_raw)
        added = changes.get("added", [])
        modified = changes.get("modified", [])
        deleted = changes.get("deleted", [])
        assert isinstance(added, list)
        assert isinstance(modified, list)
        assert isinstance(deleted, list)
        assert len(added) == 0
        assert len(modified) == 0
        assert len(deleted) == 0
