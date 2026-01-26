"""
Tests for prompts_loader.py - Prompts Loader for MCP Memory Bank.

This module tests:
- PromptsLoader initialization
- Manifest loading and parsing
- Category loading
- Prompt file reading
- Error handling for file I/O failures
- Manifest caching behavior
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.rules.prompts_loader import PromptsLoader


class TestPromptsLoaderInitialization:
    """Tests for PromptsLoader initialization."""

    def test_init_with_valid_path(self, tmp_path: Path):
        """Test initialization with valid path."""
        # Arrange
        prompts_path = tmp_path / "prompts"

        # Act
        loader = PromptsLoader(prompts_path)

        # Assert
        assert loader.prompts_path == prompts_path
        assert loader.manifest is None
        assert loader.manifest_cache is None

    def test_init_with_invalid_path(self, tmp_path: Path):
        """Test initialization with non-existent path."""
        # Arrange
        prompts_path = tmp_path / "nonexistent" / "prompts"

        # Act
        loader = PromptsLoader(prompts_path)

        # Assert
        assert loader.prompts_path == prompts_path
        assert loader.manifest is None


class TestLoadManifest:
    """Tests for load_manifest method."""

    @pytest.mark.asyncio
    async def test_load_manifest_success(self, tmp_path: Path):
        """Test loading manifest successfully."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        manifest_path = prompts_path / "prompts-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {
                    "prompts": [
                        {
                            "file": "test.md",
                            "name": "Test",
                            "description": "Test prompt",
                        }
                    ]
                }
            },
        }
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)

        # Act
        result = await loader.load_manifest()

        # Assert
        assert result is not None
        assert loader.manifest is not None
        assert loader.manifest_cache is not None
        assert loader.manifest.version == "1.0"
        assert isinstance(loader.manifest.categories, dict)

    @pytest.mark.asyncio
    async def test_load_manifest_missing_file(self, tmp_path: Path):
        """Test loading manifest when file doesn't exist."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        loader = PromptsLoader(prompts_path)

        # Act
        result = await loader.load_manifest()

        # Assert
        assert result is None
        assert loader.manifest is None
        assert loader.manifest_cache is None

    @pytest.mark.asyncio
    async def test_load_manifest_invalid_json(self, tmp_path: Path):
        """Test loading manifest with invalid JSON."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text("{ invalid json }")

        loader = PromptsLoader(prompts_path)

        # Act
        result = await loader.load_manifest()

        # Assert
        assert result is None
        assert loader.manifest is None

    @pytest.mark.asyncio
    async def test_load_manifest_io_error(self, tmp_path: Path):
        """Test handling IO error during manifest load."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text('{"valid": "json"}')

        loader = PromptsLoader(prompts_path)

        # Mock open_async_text_file to raise IOError
        with patch(
            "cortex.rules.prompts_loader.open_async_text_file",
            side_effect=OSError("Permission denied"),
        ):
            # Act
            result = await loader.load_manifest()

            # Assert
            assert result is None
            assert loader.manifest is None

    @pytest.mark.asyncio
    async def test_load_manifest_not_dict(self, tmp_path: Path):
        """Test loading manifest that is not a dictionary."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text('["not", "a", "dict"]')

        loader = PromptsLoader(prompts_path)

        # Act
        result = await loader.load_manifest()

        # Assert
        assert result is None
        assert loader.manifest is None


