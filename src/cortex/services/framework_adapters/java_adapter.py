"""Java Framework Adapter

Adapter for Java projects using Maven or Gradle: format (Spotless),
compile (type check), validate/check (lint), and test.
"""

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

from .base import CheckResult, FrameworkAdapter, TestResult

_JAVA_ERROR_RE = re.compile(r"^\[ERROR\].*|error:\s+.*", re.IGNORECASE)
_JAVAC_LINE_RE = re.compile(r"^.*\.java:\d+:\s+error:", re.IGNORECASE)


def _no_build_check_result(check_type: str) -> CheckResult:
    """Return CheckResult when no build tool is found."""
    return CheckResult(
        check_type=check_type,
        success=False,
        output="No Maven (pom.xml) or Gradle build found",
        errors=["No build file found"],
        warnings=[],
        files_modified=[],
    )


def _error_check_result(check_type: str, e: Exception) -> CheckResult:
    """Return CheckResult for a raised exception."""
    return CheckResult(
        check_type=check_type,
        success=False,
        output=str(e),
        errors=[str(e)],
        warnings=[],
        files_modified=[],
    )


def _infer_from_build_status(output: str, passed: int, failed: int) -> tuple[int, int]:
    """Infer passed/failed from build status when counts are zero."""
    if (
        passed == 0
        and failed == 0
        and ("BUILD SUCCESS" in output or "SUCCESSFUL" in output)
    ):
        return 1, 0
    if (
        passed == 0
        and failed == 0
        and ("BUILD FAILURE" in output or "FAILED" in output)
    ):
        return 0, 1
    return passed, failed


