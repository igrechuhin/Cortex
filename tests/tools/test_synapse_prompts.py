"""
Comprehensive tests for Synapse Prompts Registration

This test suite provides comprehensive coverage for:
- get_synapse_prompts_path()
- load_prompts_manifest()
- load_prompt_content()
- create_prompt_function()
- process_prompt_info()
- log_registration_summary()
- register_synapse_prompts()
- All error paths and edge cases
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools import synapse_prompts

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_project_root(tmp_path: Path) -> Path:
    """Create temporary project root with .cortex structure."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (get_cortex_path(project_root, CortexResourceType.SYNAPSE) / "prompts").mkdir(
        parents=True
    )
    return project_root


@pytest.fixture
def prompts_dir(temp_project_root: Path) -> Path:
    """Get prompts directory path."""
    return get_cortex_path(temp_project_root, CortexResourceType.SYNAPSE) / "prompts"


@pytest.fixture
def sample_manifest(prompts_dir: Path) -> Path:
    """Create sample prompts manifest."""
    manifest_path = prompts_dir / "prompts-manifest.json"
    manifest_data = {
        "version": "1.0",
        "categories": {
            "general": {
                "prompts": [
                    {
                        "file": "test-prompt.md",
                        "name": "test_prompt",
                        "description": "Test prompt description",
                    }
                ]
            }
        },
    }
    _ = manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
    return manifest_path


@pytest.fixture
def sample_prompt_file(prompts_dir: Path) -> Path:
    """Create sample prompt file."""
    prompt_file = prompts_dir / "test-prompt.md"
    _ = prompt_file.write_text(
        "# Test Prompt\n\nThis is a test prompt.", encoding="utf-8"
    )
    return prompt_file


# ============================================================================
# Tests for get_synapse_prompts_path()
# ============================================================================


