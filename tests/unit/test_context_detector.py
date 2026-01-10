"""Unit tests for ContextDetector - Phase 6"""

from pathlib import Path
from typing import cast

from cortex.rules.context_detector import ContextDetector


class TestContextDetectorInitialization:
    """Test ContextDetector initialization."""

    def test_initialization_sets_up_keywords(self):
        """Test detector initializes with keyword mappings."""
        # Arrange & Act
        detector = ContextDetector()

        # Assert
        assert "python" in detector.language_keywords
        assert "swift" in detector.language_keywords
        assert "javascript" in detector.language_keywords
        assert "django" in detector.framework_keywords
        assert ".py" in detector.extension_map
        assert detector.extension_map[".py"] == "python"


class TestDetectContext:
    """Test context detection from task descriptions and files."""

    def test_detect_python_from_description(self):
        """Test detecting Python language from task description."""
        # Arrange
        detector = ContextDetector()
        task = "Write Python tests for the authentication module"

        # Act
        context = detector.detect_context(task)

        # Assert
        languages = context.get("detected_languages")
        assert isinstance(languages, list)
        assert "python" in languages
        categories = context.get("categories_to_load")
        assert isinstance(categories, list)
        assert "python" in categories
        assert "generic" in categories

    def test_detect_swift_from_description(self):
        """Test detecting Swift language from task description."""
        # Arrange
        detector = ContextDetector()
        task = "Implement SwiftUI view for user profile"

        # Act
        context = detector.detect_context(task)

        # Assert
        languages = context.get("detected_languages")
        assert isinstance(languages, list)
        assert "swift" in languages
        frameworks = context.get("detected_frameworks")
        assert isinstance(frameworks, list)
        assert "swiftui" in frameworks

    def test_detect_framework_from_description(self):
        """Test detecting framework from task description."""
        # Arrange
        detector = ContextDetector()
        task = "Create Django REST API endpoint"

        # Act
        context = detector.detect_context(task)

        # Assert
        frameworks = context.get("detected_frameworks")
        assert isinstance(frameworks, list)
        assert "django" in frameworks
        categories = context.get("categories_to_load")
        assert isinstance(categories, list)
        assert "django" in categories

    def test_detect_multiple_languages(self):
        """Test detecting multiple languages."""
        # Arrange
        detector = ContextDetector()
        task = "Build React frontend with Python backend API"

        # Act
        context = detector.detect_context(task)

        # Assert
        languages = context.get("detected_languages")
        assert isinstance(languages, list)
        assert "python" in languages
        assert "javascript" in languages

    def test_detect_from_file_extensions(self):
        """Test detecting language from file extensions."""
        # Arrange
        detector = ContextDetector()
        files = [
            Path("src/main.py"),
            Path("src/utils.py"),
            Path("tests/test_main.py"),
        ]

        # Act
        context = detector.detect_context("", project_files=files)

        # Assert
        languages = context.get("detected_languages")
        assert isinstance(languages, list)
        assert "python" in languages

    def test_detect_mixed_file_types(self):
        """Test detecting multiple languages from mixed files."""
        # Arrange
        detector = ContextDetector()
        files = [
            Path("src/main.swift"),
            Path("src/api.py"),
            Path("frontend/app.js"),
        ]

        # Act
        context = detector.detect_context("", project_files=files)

        # Assert
        languages = context.get("detected_languages")
        assert isinstance(languages, list)
        assert "swift" in languages
        assert "python" in languages
        assert "javascript" in languages

    def test_always_includes_generic_category(self):
        """Test that generic category is always included."""
        # Arrange
        detector = ContextDetector()

        # Act
        context = detector.detect_context("")

        # Assert
        categories = context.get("categories_to_load")
        assert isinstance(categories, list)
        assert "generic" in categories


class TestDetectTaskType:
    """Test task type detection."""

    def test_detect_testing_task(self):
        """Test detecting testing task type."""
        # Arrange
        detector = ContextDetector()
        task = "Write unit tests for authentication service"

        # Act
        context = detector.detect_context(task)

        # Assert
        task_type = context.get("task_type")
        assert task_type == "testing"
        categories = context.get("categories_to_load")
        assert isinstance(categories, list)
        assert "testing" in categories

    def test_detect_authentication_task(self):
        """Test detecting authentication task type."""
        # Arrange
        detector = ContextDetector()
        task = "Implement OAuth authentication flow"

        # Act
        context = detector.detect_context(task)

        # Assert
        task_type = context.get("task_type")
        assert task_type == "authentication"

    def test_detect_api_task(self):
        """Test detecting API task type."""
        # Arrange
        detector = ContextDetector()
        task = "Create REST API endpoint for user data"

        # Act
        context = detector.detect_context(task)

        # Assert
        task_type = context.get("task_type")
        assert task_type == "api"

    def test_detect_ui_task(self):
        """Test detecting UI task type."""
        # Arrange
        detector = ContextDetector()
        task = "Design user interface for settings page"

        # Act
        context = detector.detect_context(task)

        # Assert
        task_type = context.get("task_type")
        assert task_type == "ui"

    def test_detect_database_task(self):
        """Test detecting database task type."""
        # Arrange
        detector = ContextDetector()
        task = "Create database migration for users table"

        # Act
        context = detector.detect_context(task)

        # Assert
        task_type = context.get("task_type")
        assert task_type == "database"


