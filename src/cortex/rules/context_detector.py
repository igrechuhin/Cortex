"""
Context Detection for Shared Rules.

This module provides context detection logic for intelligent rule loading
based on task descriptions and project files.
"""

from pathlib import Path
from typing import cast

from cortex.core.models import ModelDict
from cortex.rules.models import DetectedContext


class ContextDetector:
    """
    Detect context for intelligent rule loading.

    Features:
    - Language detection from task descriptions and file extensions
    - Framework detection from keywords
    - Task type classification
    - Category recommendations
    """

    def __init__(self):
        """Initialize context detector."""
        self.language_keywords = _get_language_keywords()
        self.framework_keywords = _get_framework_keywords()
        self.extension_map = _get_extension_map()

    def detect_context(
        self, task_description: str, project_files: list[Path] | None = None
    ) -> DetectedContext:
        """
        Detect context for intelligent rule loading.

        Args:
            task_description: Description of the current task
            project_files: List of project files for extension detection

        Returns:
            Detected context model
        """
        languages, frameworks = self._detect_from_description(task_description)
        if project_files:
            self._detect_from_files(project_files, languages)

        task_type = self._detect_task_type(task_description.lower(), project_files)
        categories_to_load = self._build_categories_to_load(
            languages, frameworks, task_type
        )

        return DetectedContext(
            detected_languages=list(languages),
            detected_frameworks=list(frameworks),
            task_type=task_type,
            categories_to_load=list(categories_to_load),
        )

    def _detect_from_description(
        self, task_description: str
    ) -> tuple[set[str], set[str]]:
        """Detect languages and frameworks from task description."""
        task_lower = task_description.lower()

        # Language detection
        languages_set: set[str] = set()
        for lang, keywords in self.language_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                languages_set.add(lang)

        # Framework detection
        frameworks_set: set[str] = set()
        for framework, keywords in self.framework_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                frameworks_set.add(framework)

        return languages_set, frameworks_set

    def _detect_task_type(
        self, task_lower: str, project_files: list[Path] | None = None
    ) -> str | None:
        """
        Detect task type from description and project files.

        Args:
            task_lower: Lowercase task description
            project_files: Optional list of project files for context

        Returns:
            Task type string or None
        """
        if project_files and self._is_testing_task_from_files(
            task_lower, project_files
        ):
            return "testing"

        if self._is_testing_task_from_keywords(task_lower):
            return "testing"

        return self._detect_task_type_from_keywords(task_lower)

    def _is_testing_task_from_files(
        self, task_lower: str, project_files: list[Path]
    ) -> bool:
        """Check if task is testing-related based on project files."""
        test_file_patterns = ["test_", "_test", ".test.", "spec."]
        has_test_files = any(
            any(pattern in file.name.lower() for pattern in test_file_patterns)
            for file in project_files
        )
        return has_test_files and any(
            word in task_lower for word in ["test", "testing", "pytest", "unittest"]
        )

    def _is_testing_task_from_keywords(self, task_lower: str) -> bool:
        """Check if task is testing-related based on keywords."""
        testing_patterns = [
            "write test",
            "write unit test",
            "write integration test",
            "create test",
            "testing",
            "test for",
            "test the",
            "test a",
            "test an",
        ]
        return any(pattern in task_lower for pattern in testing_patterns)

    def _detect_task_type_from_keywords(self, task_lower: str) -> str | None:
        """Detect task type from keyword matching."""
        task_types = {
            "authentication": ["auth", "authentication", "login", "jwt", "oauth"],
            "api": ["api", "endpoint", "rest", "graphql"],
            "ui": ["ui", "interface", "component", "view"],
            "database": ["database", "db", "sql", "query"],
        }

        for task_type, keywords in task_types.items():
            if any(word in task_lower for word in keywords):
                return task_type

        return None

    def _detect_from_files(
        self, project_files: list[Path], languages: set[str]
    ) -> None:
        """
        Detect languages from project file extensions.

        Args:
            project_files: List of project file paths
            languages: Languages set to update
        """
        for file_path in project_files:
            suffix = file_path.suffix.lower()
            if suffix in self.extension_map:
                languages.add(self.extension_map[suffix])

    def _build_categories_to_load(
        self, languages: set[str], frameworks: set[str], task_type: str | None
    ) -> set[str]:
        """Build categories to load based on detected context."""
        categories: set[str] = {"generic"}
        categories.update(languages)
        categories.update(frameworks)
        if task_type:
            categories.add(task_type)
        return categories

    def get_relevant_categories(
        self, context: DetectedContext | ModelDict
    ) -> list[str]:
        """
        Get relevant rule categories based on detected context.

        Args:
            context: Detected context model or dict from detect_context()

        Returns:
            List of category names to load
        """
        if isinstance(context, DetectedContext):
            categories = set(context.categories_to_load)
            categories.add("generic")
            categories.update(context.detected_languages)
            if context.task_type:
                categories.add(context.task_type)
            return list(categories)

        # Legacy dict support
        categories = set(
            cast(list[str], context.get("categories_to_load", ["generic"]))
        )

        # Always include generic
        categories.add("generic")

        # Add detected languages
        categories.update(cast(list[str], context.get("detected_languages", [])))

        # Add task type if present
        if context.get("task_type"):
            categories.add(cast(str, context["task_type"]))

        return list(categories)


def _get_language_keywords() -> dict[str, list[str]]:
    """Get language keywords mapping.

    Returns:
        Dictionary mapping language names to keyword lists
    """
    return {
        "python": ["python", "django", "flask", "fastapi", "pytest", "py"],
        "swift": ["swift", "swiftui", "ios", "uikit", "combine", "cocoa"],
        "javascript": [
            "javascript",
            "js",
            "react",
            "vue",
            "node",
            "typescript",
            "ts",
        ],
        "rust": ["rust", "cargo", "rustc"],
        "go": ["golang", "go"],
        "java": ["java", "spring", "maven", "gradle"],
        "csharp": ["c#", "csharp", "dotnet", ".net"],
        "cpp": ["c++", "cpp", "cmake"],
    }


def _get_framework_keywords() -> dict[str, list[str]]:
    """Get framework keywords mapping.

    Returns:
        Dictionary mapping framework names to keyword lists
    """
    return {
        "django": ["django"],
        "flask": ["flask"],
        "fastapi": ["fastapi"],
        "swiftui": ["swiftui"],
        "react": ["react"],
        "vue": ["vue"],
        "express": ["express"],
    }


def _get_extension_map() -> dict[str, str]:
    """Get file extension to language mapping.

    Returns:
        Dictionary mapping file extensions to language names
    """
    return {
        ".py": "python",
        ".swift": "swift",
        ".js": "javascript",
        ".ts": "javascript",
        ".jsx": "javascript",
        ".tsx": "javascript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".h": "cpp",
    }
