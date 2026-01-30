"""Tests for Rust framework adapter."""

# pyright: reportPrivateUsage=false
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.rust_adapter import RustAdapter


class TestRustAdapter:
    """Test Rust framework adapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter initializes with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = RustAdapter(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root(self) -> None:
        """Adapter initializes with cwd when project_root is None."""
        adapter = RustAdapter()
        assert adapter.project_root == Path.cwd()

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_run_tests_success(self, mock_run: MagicMock) -> None:
        """run_tests returns success when cargo test exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "test result: ok. 10 passed; 0 failed"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = RustAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            assert result.tests_run >= 0
            assert result.tests_passed >= 0
            assert result.tests_failed >= 0

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_run_tests_timeout(self, mock_run: MagicMock) -> None:
        """run_tests returns failure when execution times out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = subprocess.TimeoutExpired("cargo", 30)

            adapter = RustAdapter(str(tmpdir))
            result = adapter.run_tests(timeout=30)

            assert result.success is False
            assert (
                "timeout" in result.output.lower()
                or "timed out" in result.output.lower()
            )
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_format_code_success(self, mock_run: MagicMock) -> None:
        """format_code returns success when cargo fmt exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = RustAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_format_code_failure(self, mock_run: MagicMock) -> None:
        """format_code returns failure when cargo fmt exits non-zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "cargo fmt failed"
            mock_run.return_value = mock_result

            adapter = RustAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is False
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_format_code_returns_failure_on_exception(
        self, mock_run: MagicMock
    ) -> None:
        """format_code returns failure when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = FileNotFoundError("cargo not found")

            adapter = RustAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is False
            assert len(result.errors) == 1

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_type_check_success(self, mock_run: MagicMock) -> None:
        """type_check returns success when cargo check exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = RustAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_type_check_failure_when_compiler_reports_errors(
        self, mock_run: MagicMock
    ) -> None:
        """type_check returns errors when cargo check reports errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = "error[E0382]: use of moved value"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = RustAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is False
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_type_check_returns_failure_on_exception(self, mock_run: MagicMock) -> None:
        """type_check returns failure when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = OSError("cargo not found")

            adapter = RustAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is False
            assert len(result.errors) == 1
            assert "cargo not found" in result.errors[0]

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_lint_code_success(self, mock_run: MagicMock) -> None:
        """lint_code returns success when cargo clippy exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = RustAdapter(str(tmpdir))
            result = adapter.lint_code()

            assert result.check_type == "lint"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_lint_code_returns_failure_on_exception(self, mock_run: MagicMock) -> None:
        """lint_code returns failure when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = OSError("cargo not found")

            adapter = RustAdapter(str(tmpdir))
            result = adapter.lint_code()

            assert result.check_type == "lint"
            assert result.success is False
            assert len(result.errors) == 1

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_fix_errors_runs_fmt_and_fix(self, mock_run: MagicMock) -> None:
        """fix_errors runs cargo fmt then cargo fix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = RustAdapter(str(tmpdir))
            result = adapter.fix_errors()

            assert result.check_type == "fix_errors"
            assert result.success is True
            assert mock_run.call_count >= 2

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_fix_errors_with_formatting_only_runs_fmt(
        self, mock_run: MagicMock
    ) -> None:
        """fix_errors with error_types=['formatting'] runs only cargo fmt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = RustAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["formatting"])

            assert result.check_type == "fix_errors"
            assert result.success is True
            assert mock_run.call_count == 1

    @patch("cortex.services.framework_adapters.rust_adapter.subprocess.run")
    def test_fix_errors_with_linting_only_runs_cargo_fix(
        self, mock_run: MagicMock
    ) -> None:
        """fix_errors with error_types=['linting'] runs only cargo fix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = RustAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["linting"])

            assert result.check_type == "fix_errors"
            assert result.success is True
            assert mock_run.call_count == 1

    def test_extract_test_counts_parses_cargo_test_output(self) -> None:
        """_extract_test_counts parses cargo test result line."""
        adapter = RustAdapter()
        passed, failed = (
            adapter._extract_test_counts(  # pyright: ignore[reportPrivateUsage]
                "test result: ok. 5 passed; 2 failed"
            )
        )
        assert passed == 5
        assert failed == 2

    def test_parse_rust_output_splits_errors_and_warnings(self) -> None:
        """_parse_rust_output separates error and warning lines."""
        adapter = RustAdapter()
        output = "\n".join(
            [
                "error[E0382]: use of moved value",
                "warning: unused variable",
            ]
        )
        errs, warns = adapter._parse_rust_output(  # pyright: ignore[reportPrivateUsage]
            output
        )
        assert len(errs) == 1
        assert "error" in errs[0].lower()
        assert len(warns) == 1
        assert "warning" in warns[0].lower()
