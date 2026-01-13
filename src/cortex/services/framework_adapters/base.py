"""Base Framework Adapter

Abstract base class for language-specific framework adapters.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict


class CheckResult(TypedDict):
    """Result of a single check operation."""

    check_type: str
    success: bool
    output: str
    errors: list[str]
    warnings: list[str]
    files_modified: list[str]


class TestResult(TypedDict):
    """Test execution result."""

    success: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    pass_rate: float
    coverage: float | None
    output: str
    errors: list[str]


class FrameworkAdapter(ABC):
    """Abstract base class for framework adapters."""

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize adapter with project root.

        Args:
            project_root: Path to project root directory.
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()

    @abstractmethod
    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
    ) -> TestResult:
        """Run test suite.

        Args:
            timeout: Maximum time in seconds for test execution.
            coverage_threshold: Minimum coverage percentage required.
            max_failures: Maximum number of failures before stopping.

        Returns:
            TestResult with test execution details.
        """
        raise NotImplementedError

    @abstractmethod
    def fix_errors(
        self,
        error_types: Sequence[str] | None = None,
        auto_fix: bool = True,
        strict_mode: bool = False,
    ) -> CheckResult:
        """Fix errors in codebase.

        Args:
            error_types: Types of errors to fix (e.g., ['formatting', 'linting']).
            auto_fix: Whether to automatically fix errors.
            strict_mode: Whether to treat warnings as errors.

        Returns:
            CheckResult with fix operation details.
        """
        raise NotImplementedError

    @abstractmethod
    def format_code(self) -> CheckResult:
        """Format codebase.

        Returns:
            CheckResult with formatting operation details.
        """
        raise NotImplementedError

    @abstractmethod
    def type_check(self) -> CheckResult:
        """Run type checker.

        Returns:
            CheckResult with type checking details.
        """
        raise NotImplementedError

    @abstractmethod
    def lint_code(self) -> CheckResult:
        """Run linter.

        Returns:
            CheckResult with linting details.
        """
        raise NotImplementedError
