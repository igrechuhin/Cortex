"""Tests for Swift framework adapter."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.swift_adapter import SwiftAdapter


class TestSwiftAdapter:
    """Test Swift framework adapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter initializes with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root(self) -> None:
        """Adapter initializes with cwd when project_root is None."""
        adapter = SwiftAdapter()
        assert adapter.project_root == Path.cwd()

    def test_has_package_swift_true_when_package_swift_exists(self) -> None:
        """_has_package_swift returns True when Package.swift is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            adapter = SwiftAdapter(str(tmpdir))
            assert adapter.has_package_swift() is True

    def test_has_package_swift_false_when_no_package_swift(self) -> None:
        """_has_package_swift returns False when Package.swift is absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            assert adapter.has_package_swift() is False

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_returns_error_when_no_package_swift(
        self, mock_run: MagicMock
    ) -> None:
        """run_tests returns error when no Package.swift found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()
            mock_run.assert_not_called()
            assert result.success is False
            assert "Package.swift" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_success_when_swift_test_exits_0(
        self, mock_run: MagicMock
    ) -> None:
        """run_tests returns success when swift test exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Test run: 3 passed"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            call_args = mock_run.call_args[0][0]
            assert "swift" in call_args
            assert "test" in call_args

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_timeout(self, mock_run: MagicMock) -> None:
        """run_tests returns failure when execution times out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = subprocess.TimeoutExpired("swift", 30)

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests(timeout=30)

            assert result.success is False
            assert (
                "timeout" in result.output.lower()
                or "timed out" in result.output.lower()
            )

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """run_tests returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = RuntimeError("swift not found")
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()
            assert result.success is False
            assert "swift not found" in result.output

    def test_format_code_returns_error_when_no_package_swift(self) -> None:
        """format_code returns error when no Package.swift."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.format_code()
            assert result.success is False
            assert result.check_type == "format"
            assert "Package.swift" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_format_code_success_when_swift_format_exits_0(
        self, mock_run: MagicMock
    ) -> None:
        """format_code returns success when swift format exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is True
            call_args = mock_run.call_args[0][0]
            assert "swift" in call_args
            assert "format" in call_args

    def test_type_check_returns_error_when_no_package_swift(self) -> None:
        """type_check returns error when no Package.swift."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.type_check()
            assert result.success is False
            assert result.check_type == "type_check"
            assert "Package.swift" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_type_check_success_when_swift_build_exits_0(
        self, mock_run: MagicMock
    ) -> None:
        """type_check returns success when swift build exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is True
            call_args = mock_run.call_args[0][0]
            assert "swift" in call_args
            assert "build" in call_args

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_fix_errors_delegates_to_format_code(self, mock_run: MagicMock) -> None:
        """fix_errors delegates to format_code when formatting requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["formatting"])

            assert result.check_type == "fix_errors"
            assert result.success is True

    def test_fix_errors_without_formatting_returns_success(self) -> None:
        """fix_errors returns success when error_types excludes formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["linting"])
            assert result.check_type == "fix_errors"
            assert result.success is True
            assert result.errors == []

    def test_lint_code_returns_error_when_no_package_swift(self) -> None:
        """lint_code delegates to type_check; returns error when no Package.swift."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.lint_code()
            assert result.success is False
            assert result.check_type == "type_check"
            assert "Package.swift" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_format_code_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """format_code returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = RuntimeError("swift not found")
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.format_code()
            assert result.success is False
            assert result.check_type == "format"
            assert "swift not found" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_type_check_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """type_check returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = RuntimeError("swift not found")
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.type_check()
            assert result.success is False
            assert result.check_type == "type_check"
