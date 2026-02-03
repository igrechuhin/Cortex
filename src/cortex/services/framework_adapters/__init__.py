"""Framework Adapters Package

Language-specific adapters for test execution, error fixing, and code quality checks.
Detection is delegated to adapters via detect_language_at_path() so pre-commit
logic stays language-agnostic.
"""

from cortex.services.framework_adapters.detection import detect_language_at_path

__all__: list[str] = ["detect_language_at_path"]