class TestGetRelevantCategories:
    """Test getting relevant categories from context."""

    def test_get_categories_for_python_context(self):
        """Test getting categories for Python context."""
        # Arrange
        detector = ContextDetector()
        context: dict[str, object] = {
            "detected_languages": ["python"],
            "detected_frameworks": ["django"],
            "task_type": "testing",
            "categories_to_load": ["generic", "python", "django", "testing"],
        }

        # Act
        categories = detector.get_relevant_categories(context)

        # Assert
        assert "generic" in categories
        assert "python" in categories
        assert "django" in categories
        assert "testing" in categories

    def test_get_categories_for_swift_context(self):
        """Test getting categories for Swift context."""
        # Arrange
        detector = ContextDetector()
        context: dict[str, object] = {
            "detected_languages": ["swift"],
            "detected_frameworks": ["swiftui"],
            "task_type": "ui",
            "categories_to_load": ["generic", "swift", "swiftui", "ui"],
        }

        # Act
        categories = detector.get_relevant_categories(context)

        # Assert
        assert "generic" in categories
        assert "swift" in categories
        assert "swiftui" in categories
        assert "ui" in categories

    def test_get_categories_always_includes_generic(self):
        """Test that generic is always in categories."""
        # Arrange
        detector = ContextDetector()
        context: dict[str, object] = {
            "detected_languages": [],
            "detected_frameworks": [],
            "task_type": None,
            "categories_to_load": ["generic"],
        }

        # Act
        categories = detector.get_relevant_categories(context)

        # Assert
        assert "generic" in categories


class TestPrivateHelperMethods:
    """Test private helper methods."""

    def test_detect_from_description_case_insensitive(self):
        """Test detection is case insensitive."""
        # Arrange
        detector = ContextDetector()

        # Act
        context1 = detector.detect_context("Python testing")
        context2 = detector.detect_context("PYTHON TESTING")
        context3 = detector.detect_context("python testing")

        # Assert
        languages1 = context1.get("detected_languages")
        languages2 = context2.get("detected_languages")
        languages3 = context3.get("detected_languages")
        assert isinstance(languages1, list)
        assert isinstance(languages2, list)
        assert isinstance(languages3, list)
        assert "python" in languages1
        assert "python" in languages2
        assert "python" in languages3

    def test_detect_from_files_handles_empty_list(self):
        """Test file detection handles empty list."""
        # Arrange
        detector = ContextDetector()

        # Act
        context = detector.detect_context("Test task", project_files=[])

        # Assert
        languages = context.get("detected_languages")
        assert isinstance(languages, list)
        languages_list = cast(list[str], languages)
        assert len(languages_list) == 0

    def test_detect_from_files_ignores_unknown_extensions(self):
        """Test file detection ignores unknown extensions."""
        # Arrange
        detector = ContextDetector()
        files = [Path("README.md"), Path("config.json"), Path("data.txt")]

        # Act
        context = detector.detect_context("", project_files=files)

        # Assert
        languages = context.get("detected_languages")
        assert isinstance(languages, list)
        languages_list = cast(list[str], languages)
        assert len(languages_list) == 0


class TestMultipleSignals:
    """Test context detection with multiple signals."""

    def test_combine_description_and_files(self):
        """Test combining signals from description and files."""
        # Arrange
        detector = ContextDetector()
        task = "Write React component"
        files = [Path("src/App.tsx"), Path("src/utils.ts")]

        # Act
        context = detector.detect_context(task, project_files=files)

        # Assert
        languages = context.get("detected_languages")
        frameworks = context.get("detected_frameworks")
        assert isinstance(languages, list)
        assert isinstance(frameworks, list)
        assert "javascript" in languages
        assert "react" in frameworks

    def test_framework_and_task_type_combined(self):
        """Test combining framework and task type detection."""
        # Arrange
        detector = ContextDetector()
        task = "Write unit tests for Django API endpoints"

        # Act
        context = detector.detect_context(task)

        # Assert
        frameworks = context.get("detected_frameworks")
        task_type = context.get("task_type")
        categories = context.get("categories_to_load")
        assert isinstance(frameworks, list)
        assert isinstance(categories, list)
        assert "django" in frameworks
        assert task_type == "testing"
        assert "testing" in categories
        assert "django" in categories


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_task_description(self):
        """Test handling empty task description."""
        # Arrange
        detector = ContextDetector()

        # Act
        context = detector.detect_context("")

        # Assert
        categories = context.get("categories_to_load")
        assert isinstance(categories, list)
        assert "generic" in categories

    def test_none_project_files(self):
        """Test handling None project files."""
        # Arrange
        detector = ContextDetector()

        # Act
        context = detector.detect_context("Test task", project_files=None)

        # Assert
        assert "detected_languages" in context
        assert "detected_frameworks" in context
        assert "categories_to_load" in context

    def test_ambiguous_keywords(self):
        """Test handling ambiguous keywords."""
        # Arrange
        detector = ContextDetector()
        task = "Go to the store and get Python books about Java programming"

        # Act
        context = detector.detect_context(task)

        # Assert
        languages = context.get("detected_languages")
        assert isinstance(languages, list)
        # Should detect python, go, and java
        assert "python" in languages
        assert "go" in languages
        assert "java" in languages