class TestGetSynapsePromptsPath:
    """Tests for get_synapse_prompts_path()."""

    def test_finds_prompts_from_cwd(self, temp_project_root: Path, prompts_dir: Path):
        """Test finding prompts directory from current working directory."""
        # Arrange
        with patch(
            "cortex.tools.synapse.prompts_paths.Path.cwd",
            return_value=temp_project_root,
        ):
            # Act
            result = synapse_prompts.get_synapse_prompts_path()

            # Assert
            assert result == prompts_dir

    def test_finds_prompts_from_parent(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test finding prompts directory from parent directory."""
        # Arrange
        subdir = temp_project_root / "subdir"
        subdir.mkdir()
        with patch("cortex.tools.synapse.prompts_paths.Path.cwd", return_value=subdir):
            # Act
            result = synapse_prompts.get_synapse_prompts_path()

            # Assert
            assert result == prompts_dir

    def test_finds_prompts_from_module_location(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test finding prompts directory from module file location."""
        # Arrange
        module_file_path = (
            temp_project_root / "src" / "cortex" / "tools" / "synapse_prompts.py"
        )
        with patch(
            "cortex.tools.synapse.prompts_paths.Path.cwd", return_value=Path("/tmp")
        ):
            with patch(
                "cortex.tools.synapse.prompts_paths._paths_anchor",
                return_value=Path(str(module_file_path)),
            ):
                # Act
                result = synapse_prompts.get_synapse_prompts_path()

                # Assert
                assert result == prompts_dir

    def test_returns_none_when_not_found(self):
        """Test returns None when prompts directory doesn't exist."""
        # Arrange
        with patch(
            "cortex.tools.synapse.prompts_paths.Path.cwd", return_value=Path("/tmp")
        ):
            with patch(
                "cortex.tools.synapse.prompts_paths._paths_anchor",
                return_value=Path("/tmp") / "nonexistent" / "file.py",
            ):
                # Act
                result = synapse_prompts.get_synapse_prompts_path()

                # Assert
                assert result is None

    def test_finds_prompts_via_explicit_project_root(
        self, temp_project_root: Path, prompts_dir: Path
    ) -> None:
        """Explicit project_root skips CWD walk and returns correct path."""
        # CWD is deliberately wrong
        with patch(
            "cortex.tools.synapse.prompts_paths.Path.cwd",
            return_value=Path("/nonexistent_xyz"),
        ):
            result = synapse_prompts.get_prompts_paths(temp_project_root)

        assert prompts_dir in result

    def test_explicit_project_root_returns_empty_when_no_cortex(
        self, tmp_path: Path
    ) -> None:
        """When .cortex/synapse/prompts does not exist under explicit root, returns []."""
        result = synapse_prompts.get_prompts_paths(tmp_path)
        assert result == []


# ============================================================================
# Tests for _load_prompts_manifest()
# ============================================================================


class TestLoadPromptsManifest:
    """Tests for _load_prompts_manifest()."""

    def test_loads_valid_manifest(self, prompts_dir: Path, sample_manifest: Path):
        """Test loading valid manifest file."""
        # Act
        result = synapse_prompts.load_prompts_manifest(prompts_dir)

        # Assert
        assert result is not None
        assert result["version"] == "1.0"
        assert "categories" in result

    def test_returns_none_when_manifest_missing(self, prompts_dir: Path):
        """Test returns None when manifest file doesn't exist."""
        # Act
        result = synapse_prompts.load_prompts_manifest(prompts_dir)

        # Assert
        assert result is None

    def test_returns_none_on_json_error(self, prompts_dir: Path):
        """Test returns None when manifest has invalid JSON."""
        # Arrange
        manifest_path = prompts_dir / "prompts-manifest.json"
        _ = manifest_path.write_text("invalid json", encoding="utf-8")

        # Act
        result = synapse_prompts.load_prompts_manifest(prompts_dir)

        # Assert
        assert result is None

    def test_returns_none_on_file_read_error(self, prompts_dir: Path):
        """Test returns None when file read fails."""
        # Arrange
        manifest_path = prompts_dir / "prompts-manifest.json"
        _ = manifest_path.write_text('{"valid": "json"}', encoding="utf-8")

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            # Act
            result = synapse_prompts.load_prompts_manifest(prompts_dir)

            # Assert
            assert result is None


# ============================================================================
# Tests for load_prompt_content()
# ============================================================================


class TestLoadPromptContent:
    """Tests for load_prompt_content()."""

    def test_loads_valid_prompt_file(self, prompts_dir: Path, sample_prompt_file: Path):
        """Test loading valid prompt file."""
        # Act
        result = synapse_prompts.load_prompt_content(
            prompts_dir, "general", "test-prompt.md"
        )

        # Assert
        assert result is not None
        assert "# Test Prompt" in result

    def test_returns_none_when_file_missing(self, prompts_dir: Path):
        """Test returns None when prompt file doesn't exist."""
        # Act
        result = synapse_prompts.load_prompt_content(
            prompts_dir, "general", "nonexistent.md"
        )

        # Assert
        assert result is None

    def test_returns_none_on_file_read_error(self, prompts_dir: Path):
        """Test returns None when file read fails."""
        # Arrange
        prompt_file = prompts_dir / "test-prompt.md"
        _ = prompt_file.write_text("content", encoding="utf-8")

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            # Act
            result = synapse_prompts.load_prompt_content(
                prompts_dir, "general", "test-prompt.md"
            )

            # Assert
            assert result is None

    def test_rejects_path_traversal_attempt(self, prompts_dir: Path) -> None:
        """Test rejects path traversal attempts that escape prompts directory."""
        # Act
        result = synapse_prompts.load_prompt_content(
            prompts_dir, "general", "../outside.md"
        )

        # Assert
        assert result is None

    def test_rejects_absolute_path(self, prompts_dir: Path, tmp_path: Path) -> None:
        """Test rejects absolute paths outside of prompts directory."""
        outside_file = tmp_path / "outside.md"
        _ = outside_file.write_text("outside", encoding="utf-8")

        # Act
        result = synapse_prompts.load_prompt_content(
            prompts_dir, "general", str(outside_file)
        )

        # Assert
        assert result is None

    def test_injects_post_prompt_hook_when_missing(self, prompts_dir: Path) -> None:
        """Prompts without hook reference receive an auto-injected hook step."""
        prompt_file = prompts_dir / "workflow.md"
        _ = prompt_file.write_text("# Workflow\n\nRun tasks.", encoding="utf-8")

        result = synapse_prompts.load_prompt_content(
            prompts_dir, "general", "workflow.md"
        )

        assert result is not None
        assert "## Post-Prompt Hook" in result
        assert "post-prompt-hook.md" in result

    def test_does_not_inject_hook_for_analyze_prompt(self, prompts_dir: Path) -> None:
        """analyze.md is excluded from hook auto-injection to prevent recursion."""
        prompt_file = prompts_dir / "analyze.md"
        _ = prompt_file.write_text("# Analyze\n\nAlready special.", encoding="utf-8")

        result = synapse_prompts.load_prompt_content(
            prompts_dir, "general", "analyze.md"
        )

        assert result == "# Analyze\n\nAlready special."

    def test_does_not_duplicate_existing_hook_reference(
        self, prompts_dir: Path
    ) -> None:
        """Prompts already referencing hook keep a single hook section."""
        prompt_file = prompts_dir / "existing-hook.md"
        _ = prompt_file.write_text(
            (
                "# Existing Hook\n\n"
                "## Post-Prompt Hook\n\n"
                "Read `.cortex/synapse/prompts/post-prompt-hook.md`.\n"
            ),
            encoding="utf-8",
        )

        result = synapse_prompts.load_prompt_content(
            prompts_dir, "general", "existing-hook.md"
        )

        assert result is not None
        assert result.count("## Post-Prompt Hook") == 1


# ============================================================================
# Tests for create_prompt_function()
# ============================================================================


class TestCreatePromptFunction:
    """Tests for create_prompt_function()."""

    def test_creates_prompt_function(self) -> None:
        """Test creating a prompt function dynamically."""
        # Arrange
        test_name = "test_prompt_func"
        test_content = "Test content"
        test_description = "Test description"

        # Clear any existing function
        if test_name in synapse_prompts.__dict__:
            del synapse_prompts.__dict__[test_name]

        # Act
        synapse_prompts.create_prompt_function(
            test_name, test_content, test_description
        )

        # Assert
        assert test_name in synapse_prompts.__dict__
        func = synapse_prompts.__dict__[test_name]
        assert callable(func)
        assert func() == test_content

    def test_stores_content_in_module_dict(self) -> None:
        """Test that content is stored in module-level dict."""
        # Arrange
        test_name = "test_storage"
        test_content = "Stored content"

        # Act
        synapse_prompts.create_prompt_function(test_name, test_content, "desc")

        # Assert
        assert "_prompt_contents" in synapse_prompts.__dict__
        assert synapse_prompts.__dict__["_prompt_contents"][test_name] == test_content

    def test_create_prompt_function_with_icon_emoji(self) -> None:
        """create_prompt_function with icon_emoji creates working function."""
        test_name = "test_icon_prompt"
        test_content = "Content with icon"
        if test_name in synapse_prompts.__dict__:
            del synapse_prompts.__dict__[test_name]
        synapse_prompts.create_prompt_function(
            test_name, test_content, "Desc", icon_emoji="🔗"
        )
        assert test_name in synapse_prompts.__dict__
        assert synapse_prompts.__dict__[test_name]() == test_content


# ============================================================================
# Tests for process_prompt_info()
# ============================================================================


class TestProcessPromptInfo:
    """Tests for process_prompt_info()."""

    def test_processes_valid_prompt_info(
        self, prompts_dir: Path, sample_prompt_file: Path
    ) -> None:
        """Test processing valid prompt info."""
        # Arrange
        prompt_info = {
            "file": "test-prompt.md",
            "name": "test_prompt",
            "description": "Test description",
        }

        # Act
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), prompts_dir, "general"
        )

        # Assert
        assert result == 1

    def test_processes_prompt_info_with_icon(
        self, prompts_dir: Path, sample_prompt_file: Path
    ) -> None:
        """Test processing prompt info with icon field uses that icon."""
        prompt_info = {
            "file": "test-prompt.md",
            "name": "test_with_icon",
            "description": "Prompt with icon",
            "icon": "🔧",
        }
        # Clear if previously registered
        if "test_with_icon" in synapse_prompts.__dict__:
            del synapse_prompts.__dict__["test_with_icon"]
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), prompts_dir, "general"
        )
        assert result == 1
        assert "test_with_icon" in synapse_prompts.__dict__
        prompt_text = synapse_prompts.__dict__["test_with_icon"]()
        assert "# Test Prompt\n\nThis is a test prompt." in prompt_text
        assert "post-prompt-hook.md" in prompt_text

    def test_returns_zero_for_init_wiki_deferred_registration(
        self, tmp_path: Path
    ) -> None:
        """init-wiki is registered lazily when the wiki scaffold is empty — not via manifest."""
        pdir = tmp_path / "prompts"
        pdir.mkdir()
        _ = (pdir / "init-wiki.md").write_text("# Init Wiki\n", encoding="utf-8")
        prompt_info = {
            "file": "init-wiki.md",
            "name": "Init Wiki",
            "description": "Seed wiki",
        }
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), pdir, "general"
        )
        assert result == 0
        assert "init_wiki" not in synapse_prompts.__dict__

    def test_returns_zero_when_filename_missing(self, prompts_dir: Path):
        """Test returns 0 when filename is missing."""
        # Arrange
        prompt_info = {"name": "test", "description": "desc"}

        # Act
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), prompts_dir, "general"
        )

        # Assert
        assert result == 0

    def test_returns_zero_when_filename_not_string(self, prompts_dir: Path):
        """Test returns 0 when filename is not a string."""
        # Arrange
        prompt_info = {"file": 123, "name": "test"}

        # Act
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), prompts_dir, "general"
        )

        # Assert
        assert result == 0

    def test_returns_zero_when_prompt_name_not_string(self, prompts_dir: Path):
        """Test returns 0 when prompt name is not a string."""
        # Arrange
        prompt_info = {"file": "test.md", "name": 123}

        # Act
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), prompts_dir, "general"
        )

        # Assert
        assert result == 0

    def test_returns_zero_when_content_missing(self, prompts_dir: Path):
        """Test returns 0 when prompt content file doesn't exist."""
        # Arrange
        prompt_info = {
            "file": "nonexistent.md",
            "name": "test",
            "description": "desc",
        }

        # Act
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), prompts_dir, "general"
        )

        # Assert
        assert result == 0

    def test_skips_internal_prompt(
        self, prompts_dir: Path, sample_prompt_file: Path
    ) -> None:
        """Entries with internal=True are not published to the MCP command picker."""
        # Arrange
        prompt_info = {
            "file": "test-prompt.md",
            "name": "test_internal",
            "description": "Should not be published",
            "internal": True,
        }

        # Act
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), prompts_dir, "general"
        )

        # Assert
        assert result == 0
        assert "test_internal" not in synapse_prompts.__dict__

    def test_handles_exception_during_registration(
        self, prompts_dir: Path, sample_prompt_file: Path
    ):
        """Test handles exception during function creation."""
        # Arrange
        prompt_info = {
            "file": "test-prompt.md",
            "name": "test",
            "description": "desc",
        }

        with patch(
            "cortex.tools.synapse.prompts.create_prompt_function",
            side_effect=Exception("Registration failed"),
        ):
            # Act
            result = synapse_prompts.process_prompt_info(
                cast(ModelDict, prompt_info), prompts_dir, "general"
            )

            # Assert
            assert result == 0