class TestGetCategories:
    """Tests for get_categories method."""

    @pytest.mark.asyncio
    async def test_get_categories_with_manifest(self, tmp_path: Path):
        """Test getting categories when manifest is loaded."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        manifest_path = prompts_path / "prompts-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {"prompts": []},
                "general": {"prompts": []},
                "testing": {"prompts": []},
            },
        }
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)
        _ = await loader.load_manifest()

        # Act
        categories = loader.get_categories()

        # Assert
        assert isinstance(categories, list)
        assert len(categories) == 3
        assert "python" in categories
        assert "general" in categories
        assert "testing" in categories

    def test_get_categories_without_manifest(self, tmp_path: Path):
        """Test getting categories when manifest is not loaded."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        loader = PromptsLoader(prompts_path)

        # Act
        categories = loader.get_categories()

        # Assert
        assert categories == []

    @pytest.mark.asyncio
    async def test_get_categories_with_invalid_categories(self, tmp_path: Path):
        """Test getting categories when categories is not a dict."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        manifest_path = prompts_path / "prompts-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": ["not", "a", "dict"],
        }
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)
        _ = await loader.load_manifest()

        # Act
        categories = loader.get_categories()

        # Assert
        assert categories == []


class TestLoadCategory:
    """Tests for load_category method."""

    @pytest.mark.asyncio
    async def test_load_category_success(self, tmp_path: Path):
        """Test loading category successfully."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        python_path = prompts_path / "python"
        python_path.mkdir()

        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {
                    "prompts": [
                        {
                            "file": "test.md",
                            "name": "Test Prompt",
                            "description": "A test prompt",
                            "keywords": ["test", "python"],
                        }
                    ]
                }
            },
        }
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text(json.dumps(manifest_data))

        prompt_file = python_path / "test.md"
        _ = prompt_file.write_text("# Test Prompt\n\nThis is a test prompt.")

        loader = PromptsLoader(prompts_path)

        # Act
        prompts = await loader.load_category("python")

        # Assert
        assert isinstance(prompts, list)
        assert len(prompts) == 1
        prompt = prompts[0]
        assert prompt.category == "python"
        assert prompt.file == "test.md"
        assert prompt.name == "Test Prompt"
        assert isinstance(prompt.content, str) and prompt.content

    @pytest.mark.asyncio
    async def test_load_category_invalid_category(self, tmp_path: Path):
        """Test loading invalid category."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        manifest_path = prompts_path / "prompts-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {"python": {"prompts": []}},
        }
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)
        _ = await loader.load_manifest()

        # Act
        prompts = await loader.load_category("nonexistent")

        # Assert
        assert prompts == []

    @pytest.mark.asyncio
    async def test_load_category_missing_files(self, tmp_path: Path):
        """Test loading category with missing prompt files."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        python_path = prompts_path / "python"
        python_path.mkdir()

        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {
                    "prompts": [
                        {"file": "missing.md", "name": "Missing", "description": ""}
                    ]
                }
            },
        }
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)

        # Act
        prompts = await loader.load_category("python")

        # Assert
        assert prompts == []

    @pytest.mark.asyncio
    async def test_load_category_auto_loads_manifest(self, tmp_path: Path):
        """Test that load_category automatically loads manifest if not loaded."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        python_path = prompts_path / "python"
        python_path.mkdir()

        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {"python": {"prompts": []}},
        }
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)
        assert loader.manifest is None  # Manifest not loaded yet

        # Act
        _ = await loader.load_category("python")

        # Assert
        assert loader.manifest is not None


class TestLoadPrompt:
    """Tests for prompt loading methods."""

    @pytest.mark.asyncio
    async def test_load_prompt_success(self, tmp_path: Path):
        """Test loading a single prompt successfully."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        python_path = prompts_path / "python"
        python_path.mkdir()

        prompt_file = python_path / "test.md"
        prompt_content = "# Test Prompt\n\nThis is test content."
        _ = prompt_file.write_text(prompt_content)

        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {
                    "prompts": [
                        {
                            "file": "test.md",
                            "name": "Test Prompt",
                            "description": "A test",
                            "keywords": ["test"],
                        }
                    ]
                }
            },
        }
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)
        _ = await loader.load_manifest()

        # Act
        prompts = await loader.load_category("python")

        # Assert
        assert len(prompts) == 1
        prompt = prompts[0]
        assert prompt.content == prompt_content
        assert prompt.path == str(prompt_file)
        assert prompt.source == "synapse"

    @pytest.mark.asyncio
    async def test_load_prompt_invalid_name(self, tmp_path: Path):
        """Test loading prompt with invalid file name in manifest."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        python_path = prompts_path / "python"
        python_path.mkdir()

        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {
                    "prompts": [
                        {"file": 123, "name": "Invalid"}  # Invalid: not a string
                    ]
                }
            },
        }
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)

        # Act
        prompts = await loader.load_category("python")

        # Assert
        assert prompts == []

    @pytest.mark.asyncio
    async def test_load_prompt_missing_file(self, tmp_path: Path):
        """Test loading prompt when file doesn't exist."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        python_path = prompts_path / "python"
        python_path.mkdir()

        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {
                    "prompts": [
                        {"file": "nonexistent.md", "name": "Missing", "description": ""}
                    ]
                }
            },
        }
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)

        # Act
        prompts = await loader.load_category("python")

        # Assert
        assert prompts == []


