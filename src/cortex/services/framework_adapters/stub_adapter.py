"""Stub Framework Adapter

Placeholder adapter for languages with registered support but no implementation yet.
Returns consistent "not yet implemented" results for all operations.
"""

from collections.abc import Sequence
from enum import Enum

from .base import CheckResult, FrameworkAdapter, TestResult


class StubAdapterLanguage(str, Enum):
    """Languages that use StubAdapter (must match _ADAPTER_REGISTRY in pre_commit_tools)."""

    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    JAVA = "java"


_NOT_IMPLEMENTED_MSG = "Adapter registered; full implementation not yet available"


class StubAdapter(FrameworkAdapter):
    """Stub adapter for languages without full implementation.

    Used for Java until a language-specific implementation is added.
    Python, TypeScript, JavaScript, Rust, and Go have full adapters. All
    operations return a clear "not yet implemented" result.
    """

    def __init__(
        self,
        project_root: str | None = None,
        language: str | StubAdapterLanguage = "java",
    ) -> None:
        """Initialize stub adapter.

        Args:
            project_root: Path to project root directory.
            language: Language identifier (java).
        """
        super().__init__(project_root)
        if isinstance(language, StubAdapterLanguage):
            self._language: StubAdapterLanguage = language
        else:
            self._language = StubAdapterLanguage(language)

    def _not_implemented_check(self, check_type: str) -> CheckResult:
        """Build a check result for not-implemented operation."""
        msg = f"{self._language.value}: {_NOT_IMPLEMENTED_MSG}"
        return CheckResult(
            check_type=check_type,
            success=False,
            output=msg,
            errors=[msg],
            warnings=[],
            files_modified=[],
        )

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
    ) -> TestResult:
        """Return stub result; tests not implemented for this language."""
        msg = f"{self._language.value}: {_NOT_IMPLEMENTED_MSG}"
        return TestResult(
            success=False,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output=msg,
            errors=[msg],
        )

    def fix_errors(
        self,
        error_types: Sequence[str] | None = None,
        auto_fix: bool = True,
        strict_mode: bool = False,
    ) -> CheckResult:
        """Return stub result; fix_errors not implemented for this language."""
        return self._not_implemented_check("fix_errors")

    def format_code(self) -> CheckResult:
        """Return stub result; format not implemented for this language."""
        return self._not_implemented_check("format")

    def type_check(self) -> CheckResult:
        """Return stub result; type_check not implemented for this language."""
        return self._not_implemented_check("type_check")

    def lint_code(self) -> CheckResult:
        """Return stub result; lint not implemented for this language."""
        return self._not_implemented_check("lint")
