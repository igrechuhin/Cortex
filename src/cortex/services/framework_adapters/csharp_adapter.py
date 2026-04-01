"""C# Framework Adapter

Adapter for C#/.NET projects using dotnet CLI commands.
"""

import subprocess
from collections.abc import Sequence
from pathlib import Path

from cortex.services.language_detector import LanguageInfo

from .base import CheckResult, FrameworkAdapter, ProgressCallback, TestResult


def _no_dotnet_project_result(check_type: str) -> CheckResult:
    """Return CheckResult when no .NET project or solution is present."""
    return CheckResult(
        check_type=check_type,
        success=False,
        output="No .NET project file (.csproj) or solution (.sln) found",
        errors=["No build file found"],
        warnings=[],
        files_modified=[],
    )


class CSharpAdapter(FrameworkAdapter):
    """Adapter for C#/.NET projects."""

    @classmethod
    def detect(cls, path: Path) -> LanguageInfo | None:
        """Detect if path is a C# project via .csproj/.sln markers."""
        has_csproj = any(path.glob("*.csproj"))
        has_sln = any(path.glob("*.sln"))
        if not has_csproj and not has_sln:
            return None
        return LanguageInfo(
            language="csharp",
            test_framework="dotnet test",
            formatter="dotnet format",
            linter=None,
            type_checker="dotnet build",
            build_tool="dotnet",
            confidence=0.9,
        )

    def _has_dotnet_project(self) -> bool:
        root = Path(self.project_root)
        return any(root.glob("*.csproj")) or any(root.glob("*.sln"))

    def _run_dotnet(
        self, args: list[str], timeout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run dotnet command in project root."""
        return subprocess.run(
            ["dotnet", *args],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _run_check(self, check_type: str, args: list[str]) -> CheckResult:
        """Run a dotnet command and return a CheckResult, handling exceptions."""
        if not self._has_dotnet_project():
            return _no_dotnet_project_result(check_type)
        try:
            result = self._run_dotnet(args)
            output = result.stdout + result.stderr
            return CheckResult(
                check_type=check_type,
                success=result.returncode == 0,
                output=output,
                errors=[] if result.returncode == 0 else [f"dotnet {args[0]} failed"],
                warnings=[],
                files_modified=[],
            )
        except Exception as exc:
            return CheckResult(
                check_type=check_type,
                success=False,
                output=str(exc),
                errors=[str(exc)],
                warnings=[],
                files_modified=[],
            )

    def _missing_project_test_result(self) -> TestResult:
        message = "No .NET project file (.csproj) or solution (.sln) found"
        return TestResult(
            success=False,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output=message,
            errors=[message],
        )

    def _run_test_result(self, timeout: int | None) -> TestResult:
        result = self._run_dotnet(["test"], timeout=timeout)
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return TestResult(
            success=success,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output=output,
            errors=[] if success else ["dotnet test failed"],
        )

    def _timeout_test_result(self) -> TestResult:
        return TestResult(
            success=False,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output="Test execution timed out",
            errors=["Test execution exceeded timeout"],
        )

    def _error_test_result(self, exc: Exception) -> TestResult:
        return TestResult(
            success=False,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output=str(exc),
            errors=[str(exc)],
        )

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
        progress_callback: ProgressCallback | None = None,
        include_slow_tests: bool = False,
    ) -> TestResult:
        """Run tests via dotnet test."""
        if not self._has_dotnet_project():
            return self._missing_project_test_result()
        try:
            return self._run_test_result(timeout)
        except subprocess.TimeoutExpired:
            return self._timeout_test_result()
        except Exception as exc:
            return self._error_test_result(exc)

    def fix_errors(
        self,
        error_types: Sequence[str] | None = None,
        auto_fix: bool = True,
        strict_mode: bool = False,
    ) -> CheckResult:
        """Fix errors using dotnet format."""
        if not error_types or "formatting" in error_types:
            return self.format_code()
        return CheckResult(
            check_type="fix_errors",
            success=True,
            output="",
            errors=[],
            warnings=[],
            files_modified=[],
        )

    def format_code(self) -> CheckResult:
        """Format code using dotnet format."""
        return self._run_check("format", ["format"])

    def type_check(self) -> CheckResult:
        """Run type checking via dotnet build."""
        return self._run_check("type_check", ["build"])

    def lint_code(self) -> CheckResult:
        """Run lint/analyzer pass via dotnet build with warnings as errors."""
        return self._run_check("lint", ["build", "-warnaserror"])