class TestManifestCaching:
    """Tests for manifest caching behavior."""

    @pytest.mark.asyncio
    async def test_manifest_caching(self, tmp_path: Path):
        """Test that manifest is cached after loading."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        manifest_path = prompts_path / "prompts-manifest.json"
        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {"python": {"prompts": []}},
        }
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)

        # Act
        result1 = await loader.load_manifest()
        result2 = await loader.load_manifest()

        # Assert
        assert result1 is not None
        assert result2 is not None
        assert loader.manifest is not None
        assert loader.manifest_cache is not None
        # Both results should be the same (cached)
        assert result1 == result2


class TestSaveManifest:
    """Tests for save_manifest method."""

    @pytest.mark.asyncio
    async def test_save_manifest_success(self, tmp_path: Path):
        """Test saving manifest successfully."""
        from cortex.rules.models import PromptsManifestModel

        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        manifest_path = prompts_path / "prompts-manifest.json"

        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {"python": {"prompts": []}},
        }

        loader = PromptsLoader(prompts_path)

        # Act
        manifest_model = PromptsManifestModel.model_validate(manifest_data)
        await loader.save_manifest(manifest_model)

        # Assert
        assert loader.manifest is not None
        assert loader.manifest.version == "1.0"
        assert loader.manifest_cache is not None
        assert manifest_path.exists()
        saved_data = json.loads(manifest_path.read_text())
        assert saved_data["version"] == "1.0"


class TestCreatePromptFile:
    """Tests for create_prompt_file method."""

    @pytest.mark.asyncio
    async def test_create_prompt_file_success(self, tmp_path: Path):
        """Test creating a new prompt file."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        loader = PromptsLoader(prompts_path)

        # Act
        file_path = await loader.create_prompt_file(
            category="python", filename="new-prompt.md", content="# New Prompt\nContent"
        )

        # Assert
        assert file_path.exists()
        assert file_path.name == "new-prompt.md"
        assert file_path.parent.name == "python"
        assert file_path.read_text() == "# New Prompt\nContent"


class TestUpdatePromptFile:
    """Tests for update_prompt_file method."""

    @pytest.mark.asyncio
    async def test_update_prompt_file_success(self, tmp_path: Path):
        """Test updating an existing prompt file."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        python_path = prompts_path / "python"
        python_path.mkdir()
        prompt_file = python_path / "test.md"
        _ = prompt_file.write_text("# Old Content")

        loader = PromptsLoader(prompts_path)

        # Act
        await loader.update_prompt_file(
            prompt_path=prompt_file, content="# New Content"
        )

        # Assert
        assert prompt_file.read_text() == "# New Content"


class TestGetAllPrompts:
    """Tests for get_all_prompts method."""

    @pytest.mark.asyncio
    async def test_get_all_prompts_success(self, tmp_path: Path):
        """Test getting all prompts from all categories."""
        # Arrange
        prompts_path = tmp_path / "prompts"
        prompts_path.mkdir()
        python_path = prompts_path / "python"
        python_path.mkdir()
        general_path = prompts_path / "general"
        general_path.mkdir()

        # Create prompt files
        _ = (python_path / "test1.md").write_text("# Python Prompt 1")
        _ = (general_path / "test2.md").write_text("# General Prompt 1")

        manifest_data: dict[str, object] = {
            "version": "1.0",
            "categories": {
                "python": {
                    "prompts": [
                        {"file": "test1.md", "name": "Python Test", "description": ""}
                    ]
                },
                "general": {
                    "prompts": [
                        {"file": "test2.md", "name": "General Test", "description": ""}
                    ]
                },
            },
        }
        manifest_path = prompts_path / "prompts-manifest.json"
        _ = manifest_path.write_text(json.dumps(manifest_data))

        loader = PromptsLoader(prompts_path)

        # Act
        all_prompts = await loader.get_all_prompts()

        # Assert
        assert isinstance(all_prompts, list)
        assert len(all_prompts) == 2
        categories = {prompt.category for prompt in all_prompts}
        assert "python" in categories
        assert "general" in categories