# ============================================================================
# Tests for log_registration_summary()
# ============================================================================


class TestLogRegistrationSummary:
    """Tests for log_registration_summary()."""

    def test_logs_when_count_greater_than_zero(self):
        """Test logs summary when registered_count > 0."""
        # Arrange
        with patch("cortex.core.logging_config.logger") as mock_logger:
            # Act
            synapse_prompts.log_registration_summary(5)

            # Assert
            mock_logger.info.assert_called_once()
            assert "5" in mock_logger.info.call_args[0][0]

    def test_logs_debug_with_function_names(self):
        """Test logs debug message with registered function names."""
        # Arrange
        # Create a test function that matches the pattern
        test_func_name = "commit_test"
        synapse_prompts.__dict__[test_func_name] = lambda: "test"

        with patch("cortex.core.logging_config.logger") as mock_logger:
            # Act
            synapse_prompts.log_registration_summary(1)

            # Assert
            mock_logger.debug.assert_called_once()

        # Cleanup
        if test_func_name in synapse_prompts.__dict__:
            del synapse_prompts.__dict__[test_func_name]

    def test_does_not_log_when_count_zero(self):
        """Test does not log when registered_count is 0."""
        # Arrange
        with patch("cortex.core.logging_config.logger") as mock_logger:
            # Act
            synapse_prompts.log_registration_summary(0)

            # Assert
            mock_logger.info.assert_not_called()


