"""Tests for JavaScript framework adapter."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.javascript_adapter import JavaScriptAdapter


class TestJavaScriptAdapter:
    """Test JavaScript framework adapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter initializes with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaScriptAdapter(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root(self) -> None:
        """Adapter initializes with cwd when project_root is None."""
        adapter = JavaScriptAdapter()
        assert adapter.project_root == Path.cwd()

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_run_tests_success(self, mock_run: MagicMock) -> None:
        """run_tests returns success when npm test exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "10 passed, 0 failed"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            assert result.tests_run >= 0
            assert result.tests_passed >= 0
            assert result.tests_failed >= 0

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_run_tests_timeout(self, mock_run: MagicMock) -> None:
        """run_tests returns failure when execution times out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = subprocess.TimeoutExpired("npm", 30)

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.run_tests(timeout=30)

            assert result.success is False
            assert (
                "timeout" in result.output.lower()
                or "timed out" in result.output.lower()
            )
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_run_tests_success_with_low_coverage_reports_error(
        self, mock_run: MagicMock
    ) -> None:
        """run_tests adds error when coverage is below 90%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "5 passed, 0 failed\nCoverage: 85.00%"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.run_tests(coverage_threshold=0.90)

            assert result.success is False
            assert any("85" in e or "below" in e.lower() for e in result.errors)
            assert result.coverage == 0.85

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_format_code_success(self, mock_run: MagicMock) -> None:
        """format_code returns success when Prettier exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Formatted 2 files"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_format_code_failure(self, mock_run: MagicMock) -> None:
        """format_code returns failure when Prettier exits non-zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Prettier error"
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is False
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_format_code_returns_failure_on_exception(
        self, mock_run: MagicMock
    ) -> None:
        """format_code returns failure when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = FileNotFoundError("prettier not found")

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is False
            assert len(result.errors) == 1

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_type_check_success_when_tsc_passes(self, mock_run: MagicMock) -> None:
        """type_check returns success when tsc --noEmit --allowJs exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_type_check_success_when_tsc_not_configured(
        self, mock_run: MagicMock
    ) -> None:
        """type_check returns success with warning when tsc not configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Cannot find module 'typescript'"
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is True
            assert len(result.warnings) > 0

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_type_check_failure_when_tsc_reports_errors(
        self, mock_run: MagicMock
    ) -> None:
        """type_check returns errors when tsc reports type errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = (
                "src/a.js:1:2 error TS2322: Type 'string' is not assignable"
            )
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is False
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_type_check_returns_failure_on_exception(self, mock_run: MagicMock) -> None:
        """type_check returns failure when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = OSError("npx not found")

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is False
            assert len(result.errors) == 1
            assert "npx not found" in result.errors[0]

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_lint_code_success(self, mock_run: MagicMock) -> None:
        """lint_code returns success when ESLint exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.lint_code()

            assert result.check_type == "lint"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_lint_code_returns_failure_on_exception(self, mock_run: MagicMock) -> None:
        """lint_code returns failure when ESLint subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = OSError("eslint not found")

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.lint_code()

            assert result.check_type == "lint"
            assert result.success is False
            assert len(result.errors) == 1

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_fix_errors_runs_lint_and_format(self, mock_run: MagicMock) -> None:
        """fix_errors runs ESLint then Prettier."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.fix_errors()

            assert result.check_type == "fix_errors"
            assert result.success is True
            assert mock_run.call_count >= 2

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_fix_errors_with_formatting_only_runs_prettier(
        self, mock_run: MagicMock
    ) -> None:
        """fix_errors with error_types=['formatting'] runs only Prettier."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["formatting"])

            assert result.check_type == "fix_errors"
            assert result.success is True
            assert mock_run.call_count == 1

    @patch("cortex.services.framework_adapters.javascript_adapter.subprocess.run")
    def test_fix_errors_with_linting_only_runs_eslint(
        self, mock_run: MagicMock
    ) -> None:
        """fix_errors with error_types=['linting'] runs only ESLint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaScriptAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["linting"])

            assert result.check_type == "fix_errors"
            assert result.success is True
            assert mock_run.call_count == 1

    def test_extract_test_counts_parses_passed_failed(self) -> None:
        """_extract_test_counts parses Jest-style output."""
        adapter = JavaScriptAdapter()
        passed, failed = adapter.extract_test_counts("5 passed, 2 failed")
        assert passed == 5
        assert failed == 2

    def test_type_check_success_result_helper(self) -> None:
        """_type_check_success_result returns success CheckResult."""
        adapter = JavaScriptAdapter()
        result = adapter.type_check_success_result("ok")
        assert result.check_type == "type_check"
        assert result.success is True
        assert result.output == "ok"
        assert len(result.errors) == 0

    def test_type_check_not_configured_result_helper(self) -> None:
        """_type_check_not_configured_result returns success with warning."""
        adapter = JavaScriptAdapter()
        result = adapter.type_check_not_configured_result("tsc not found")
        assert result.check_type == "type_check"
        assert result.success is True
        assert len(result.warnings) == 1
        assert "not configured" in result.warnings[0]

    def test_type_check_failure_result_helper(self) -> None:
        """_type_check_failure_result returns failure with errors."""
        adapter = JavaScriptAdapter()
        result = adapter.type_check_failure_result("out", ["err1"])
        assert result.check_type == "type_check"
        assert result.success is False
        assert result.errors == ["err1"]

    def test_type_check_exception_result_helper(self) -> None:
        """_type_check_exception_result returns failure with exception message."""
        adapter = JavaScriptAdapter()
        result = adapter.type_check_exception_result(ValueError("bad"))
        assert result.check_type == "type_check"
        assert result.success is False
        assert result.errors == ["bad"]

    def test_parse_tsc_errors_finds_ts_errors(self) -> None:
        """parse_tsc_errors extracts lines with error TS."""
        adapter = JavaScriptAdapter()
        output = "src/a.js:1:2 error TS2322: not assignable\nsrc/b.js:3:4 warning"
        errors = adapter.parse_tsc_errors(output)
        assert len(errors) == 1
        assert "TS2322" in errors[0]

    def test_parse_eslint_output_splits_errors_and_warnings(self) -> None:
        """parse_eslint_output separates error and warning lines."""
        adapter = JavaScriptAdapter()
        output = (
            "src/a.js:1:1: error Unexpected var\nsrc/b.js:2:2: warning Prefer const\n"
        )
        errs, warns = adapter.parse_eslint_output(output)
        assert len(errs) == 1
        assert "error" in errs[0].lower()
        assert len(warns) == 1
        assert "warning" in warns[0].lower()