class JavaAdapter(FrameworkAdapter):
    """Adapter for Java projects (Maven or Gradle)."""

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize Java adapter.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__(project_root)

    def _build_tool(self) -> str | None:
        """Detect Maven or Gradle from project root."""
        root = Path(self.project_root)
        if (root / "pom.xml").is_file():
            return "maven"
        if (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
            return "gradle"
        return None

    def _run_maven(
        self, goals: list[str], timeout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run Maven in project root."""
        cmd = ["mvn", "-q", *goals]
        return subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _gradle_wrapper_cmd(self) -> list[str]:
        """Return Gradle wrapper command (gradlew or gradlew.bat)."""
        root = Path(self.project_root)
        bat = root / "gradlew.bat"
        if bat.is_file():
            return [str(bat)]
        gw = root / "gradlew"
        if gw.is_file():
            return [str(gw)]
        return ["gradle"]

    def _run_gradle(
        self, tasks: list[str], timeout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run Gradle in project root."""
        cmd = self._gradle_wrapper_cmd() + ["--quiet", *tasks]
        return subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
    ) -> TestResult:
        """Run test suite via Maven or Gradle."""
        tool = self._build_tool()
        if tool is None:
            return self._error_test_result("No Maven (pom.xml) or Gradle build found")
        try:
            if tool == "maven":
                result = self._run_maven(["test"], timeout=timeout)
            else:
                result = self._run_gradle(["test"], timeout=timeout)
            output = result.stdout + result.stderr
            return self._parse_test_output(output, result.returncode == 0)
        except subprocess.TimeoutExpired:
            return self._timeout_test_result()
        except Exception as e:
            return self._error_test_result(str(e))

    def _parse_test_output(self, output: str, success: bool) -> TestResult:
        """Parse Maven/Gradle test output."""
        passed, failed = self._extract_test_counts(output)
        total = passed + failed
        pass_rate = (passed / total) if total > 0 else 0.0
        errors: list[str] = []
        if not success:
            errors.append("Test execution failed")
        return TestResult(
            success=success and len(errors) == 0,
            tests_run=total,
            tests_passed=passed,
            tests_failed=failed,
            pass_rate=pass_rate,
            coverage=None,
            output=output,
            errors=errors,
        )

    def _extract_test_counts(self, output: str) -> tuple[int, int]:
        """Extract passed/failed counts from Maven/Gradle test output."""
        passed, failed = 0, 0
        for line in output.splitlines():
            line_lower = line.lower()
            if "tests:" in line_lower or "tests run:" in line_lower:
                parts = line.replace(",", " ").split()
                for i, part in enumerate(parts):
                    if part == "Failures:" and i + 1 < len(parts):
                        try:
                            failed = int(parts[i + 1])
                        except ValueError:
                            pass
                    if "passed" in part and i > 0:
                        try:
                            passed = int(parts[i - 1])
                        except ValueError:
                            pass
        return _infer_from_build_status(output, passed, failed)

    def _timeout_test_result(self) -> TestResult:
        """Build test result for timeout."""
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

    def _error_test_result(self, message: str) -> TestResult:
        """Build test result for error."""
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

    def fix_errors(
        self,
        error_types: Sequence[str] | None = None,
        auto_fix: bool = True,
        strict_mode: bool = False,
    ) -> CheckResult:
        """Fix errors using Spotless (format)."""
        if not error_types or "formatting" in error_types:
            fmt_r = self.format_code()
            return CheckResult(
                check_type="fix_errors",
                success=fmt_r.success,
                output=fmt_r.output,
                errors=fmt_r.errors,
                warnings=fmt_r.warnings,
                files_modified=fmt_r.files_modified,
            )
        return CheckResult(
            check_type="fix_errors",
            success=True,
            output="",
            errors=[],
            warnings=[],
            files_modified=[],
        )

    def format_code(self) -> CheckResult:
        """Format code using Spotless (Maven spotless:apply / Gradle spotlessApply)."""
        tool = self._build_tool()
        if tool is None:
            return _no_build_check_result("format")
        try:
            result = (
                self._run_maven(["spotless:apply"])
                if tool == "maven"
                else self._run_gradle(["spotlessApply"])
            )
            out = result.stdout + result.stderr
            return CheckResult(
                check_type="format",
                success=result.returncode == 0,
                output=out,
                errors=[] if result.returncode == 0 else ["Spotless format failed"],
                warnings=[],
                files_modified=[],
            )
        except Exception as e:
            return _error_check_result("format", e)

    def type_check(self) -> CheckResult:
        """Run type checker via Maven compile or Gradle compileJava."""
        tool = self._build_tool()
        if tool is None:
            return _no_build_check_result("type_check")
        try:
            result = (
                self._run_maven(["compile"])
                if tool == "maven"
                else self._run_gradle(["compileJava"])
            )
            output = result.stdout + result.stderr
            errs = self._parse_compile_output(output) if result.returncode != 0 else []
            return CheckResult(
                check_type="type_check",
                success=result.returncode == 0,
                output=output,
                errors=errs,
                warnings=[],
                files_modified=[],
            )
        except Exception as e:
            return _error_check_result("type_check", e)

    def _parse_compile_output(self, output: str) -> list[str]:
        """Extract error lines from Maven/Gradle compile output."""
        errors: list[str] = []
        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if _JAVA_ERROR_RE.search(line_stripped) or _JAVAC_LINE_RE.search(
                line_stripped
            ):
                errors.append(line_stripped)
        return errors

    def lint_code(self) -> CheckResult:
        """Run linter via Maven validate or Gradle check."""
        tool = self._build_tool()
        if tool is None:
            return _no_build_check_result("lint")
        try:
            result = (
                self._run_maven(["validate"])
                if tool == "maven"
                else self._run_gradle(["check"])
            )
            output = result.stdout + result.stderr
            errs = self._parse_compile_output(output) if result.returncode != 0 else []
            return CheckResult(
                check_type="lint",
                success=result.returncode == 0,
                output=output,
                errors=errs,
                warnings=[],
                files_modified=[],
            )
        except Exception as e:
            return _error_check_result("lint", e)
