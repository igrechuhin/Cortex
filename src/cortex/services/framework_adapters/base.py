"""Base Framework Adapter

Abstract base class for language-specific framework adapters.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class CheckResult(BaseModel):
    """Result of a single check operation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    check_type: str = Field(description="Type of check performed")
    success: bool = Field(description="Whether check succeeded")
    output: str = Field(description="Check output")
    errors: list[str] = Field(default_factory=list, description="List of errors")
    warnings: list[str] = Field(default_factory=list, description="List of warnings")
    files_modified: list[str] = Field(
        default_factory=list, description="List of modified files"
    )


class TestResult(BaseModel):
    """Test execution result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    success: bool = Field(description="Whether tests passed")
    tests_run: int = Field(ge=0, description="Number of tests run")
    tests_passed: int = Field(ge=0, description="Number of tests passed")
    tests_failed: int = Field(ge=0, description="Number of tests failed")
    pass_rate: float = Field(ge=0.0, le=1.0, description="Pass rate (0-1)")
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
