"""
Tests for resources.py - Templates and guides for MCP Memory Bank.

This module tests:
- TEMPLATES dictionary structure and content
- GUIDES dictionary structure and content
- Template and guide value validation
"""

from cortex.resources import GUIDES, TEMPLATES


class TestTemplatesDictStructure:
    """Tests for TEMPLATES dictionary structure."""

    def test_templates_dict_structure(self):
        """Test that TEMPLATES is a dictionary."""
        # Arrange & Act
        templates = TEMPLATES

        # Assert
        assert isinstance(templates, dict)
        assert len(templates) > 0

    def test_templates_all_keys_present(self):
        """Test that all expected template keys are present."""
        # Arrange
        expected_keys = {
            "memorybankinstructions.md",
            "projectBrief.md",
            "productContext.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "progress.md",
        }

        # Act
        actual_keys = set(TEMPLATES.keys())

        # Assert
        assert actual_keys == expected_keys

    def test_templates_all_values_are_strings(self):
        """Test that all template values are strings."""
        # Arrange & Act
        templates = TEMPLATES

        # Assert
        for key, value in templates.items():
            assert isinstance(value, str), f"Template {key} is not a string"

    def test_templates_all_values_non_empty(self):
        """Test that all template values are non-empty."""
        # Arrange & Act
        templates = TEMPLATES

        # Assert
        for key, value in templates.items():
            assert len(value) > 0, f"Template {key} is empty"
            assert value.strip() != "", f"Template {key} contains only whitespace"


class TestGuidesDictStructure:
    """Tests for GUIDES dictionary structure."""

    def test_guides_dict_structure(self):
        """Test that GUIDES is a dictionary."""
        # Arrange & Act
        guides = GUIDES

        # Assert
        assert isinstance(guides, dict)
        assert len(guides) > 0

    def test_guides_all_keys_present(self):
        """Test that all expected guide keys are present."""
        # Arrange
        expected_keys = {"setup", "usage", "benefits", "structure"}

        # Act
        actual_keys = set(GUIDES.keys())

        # Assert
        assert actual_keys == expected_keys

    def test_guides_all_values_are_strings(self):
        """Test that all guide values are strings."""
        # Arrange & Act
        guides = GUIDES

        # Assert
        for key, value in guides.items():
            assert isinstance(value, str), f"Guide {key} is not a string"

    def test_guides_all_values_non_empty(self):
        """Test that all guide values are non-empty."""
        # Arrange & Act
        guides = GUIDES

        # Assert
        for key, value in guides.items():
            assert len(value) > 0, f"Guide {key} is empty"
            assert value.strip() != "", f"Guide {key} contains only whitespace"
