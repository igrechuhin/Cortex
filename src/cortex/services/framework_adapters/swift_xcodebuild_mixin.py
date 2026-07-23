"""Swift xcodebuild helpers factored out of SwiftAdapter to keep file size under limits.

This mixin provides all methods that invoke xcodebuild: simulator discovery,
project/scheme detection, build-for-testing, and type-check via xcodebuild.
SwiftAdapter inherits from this mixin, so all methods can use ``self`` normally.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .base import CheckResult, TestResult


class SwiftXcodebuildMixin:
    """Mixin providing xcodebuild-based test and type-check methods.

    Subclasses must set before calling mixin methods:
    - ``project_root: Path``
    - ``_cached_simulator_destination: str | None``
    - ``_PREFERRED_SIMULATORS: list[str]``
    - ``_xcodebuild_skip_testing: list[str]``
    And provide: ``extract_test_counts``, ``_error_test_result``,
    ``_timeout_test_result``, ``_parse_build_errors``.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Pass through to next class in MRO; declare variables subclass will override."""
        super().__init__(*args, **kwargs)
        # These will be overwritten by the concrete subclass __init__,
        # but must be declared here for pyright strict-mode compatibility.
        if not hasattr(self, "project_root"):
            self.project_root: Path = Path(".")
        if not hasattr(self, "_cached_simulator_destination"):
            self._cached_simulator_destination: str | None = None
        if not hasattr(self, "_PREFERRED_SIMULATORS"):
            self._PREFERRED_SIMULATORS: list[str] = []
        if not hasattr(self, "_xcodebuild_skip_testing"):
            # AI: Populated from .cortex/config/swift_test.json (see
            # cortex.config.swift_test_config) — Xcode -skip-testing:
            # identifiers excluded from `xcodebuild test`/`test-without-building`.
            self._xcodebuild_skip_testing: list[str] = []

    @staticmethod
    def _error_check_result(check_type: str, message: str) -> CheckResult:
        """Build a failed CheckResult for an unexpected exception."""
        return CheckResult(
            check_type=check_type,
            success=False,
            output=message,
            errors=[message],
            warnings=[],
            files_modified=[],
        )

    @staticmethod
    def _timeout_check_result(check_type: str, tool: str) -> CheckResult:
        """Build a failed CheckResult for a subprocess timeout."""
        msg = f"{tool} exceeded timeout"
        return CheckResult(
            check_type=check_type,
            success=False,
            output=f"{tool} timed out",
            errors=[msg],
            warnings=[],
            files_modified=[],
        )

    def _simulator_destination(self) -> str:
        """Return the best available iOS simulator destination string."""
        if self._cached_simulator_destination is not None:
            return self._cached_simulator_destination
        try:
            result = subprocess.run(
                ["xcrun", "simctl", "list", "devices", "available"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            available_names: set[str] = set()
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("--"):
                    continue
                paren_idx = stripped.find(" (")
                if paren_idx > 0:
                    available_names.add(stripped[:paren_idx])
            for name in self._PREFERRED_SIMULATORS:
                if name in available_names:
                    dest = f"platform=iOS Simulator,name={name}"
                    self._cached_simulator_destination = dest
                    return dest
        except Exception:
            pass
        fallback = "generic/platform=iOS Simulator"
        self._cached_simulator_destination = fallback
        return fallback

    def _xcode_project_path(self) -> Path | None:
        """Return path to the first .xcodeproj found, or None."""
        for p in self.project_root.glob("*.xcodeproj"):
            return p
        return None

    def _xcode_scheme(self) -> str | None:
        """Return the first non-package scheme from xcodebuild -list."""
        return _parse_xcode_scheme(self.project_root, self._xcode_project_path())

    def _run_xcodebuild(
        self,
        args: list[str],
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run xcodebuild command in project root."""
        cmd = ["xcodebuild", *args]
        raw = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=False,
            timeout=timeout,
        )
        stdout = raw.stdout.decode("utf-8", errors="replace") if raw.stdout else ""
        stderr = raw.stderr.decode("utf-8", errors="replace") if raw.stderr else ""
        return subprocess.CompletedProcess(
            args=raw.args,
            returncode=raw.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    # Abstract methods that subclass must provide.
    def extract_test_counts(self, output: str) -> tuple[int, int]:  # pragma: no cover
        """Return (passed, failed) counts from test output."""
        raise NotImplementedError

    def _error_test_result(self, message: str) -> TestResult:  # pragma: no cover
        """Build a failed TestResult for an unexpected error."""
        raise NotImplementedError

    def _timeout_test_result(self) -> TestResult:  # pragma: no cover
        """Build a failed TestResult for a timeout."""
        raise NotImplementedError

    def _parse_build_errors(self, output: str) -> list[str]:  # pragma: no cover
        """Extract error lines from swift build output."""
        raise NotImplementedError

    def _xcodebuild_build_phase(
        self, scheme: str, proj: Path, timeout: int
    ) -> TestResult | None:
        """Build for testing; return failed TestResult on error, None on success."""
        result = self._run_xcodebuild(
            [
                "-project",
                str(proj),
                "-scheme",
                scheme,
                "-destination",
                self._simulator_destination(),
                "build-for-testing",
            ],
            timeout=timeout,
        )
        if result.returncode == 0:
            return None
        output = result.stdout + result.stderr
        errors = [ln.strip() for ln in output.splitlines() if "error:" in ln.lower()][
            :10
        ]
        return TestResult(
            success=False,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output=output,
            errors=errors or ["xcodebuild build-for-testing failed"],
        )

    def _xcodebuild_test_phase_args(self, scheme: str, proj: Path) -> list[str]:
        """Build the ``xcodebuild ... test-without-building`` argv.

        Honors ``self._xcodebuild_skip_testing`` (from
        ``.cortex/config/swift_test.json``) by passing one ``-skip-testing:``
        flag per configured identifier — e.g. a live-network integration test
        class a project's CLAUDE.md documents as excluded from its standard
        test command, so the quality gate doesn't fail on infra it was never
        meant to exercise.
        """
        args = [
            "-project",
            str(proj),
            "-scheme",
            scheme,
            "-destination",
            self._simulator_destination(),
        ]
        args.extend(
            f"-skip-testing:{identifier}"
            for identifier in self._xcodebuild_skip_testing
        )
        args.append("test-without-building")
        return args

    def _xcodebuild_test_phase(
        self, scheme: str, proj: Path, timeout: int
    ) -> TestResult:
        """Run test-without-building and parse results."""
        result = self._run_xcodebuild(
            self._xcodebuild_test_phase_args(scheme, proj), timeout=timeout
        )
        output = result.stdout + result.stderr
        passed, failed = self.extract_test_counts(output)
        total = passed + failed
        success = result.returncode == 0 or (failed == 0 and passed > 0)
        errors = _xcodebuild_test_errors(output) if not success else []
        return TestResult(
            success=success,
            tests_run=total,
            tests_passed=passed,
            tests_failed=failed,
            pass_rate=(passed / total) if total > 0 else 0.0,
            coverage=None,
            output=output,
            errors=errors,
        )

    def _run_xcodebuild_tests(self, timeout: int | None) -> TestResult:
        """Run tests via xcodebuild test-without-building for Xcode projects."""
        scheme = self._xcode_scheme()
        proj = self._xcode_project_path()
        if scheme is None or proj is None:
            return self._error_test_result(
                "No .xcodeproj or scheme found for xcodebuild"
            )
        try:
            build_err = self._xcodebuild_build_phase(scheme, proj, timeout or 300)
            if build_err is not None:
                return build_err
            return self._xcodebuild_test_phase(scheme, proj, timeout or 600)
        except subprocess.TimeoutExpired:
            return self._timeout_test_result()
        except Exception as e:
            return self._error_test_result(str(e))

    def _xcodebuild_type_check_run(self, scheme: str, proj: Path) -> CheckResult:
        """Run xcodebuild build-for-testing and return a type_check CheckResult."""
        try:
            result = self._run_xcodebuild(
                [
                    "-project",
                    str(proj),
                    "-scheme",
                    scheme,
                    "-destination",
                    self._simulator_destination(),
                    "build-for-testing",
                ],
                timeout=300,
            )
            output = result.stdout + result.stderr
            errs = self._parse_build_errors(output) if result.returncode != 0 else []
            return CheckResult(
                check_type="type_check",
                success=result.returncode == 0,
                output=output,
                errors=errs,
                warnings=[],
                files_modified=[],
            )
        except subprocess.TimeoutExpired:
            return self._timeout_check_result(
                "type_check", "xcodebuild build-for-testing"
            )
        except Exception as e:
            return self._error_check_result("type_check", str(e))

    def _type_check_xcodebuild(self) -> CheckResult:
        """Type-check via xcodebuild build-for-testing for Xcode projects."""
        scheme = self._xcode_scheme()
        proj = self._xcode_project_path()
        if scheme is None or proj is None:
            return CheckResult(
                check_type="type_check",
                success=False,
                output="No .xcodeproj or scheme found",
                errors=["No .xcodeproj or scheme found for xcodebuild"],
                warnings=[],
                files_modified=[],
            )
        return self._xcodebuild_type_check_run(scheme, proj)


def _parse_xcode_scheme(project_root: Path, proj: Path | None) -> str | None:
    """Return the first non-package scheme from xcodebuild -list, preferring *-Dev."""
    if proj is None:
        return None
    try:
        result = subprocess.run(
            ["xcodebuild", "-project", str(proj), "-list"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        schemes: list[str] = []
        in_schemes = False
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped == "Schemes:":
                in_schemes = True
                continue
            if in_schemes:
                if stripped == "" or stripped.endswith(":"):
                    break
                if not stripped.endswith("-Package"):
                    schemes.append(stripped)
        for s in schemes:
            if s.endswith("-Dev"):
                return s
        return schemes[0] if schemes else None
    except Exception:
        return None


def _xcodebuild_test_errors(output: str) -> list[str]:
    """Extract error/failure lines from xcodebuild test output (max 10)."""
    errors = [
        ln.strip()
        for ln in output.splitlines()
        if "error:" in ln.lower() or "failed" in ln.lower()
    ][:10]
    return errors or ["xcodebuild test-without-building failed"]
