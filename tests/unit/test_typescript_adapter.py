"""Tests for TypeScript framework adapter."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.typescript_adapter import TypeScriptAdapter


class TestTypeScriptAdapter:
    """Test TypeScript framework adapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter initializes with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = TypeScriptAdapter(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root(self) -> None:
        """Adapter initializes with cwd when project_root is None."""
        adapter = TypeScriptAdapter()
        assert adapter.project_root == Path.cwd()

    @patch("cortex.services.framework_adapters.typescript_adapter.subprocess.run")
    def test_run_tests_success(self, mock_run: MagicMock) -> None:
        """run_tests returns success when npm test exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "10 passed, 0 failed"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = TypeScriptAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            assert result.tests_run >= 0
            assert result.tests_passed >= 0
            assert result.tests_failed >= 0

    @patch("cortex.services.framework_adapters.typescript_adapter.subprocess.run")
    def test_run_tests_timeout(self, mock_run: MagicMock) -> None:
        """run_tests returns failure when execution times out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.side_effect = subprocess.TimeoutExpired("npm", 30)

            adapter = TypeScriptAdapter(str(tmpdir))
            result = adapter.run_tests(timeout=30)

            assert result.success is False
            assert (
                "timeout" in result.output.lower()
                or "timed out" in result.output.lower()
            )
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.typescript_adapter.subprocess.run")
    def test_format_code_success(self, mock_run: MagicMock) -> None:
        """format_code returns success when Prettier exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Formatted 2 files"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = TypeScriptAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.typescript_adapter.subprocess.run")
    def test_format_code_failure(self, mock_run: MagicMock) -> None:
        """format_code returns failure when Prettier exits non-zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Prettier error"
            mock_run.return_value = mock_result

            adapter = TypeScriptAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is False
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.typescript_adapter.subprocess.run")
    def test_type_check_success(self, mock_run: MagicMock) -> None:
        """type_check returns success when tsc --noEmit exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = TypeScriptAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.typescript_adapter.subprocess.run")
    def test_type_check_failure(self, mock_run: MagicMock) -> None:
        """type_check returns errors when tsc reports type errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = (
                "src/a.ts:1:2 error TS2322: Type 'string' is not assignable"
            )
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = TypeScriptAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is False
            assert len(result.errors) > 0

    @patch("cortex.services.framework_adapters.typescript_adapter.subprocess.run")
    def test_lint_code_success(self, mock_run: MagicMock) -> None:
        """lint_code returns success when ESLint exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = TypeScriptAdapter(str(tmpdir))
            result = adapter.lint_code()

            assert result.check_type == "lint"
            assert result.success is True
            assert len(result.errors) == 0

    @patch("cortex.services.framework_adapters.typescript_adapter.subprocess.run")
    def test_fix_errors_runs_lint_and_format(self, mock_run: MagicMock) -> None:
        """fix_errors runs ESLint then Prettier."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = TypeScriptAdapter(str(tmpdir))
            result = adapter.fix_errors()

            assert result.check_type == "fix_errors"
            assert result.success is True
            assert mock_run.call_count >= 2

    def test_extract_test_counts_parses_passed_failed(self) -> None:
        """_extract_test_counts parses Jest-style output."""
        adapter = TypeScriptAdapter()
        passed, failed = (
            adapter._extract_test_counts(  # pyright: ignore[reportPrivateUsage]
                "5 passed, 2 failed"
            )
        )
        assert passed == 5
        assert failed == 2

    def test_parse_tsc_errors_finds_ts_errors(self) -> None:
        """_parse_tsc_errors extracts lines with error TS."""
        adapter = TypeScriptAdapter()
        output = "src/a.ts:1:2 error TS2322: not assignable\nsrc/b.ts:3:4 warning"
        errors = adapter.parse_tsc_errors(output)  # pyright: ignore[reportPrivateUsage]
        assert len(errors) == 1
        assert "TS2322" in errors[0]

    def test_parse_eslint_output_splits_errors_and_warnings(self) -> None:
        """_parse_eslint_output separates error and warning lines."""
        adapter = TypeScriptAdapter()
        output = (
            "src/a.ts:1:1: error Unexpected var\nsrc/b.ts:2:2: warning Prefer const\n"
        )
        errs, warns = adapter.parse_eslint_output(
            output
        )  # pyright: ignore[reportPrivateUsage]
        assert len(errs) == 1
        assert "error" in errs[0].lower()
        assert len(warns) == 1
        assert "warning" in warns[0].lower()
