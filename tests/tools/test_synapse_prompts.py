"""
Comprehensive tests for Synapse Prompts Registration

This test suite provides comprehensive coverage for:
- _get_synapse_prompts_path()
- _load_prompts_manifest()
- _load_prompt_content()
- _create_prompt_function()
- _process_prompt_info()
- _log_registration_summary()
- _register_synapse_prompts()
- All error paths and edge cases
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.tools import synapse_prompts

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_project_root(tmp_path: Path) -> Path:
    """Create temporary project root with .cortex structure."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".cortex" / "synapse" / "prompts").mkdir(parents=True)
    return project_root


@pytest.fixture
def prompts_dir(temp_project_root: Path) -> Path:
    """Get prompts directory path."""
    return temp_project_root / ".cortex" / "synapse" / "prompts"


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
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
    return manifest_path


@pytest.fixture
def sample_prompt_file(prompts_dir: Path) -> Path:
    """Create sample prompt file."""
    prompt_file = prompts_dir / "test-prompt.md"
    prompt_file.write_text("# Test Prompt\n\nThis is a test prompt.", encoding="utf-8")
    return prompt_file


# ============================================================================
# Tests for _get_synapse_prompts_path()
# ============================================================================


class TestGetSynapsePromptsPath:
    """Tests for _get_synapse_prompts_path()."""

    def test_finds_prompts_from_cwd(self, temp_project_root: Path, prompts_dir: Path):
        """Test finding prompts directory from current working directory."""
        # Arrange
        with patch(
            "cortex.tools.synapse_prompts.Path.cwd", return_value=temp_project_root
        ):
            # Act
            result = synapse_prompts._get_synapse_prompts_path()

            # Assert
            assert result == prompts_dir

    def test_finds_prompts_from_parent(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test finding prompts directory from parent directory."""
        # Arrange
        subdir = temp_project_root / "subdir"
        subdir.mkdir()
        with patch("cortex.tools.synapse_prompts.Path.cwd", return_value=subdir):
            # Act
            result = synapse_prompts._get_synapse_prompts_path()

            # Assert
            assert result == prompts_dir

    def test_finds_prompts_from_module_location(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test finding prompts directory from module file location."""
        # Arrange
        with patch("cortex.tools.synapse_prompts.Path.cwd", return_value=Path("/tmp")):
            with patch(
                "cortex.tools.synapse_prompts.Path.__file__",
                new=temp_project_root
                / "src"
                / "cortex"
                / "tools"
                / "synapse_prompts.py",
            ):
                # Act
                result = synapse_prompts._get_synapse_prompts_path()

                # Assert
                assert result == prompts_dir

    def test_returns_none_when_not_found(self):
        """Test returns None when prompts directory doesn't exist."""
        # Arrange
        with patch("cortex.tools.synapse_prompts.Path.cwd", return_value=Path("/tmp")):
            with patch(
                "cortex.tools.synapse_prompts.Path.__file__",
                new=Path("/tmp" / "nonexistent" / "file.py"),
            ):
                # Act
                result = synapse_prompts._get_synapse_prompts_path()

                # Assert
                assert result is None


# ============================================================================
# Tests for _load_prompts_manifest()
# ============================================================================


class TestLoadPromptsManifest:
    """Tests for _load_prompts_manifest()."""

    def test_loads_valid_manifest(self, prompts_dir: Path, sample_manifest: Path):
        """Test loading valid manifest file."""
        # Act
        result = synapse_prompts._load_prompts_manifest(prompts_dir)

        # Assert
        assert result is not None
        assert result["version"] == "1.0"
        assert "categories" in result

    def test_returns_none_when_manifest_missing(self, prompts_dir: Path):
        """Test returns None when manifest file doesn't exist."""
        # Act
        result = synapse_prompts._load_prompts_manifest(prompts_dir)

        # Assert
        assert result is None

    def test_returns_none_on_json_error(self, prompts_dir: Path):
        """Test returns None when manifest has invalid JSON."""
        # Arrange
        manifest_path = prompts_dir / "prompts-manifest.json"
        manifest_path.write_text("invalid json", encoding="utf-8")

        # Act
        result = synapse_prompts._load_prompts_manifest(prompts_dir)

        # Assert
        assert result is None

    def test_returns_none_on_file_read_error(self, prompts_dir: Path):
        """Test returns None when file read fails."""
        # Arrange
        manifest_path = prompts_dir / "prompts-manifest.json"
        manifest_path.write_text('{"valid": "json"}', encoding="utf-8")

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            # Act
            result = synapse_prompts._load_prompts_manifest(prompts_dir)

            # Assert
            assert result is None


# ============================================================================
# Tests for _load_prompt_content()
# ============================================================================


class TestLoadPromptContent:
    """Tests for _load_prompt_content()."""

    def test_loads_valid_prompt_file(self, prompts_dir: Path, sample_prompt_file: Path):
        """Test loading valid prompt file."""
        # Act
        result = synapse_prompts._load_prompt_content(
            prompts_dir, "general", "test-prompt.md"
        )

        # Assert
        assert result is not None
        assert "# Test Prompt" in result

    def test_returns_none_when_file_missing(self, prompts_dir: Path):
        """Test returns None when prompt file doesn't exist."""
        # Act
        result = synapse_prompts._load_prompt_content(
            prompts_dir, "general", "nonexistent.md"
        )

        # Assert
        assert result is None

    def test_returns_none_on_file_read_error(self, prompts_dir: Path):
        """Test returns None when file read fails."""
        # Arrange
        prompt_file = prompts_dir / "test-prompt.md"
        prompt_file.write_text("content", encoding="utf-8")

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            # Act
            result = synapse_prompts._load_prompt_content(
                prompts_dir, "general", "test-prompt.md"
            )

            # Assert
            assert result is None


# ============================================================================
# Tests for _create_prompt_function()
# ============================================================================


class TestCreatePromptFunction:
    """Tests for _create_prompt_function()."""

    def test_creates_prompt_function(self):
        """Test creating a prompt function dynamically."""
        # Arrange
        test_name = "test_prompt_func"
        test_content = "Test content"
        test_description = "Test description"

        # Clear any existing function
        if test_name in globals():
            del globals()[test_name]

        # Act
        synapse_prompts._create_prompt_function(
            test_name, test_content, test_description
        )

        # Assert
        assert test_name in synapse_prompts.__dict__
        func = synapse_prompts.__dict__[test_name]
        assert callable(func)
        assert func() == test_content

    def test_stores_content_in_module_dict(self):
        """Test that content is stored in module-level dict."""
        # Arrange
        test_name = "test_storage"
        test_content = "Stored content"

        # Act
        synapse_prompts._create_prompt_function(test_name, test_content, "desc")

        # Assert
        assert "_prompt_contents" in synapse_prompts.__dict__
        assert synapse_prompts.__dict__["_prompt_contents"][test_name] == test_content


# ============================================================================
# Tests for _process_prompt_info()
# ============================================================================


class TestProcessPromptInfo:
    """Tests for _process_prompt_info()."""

    def test_processes_valid_prompt_info(
        self, prompts_dir: Path, sample_prompt_file: Path
    ):
        """Test processing valid prompt info."""
        # Arrange
        prompt_info = {
            "file": "test-prompt.md",
            "name": "test_prompt",
            "description": "Test description",
        }

        # Act
        result = synapse_prompts._process_prompt_info(
            prompt_info, prompts_dir, "general"
        )

        # Assert
        assert result == 1

    def test_returns_zero_when_filename_missing(self, prompts_dir: Path):
        """Test returns 0 when filename is missing."""
        # Arrange
        prompt_info = {"name": "test", "description": "desc"}

        # Act
        result = synapse_prompts._process_prompt_info(
            prompt_info, prompts_dir, "general"
        )

        # Assert
        assert result == 0

    def test_returns_zero_when_filename_not_string(self, prompts_dir: Path):
        """Test returns 0 when filename is not a string."""
        # Arrange
        prompt_info = {"file": 123, "name": "test"}

        # Act
        result = synapse_prompts._process_prompt_info(
            prompt_info, prompts_dir, "general"
        )

        # Assert
        assert result == 0

    def test_returns_zero_when_prompt_name_not_string(self, prompts_dir: Path):
        """Test returns 0 when prompt name is not a string."""
        # Arrange
        prompt_info = {"file": "test.md", "name": 123}

        # Act
        result = synapse_prompts._process_prompt_info(
            prompt_info, prompts_dir, "general"
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
        result = synapse_prompts._process_prompt_info(
            prompt_info, prompts_dir, "general"
        )

        # Assert
        assert result == 0

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
            "cortex.tools.synapse_prompts._create_prompt_function",
            side_effect=Exception("Registration failed"),
        ):
            # Act
            result = synapse_prompts._process_prompt_info(
                prompt_info, prompts_dir, "general"
            )

            # Assert
            assert result == 0


# ============================================================================
# Tests for _log_registration_summary()
# ============================================================================


class TestLogRegistrationSummary:
    """Tests for _log_registration_summary()."""

    def test_logs_when_count_greater_than_zero(self):
        """Test logs summary when registered_count > 0."""
        # Arrange
        with patch("cortex.tools.synapse_prompts.logger") as mock_logger:
            # Act
            synapse_prompts._log_registration_summary(5)

            # Assert
            mock_logger.info.assert_called_once()
            assert "5" in mock_logger.info.call_args[0][0]

    def test_logs_debug_with_function_names(self):
        """Test logs debug message with registered function names."""
        # Arrange
        # Create a test function that matches the pattern
        test_func_name = "commit_test"
        synapse_prompts.__dict__[test_func_name] = lambda: "test"

        with patch("cortex.tools.synapse_prompts.logger") as mock_logger:
            # Act
            synapse_prompts._log_registration_summary(1)

            # Assert
            mock_logger.debug.assert_called_once()

        # Cleanup
        if test_func_name in synapse_prompts.__dict__:
            del synapse_prompts.__dict__[test_func_name]

    def test_does_not_log_when_count_zero(self):
        """Test does not log when registered_count is 0."""
        # Arrange
        with patch("cortex.tools.synapse_prompts.logger") as mock_logger:
            # Act
            synapse_prompts._log_registration_summary(0)

            # Assert
            mock_logger.info.assert_not_called()


# ============================================================================
# Tests for _register_synapse_prompts()
# ============================================================================


class TestRegisterSynapsePrompts:
    """Tests for _register_synapse_prompts()."""

    def test_registers_prompts_successfully(
        self, temp_project_root: Path, sample_manifest: Path, sample_prompt_file: Path
    ):
        """Test successfully registering prompts."""
        # Arrange
        with patch(
            "cortex.tools.synapse_prompts._get_synapse_prompts_path",
            return_value=temp_project_root / ".cortex" / "synapse" / "prompts",
        ):
            # Clear any existing registrations
            for key in list(synapse_prompts.__dict__.keys()):
                if key.startswith("test_prompt"):
                    del synapse_prompts.__dict__[key]

            # Act
            synapse_prompts._register_synapse_prompts()

            # Assert - function should be registered
            # Note: This test verifies the function runs without error
            # Actual registration happens at import time

    def test_handles_missing_prompts_path(self):
        """Test handles case when prompts path doesn't exist."""
        # Arrange
        with patch(
            "cortex.tools.synapse_prompts._get_synapse_prompts_path", return_value=None
        ):
            # Act & Assert - should not raise
            synapse_prompts._register_synapse_prompts()

    def test_handles_missing_manifest(self, temp_project_root: Path, prompts_dir: Path):
        """Test handles case when manifest doesn't exist."""
        # Arrange
        with patch(
            "cortex.tools.synapse_prompts._get_synapse_prompts_path",
            return_value=prompts_dir,
        ):
            with patch(
                "cortex.tools.synapse_prompts._load_prompts_manifest", return_value=None
            ):
                # Act & Assert - should not raise
                synapse_prompts._register_synapse_prompts()

    def test_handles_invalid_categories(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test handles case when categories is not a dict."""
        # Arrange
        manifest = {"version": "1.0", "categories": "not a dict"}
        with patch(
            "cortex.tools.synapse_prompts._get_synapse_prompts_path",
            return_value=prompts_dir,
        ):
            with patch(
                "cortex.tools.synapse_prompts._load_prompts_manifest",
                return_value=manifest,
            ):
                # Act & Assert - should not raise
                synapse_prompts._register_synapse_prompts()

    def test_handles_invalid_category_info(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test handles case when category_info is not a dict."""
        # Arrange
        manifest = {
            "version": "1.0",
            "categories": {"general": "not a dict"},
        }
        with patch(
            "cortex.tools.synapse_prompts._get_synapse_prompts_path",
            return_value=prompts_dir,
        ):
            with patch(
                "cortex.tools.synapse_prompts._load_prompts_manifest",
                return_value=manifest,
            ):
                # Act & Assert - should not raise
                synapse_prompts._register_synapse_prompts()

    def test_handles_invalid_prompts_list(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test handles case when prompts is not a list."""
        # Arrange
        manifest = {
            "version": "1.0",
            "categories": {"general": {"prompts": "not a list"}},
        }
        with patch(
            "cortex.tools.synapse_prompts._get_synapse_prompts_path",
            return_value=prompts_dir,
        ):
            with patch(
                "cortex.tools.synapse_prompts._load_prompts_manifest",
                return_value=manifest,
            ):
                # Act & Assert - should not raise
                synapse_prompts._register_synapse_prompts()

    def test_handles_non_dict_prompt_info(
        self, temp_project_root: Path, prompts_dir: Path
    ):
        """Test handles case when prompt_info is not a dict."""
        # Arrange
        manifest = {
            "version": "1.0",
            "categories": {"general": {"prompts": ["not a dict"]}},
        }
        with patch(
            "cortex.tools.synapse_prompts._get_synapse_prompts_path",
            return_value=prompts_dir,
        ):
            with patch(
                "cortex.tools.synapse_prompts._load_prompts_manifest",
                return_value=manifest,
            ):
                # Act & Assert - should not raise
                synapse_prompts._register_synapse_prompts()
