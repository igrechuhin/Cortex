"""Tests for Go framework adapter."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.go_adapter import GoAdapter


class TestGoAdapter:
    """Test Go framework adapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter initializes with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = GoAdapter(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root(self) -> None:
        """Adapter initializes with cwd when project_root is None."""
        adapter = GoAdapter()
        assert adapter.project_root == Path.cwd()

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_run_tests_success(self, mock_run: MagicMock) -> None:
        """run_tests returns success when go test exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "--- PASS: TestFoo (0.00s)\n--- PASS: TestBar (0.00s)"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = GoAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            assert result.tests_run >= 0
            assert result.tests_passed >= 0
            assert result.tests_failed >= 0

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_run_tests_timeout(self, mock_run: MagicMock) -> None:
        """run_tests returns failure when execution times out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = subprocess.TimeoutExpired("go", 30)

            adapter = GoAdapter(str(tmpdir))
            result = adapter.run_tests(timeout=30)

            assert result.success is False
            assert (
                "timeout" in result.output.lower()
                or "timed out" in result.output.lower()
            )
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_format_code_success(self, mock_run: MagicMock) -> None:
        """format_code returns success when go fmt exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = GoAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_format_code_failure(self, mock_run: MagicMock) -> None:
        """format_code returns failure when go fmt exits non-zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "go fmt failed"
            mock_run.return_value = mock_result

            adapter = GoAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is False
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_format_code_returns_failure_on_exception(
        self, mock_run: MagicMock
    ) -> None:
        """format_code returns failure when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = FileNotFoundError("go not found")

            adapter = GoAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is False
            assert len(result.errors) == 1

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_type_check_success(self, mock_run: MagicMock) -> None:
        """type_check returns success when go build exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = GoAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_type_check_failure_when_compiler_reports_errors(
        self, mock_run: MagicMock
    ) -> None:
        """type_check returns errors when go build reports errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "main.go:10:2: undefined: x"
            mock_run.return_value = mock_result

            adapter = GoAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is False
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_type_check_returns_failure_on_exception(self, mock_run: MagicMock) -> None:
        """type_check returns failure when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = OSError("go not found")

            adapter = GoAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is False
            assert len(result.errors) == 1
            assert "go not found" in result.errors[0]

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_lint_code_success(self, mock_run: MagicMock) -> None:
        """lint_code returns success when go vet exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = GoAdapter(str(tmpdir))
            result = adapter.lint_code()

            assert result.check_type == "lint"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_lint_code_returns_failure_on_exception(self, mock_run: MagicMock) -> None:
        """lint_code returns failure when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = OSError("go not found")

            adapter = GoAdapter(str(tmpdir))
            result = adapter.lint_code()

            assert result.check_type == "lint"
            assert result.success is False
            assert len(result.errors) == 1

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_fix_errors_runs_fmt(self, mock_run: MagicMock) -> None:
        """fix_errors runs go fmt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = GoAdapter(str(tmpdir))
            result = adapter.fix_errors()

            assert result.check_type == "fix_errors"
            assert result.success is True
            assert mock_run.call_count >= 1

    @patch("cortex.services.framework_adapters.go_adapter.subprocess.run")
    def test_fix_errors_with_formatting_only_runs_fmt(
        self, mock_run: MagicMock
    ) -> None:
        """fix_errors with error_types=['formatting'] runs only go fmt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = GoAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["formatting"])

            assert result.check_type == "fix_errors"
            assert result.success is True
            assert mock_run.call_count == 1

    def test_extract_test_counts_parses_go_test_output(self) -> None:
        """_extract_test_counts parses go test result lines."""
        adapter = GoAdapter()
        output = "--- PASS: TestFoo (0.00s)\n--- PASS: TestBar (0.00s)\n--- FAIL: TestBaz (0.00s)"
        passed, failed = adapter.extract_test_counts(output)
        assert passed == 2
        assert failed == 1

    def test_parse_go_vet_output_extracts_error_lines(self) -> None:
        """_parse_go_vet_output extracts file:line: message lines."""
        adapter = GoAdapter()
        output = "main.go:10:2: undefined: x\nmain.go:11:3: undefined: y"
        errs = adapter.parse_go_vet_output(output)
        assert len(errs) == 2
        assert "main.go:10" in errs[0]
        assert "main.go:11" in errs[1]