# ============================================================================
# Tests for register_synapse_prompts()
# ============================================================================


class TestRegisterSynapsePrompts:
    """Tests for register_synapse_prompts()."""

    def test_registers_prompts_successfully(
        self, temp_project_root: Path, sample_manifest: Path, sample_prompt_file: Path
    ):
        """Test successfully registering prompts."""
        # Arrange
        prompts_dir = (
            get_cortex_path(temp_project_root, CortexResourceType.SYNAPSE) / "prompts"
        )
        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[prompts_dir],
        ):
            # Clear any existing registrations
            for key in list(synapse_prompts.__dict__.keys()):
                if key.startswith("test_prompt"):
                    del synapse_prompts.__dict__[key]

            # Act
            synapse_prompts.register_synapse_prompts()

            # Assert - function should be registered
            # Note: This test verifies the function runs without error
            # Actual registration happens at import time

    def test_handles_missing_prompts_path(self):
        """Test handles case when prompts path doesn't exist."""
        # Arrange
        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[],
        ):
            # Act & Assert - should not raise
            synapse_prompts.register_synapse_prompts()

    def test_handles_missing_manifest(self, temp_project_root: Path, prompts_dir: Path):
        """Test handles case when manifest doesn't exist."""
        # Arrange
        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[prompts_dir],
        ):
            with patch(
                "cortex.tools.synapse.prompts_paths.load_prompts_manifest",
                return_value=None,
            ):
                # Act & Assert - should not raise
                synapse_prompts.register_synapse_prompts()

    def test_handles_invalid_categories(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test handles case when categories is not a dict."""
        # Arrange
        manifest = MagicMock(
            model_dump=MagicMock(
                return_value={"version": "1.0", "categories": "not a dict"}
            )
        )
        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[prompts_dir],
        ):
            with patch(
                "cortex.tools.synapse.prompts_paths.load_prompts_manifest",
                return_value=manifest,
            ):
                # Act & Assert - should not raise
                synapse_prompts.register_synapse_prompts()

    def test_handles_invalid_category_info(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test handles case when category_info is not a dict."""
        # Arrange
        manifest = MagicMock(
            model_dump=MagicMock(
                return_value={
                    "version": "1.0",
                    "categories": {"general": "not a dict"},
                }
            )
        )
        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[prompts_dir],
        ):
            with patch(
                "cortex.tools.synapse.prompts_paths.load_prompts_manifest",
                return_value=manifest,
            ):
                # Act & Assert - should not raise
                synapse_prompts.register_synapse_prompts()

    def test_handles_invalid_prompts_list(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test handles case when prompts is not a list."""
        # Arrange
        manifest = MagicMock(
            model_dump=MagicMock(
                return_value={
                    "version": "1.0",
                    "categories": {"general": {"prompts": "not a list"}},
                }
            )
        )
        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[prompts_dir],
        ):
            with patch(
                "cortex.tools.synapse.prompts_paths.load_prompts_manifest",
                return_value=manifest,
            ):
                # Act & Assert - should not raise
                synapse_prompts.register_synapse_prompts()

    def test_handles_non_dict_prompt_info(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test handles case when prompt_info is not a dict."""
        # Arrange
        manifest = MagicMock(
            model_dump=MagicMock(
                return_value={
                    "version": "1.0",
                    "categories": {"general": {"prompts": ["not a dict"]}},
                }
            )
        )
        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[prompts_dir],
        ):
            with patch(
                "cortex.tools.synapse.prompts_paths.load_prompts_manifest",
                return_value=manifest,
            ):
                # Act & Assert - should not raise
                synapse_prompts.register_synapse_prompts()

    def test_processes_prompt_with_default_name(
        self, prompts_dir: Path, sample_prompt_file: Path
    ):
        """Test processing prompt info with default name from filename."""
        # Arrange
        prompt_info = {"file": "test-prompt.md", "description": "Test"}

        # Act
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), prompts_dir, "general"
        )

        # Assert
        assert result == 1

    def test_processes_prompt_with_non_string_description(
        self, prompts_dir: Path, sample_prompt_file: Path
    ):
        """Test processing prompt info with non-string description."""
        # Arrange
        prompt_info = {
            "file": "test-prompt.md",
            "name": "test",
            "description": 123,
        }

        # Act
        result = synapse_prompts.process_prompt_info(
            cast(ModelDict, prompt_info), prompts_dir, "general"
        )

        # Assert
        assert result == 1

    def test_creates_prompt_when_dict_already_exists(self):
        """Test creating prompt function when _prompt_contents already exists."""
        # Arrange
        test_name = "test_existing_dict"
        test_content = "Content"
        synapse_prompts.__dict__["_prompt_contents"] = {}

        # Act
        synapse_prompts.create_prompt_function(test_name, test_content, "desc")

        # Assert
        assert synapse_prompts.__dict__["_prompt_contents"][test_name] == test_content

    def _write_two_prompt_manifest(self, prompts_dir: Path) -> None:
        """Write a two-prompt manifest and matching .md files into prompts_dir."""
        manifest_data = {
            "version": "1.0",
            "categories": {
                "general": {
                    "prompts": [
                        {
                            "file": "prompt1.md",
                            "name": "prompt1",
                            "description": "First prompt",
                        },
                        {
                            "file": "prompt2.md",
                            "name": "prompt2",
                            "description": "Second prompt",
                        },
                    ]
                }
            },
        }
        _ = (prompts_dir / "prompts-manifest.json").write_text(
            json.dumps(manifest_data), encoding="utf-8"
        )
        _ = (prompts_dir / "prompt1.md").write_text("Content 1", encoding="utf-8")
        _ = (prompts_dir / "prompt2.md").write_text("Content 2", encoding="utf-8")

    def test_registers_multiple_prompts(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test registering multiple prompts from manifest."""
        # Arrange
        self._write_two_prompt_manifest(prompts_dir)

        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[prompts_dir],
        ):
            # Clear existing registrations
            for key in list(synapse_prompts.__dict__.keys()):
                if key in ["prompt1", "prompt2"]:
                    del synapse_prompts.__dict__[key]

            # Act
            synapse_prompts.register_synapse_prompts()

            # Assert - functions should be registered
            # Note: This verifies the registration flow completes


# ============================================================================
# Additional coverage: both-roots preference, load_prompt_content edge cases,
# prompts_registration fallback paths, register_synapse_prompts_for_facade
# ============================================================================


class TestGetSynapsePromptsPathBothRoots:
    """get_synapse_prompts_path prefers synapse root when both roots exist."""

    def test_prefers_synapse_prompts_over_project_prompts(
        self, temp_project_root: Path, prompts_dir: Path
    ) -> None:
        """When both .cortex/synapse/prompts and .cortex/prompts exist,
        get_synapse_prompts_path returns the synapse-shaped one."""
        from cortex.core.path_resolver import CortexResourceType, get_cortex_path

        # Create project-specific prompts directory alongside synapse prompts
        project_prompts = (
            get_cortex_path(temp_project_root, CortexResourceType.CORTEX_DIR)
            / "prompts"
        )
        project_prompts.mkdir(parents=True, exist_ok=True)

        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[project_prompts, prompts_dir],
        ):
            result = synapse_prompts.get_synapse_prompts_path()

        assert result == prompts_dir

    def test_falls_back_to_first_path_when_no_synapse_shaped_root(
        self, temp_project_root: Path
    ) -> None:
        """Falls back to paths[0] when no synapse-shaped entry exists."""
        from cortex.core.path_resolver import CortexResourceType, get_cortex_path

        project_prompts = (
            get_cortex_path(temp_project_root, CortexResourceType.CORTEX_DIR)
            / "prompts"
        )
        project_prompts.mkdir(parents=True, exist_ok=True)
        other_prompts = temp_project_root / "other" / "prompts"
        other_prompts.mkdir(parents=True)

        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[project_prompts, other_prompts],
        ):
            result = synapse_prompts.get_synapse_prompts_path()

        assert result == project_prompts


class TestLoadPromptContentEdgeCases:
    """Additional edge cases for load_prompt_content."""

    def test_returns_none_when_resolve_raises_oserror(self, prompts_dir: Path) -> None:
        """Returns None when candidate.resolve() raises OSError (lines 97-98).

        The first call to .resolve() on prompts_path must succeed (to get
        base_dir); the second call on the candidate must raise OSError.
        """
        import pathlib

        prompt_file = prompts_dir / "test.md"
        _ = prompt_file.write_text("content", encoding="utf-8")

        original_resolve = pathlib.Path.resolve
        call_count = 0

        def resolve_raise_on_second(self: Path, **kwargs: object) -> Path:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return original_resolve(self, **kwargs)  # type: ignore[arg-type]
            raise OSError("bad path")

        with patch.object(pathlib.Path, "resolve", resolve_raise_on_second):
            result = synapse_prompts.load_prompt_content(
                prompts_dir, "general", "test.md"
            )

        assert result is None

    def test_returns_none_when_relative_to_raises_value_error(
        self, tmp_path: Path
    ) -> None:
        """Returns None when resolved path is outside base_dir (lines 103-104).

        This simulates a symlink pointing outside the prompts directory.
        """
        base = tmp_path / "base"
        base.mkdir()
        outside = tmp_path / "outside.md"
        _ = outside.write_text("secret", encoding="utf-8")

        # Create a symlink inside base pointing outside
        link = base / "link.md"
        link.symlink_to(outside)

        result = synapse_prompts.load_prompt_content(base, "cat", "link.md")
        assert result is None


class TestRegisterSynapsePromptsForFacade:
    """Tests for register_synapse_prompts_for_facade."""

    def test_uses_provided_facade_module(self) -> None:
        """Uses provided facade module instead of default."""
        import types

        fake_facade = types.ModuleType("fake_facade")
        fake_facade.create_prompt_function = synapse_prompts.create_prompt_function  # type: ignore[attr-defined]
        fake_facade.__dict__["_prompt_contents"] = {}

        with patch(
            "cortex.tools.synapse.prompts_paths.get_prompts_paths",
            return_value=[],
        ):
            synapse_prompts.register_synapse_prompts_for_facade(  # type: ignore[reportPrivateImportUsage]
                fake_facade
            )
            # No error — confirms facade dispatch works with explicit arg


class TestRegisterPromptsFromPathEdgeCases:
    """Additional coverage for register_prompts_from_path."""

    def test_returns_zero_when_categories_not_dict(self, prompts_dir: Path) -> None:
        """Returns 0 when manifest categories is not a dict (line 141)."""
        manifest_path = prompts_dir / "prompts-manifest.json"
        _ = manifest_path.write_text(
            '{"version": "1.0", "categories": ["not", "a", "dict"]}',
            encoding="utf-8",
        )
        result = synapse_prompts.register_prompts_from_path(prompts_dir)
        assert result == 0

    def test_returns_zero_when_prompts_not_list(self, prompts_dir: Path) -> None:
        """Returns 0 for category whose prompts field is not a list (line 150)."""
        import json as _json

        manifest_data = {
            "version": "1.0",
            "categories": {"general": {"prompts": "not-a-list"}},
        }
        _ = (prompts_dir / "prompts-manifest.json").write_text(
            _json.dumps(manifest_data), encoding="utf-8"
        )
        result = synapse_prompts.register_prompts_from_path(prompts_dir)
        assert result == 0
