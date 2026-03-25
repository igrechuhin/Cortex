"""Tests for Java framework adapter."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.java_adapter import (
    JavaAdapter,
    error_check_result,
    infer_from_build_status,
    no_build_check_result,
)


class TestJavaAdapter:
    """Test Java framework adapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter initializes with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root(self) -> None:
        """Adapter initializes with cwd when project_root is None."""
        adapter = JavaAdapter()
        assert adapter.project_root == Path.cwd()

    def test_build_tool_returns_maven_when_pom_xml_exists(self) -> None:
        """_build_tool returns maven when pom.xml is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            adapter = JavaAdapter(str(tmpdir))
            assert adapter.build_tool() == "maven"

    def test_build_tool_returns_gradle_when_build_gradle_exists(self) -> None:
        """_build_tool returns gradle when build.gradle is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle").write_text("")
            adapter = JavaAdapter(str(tmpdir))
            assert adapter.build_tool() == "gradle"

    def test_build_tool_returns_gradle_when_build_gradle_kts_exists(self) -> None:
        """_build_tool returns gradle when build.gradle.kts is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle.kts").write_text("")
            adapter = JavaAdapter(str(tmpdir))
            assert adapter.build_tool() == "gradle"

    def test_build_tool_returns_none_when_no_build_file(self) -> None:
        """_build_tool returns None when no Maven/Gradle build file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            assert adapter.build_tool() is None

    def test_gradle_wrapper_cmd_returns_gradlew_when_present(self) -> None:
        """_gradle_wrapper_cmd returns [gradlew] when gradlew exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle").write_text("")
            _ = (Path(tmpdir) / "gradlew").write_text("#!/bin/sh\n")
            adapter = JavaAdapter(str(tmpdir))
            cmd = adapter.gradle_wrapper_cmd()
            assert len(cmd) == 1
            assert "gradlew" in cmd[0]
            assert "gradle" in cmd[0] or "gradlew" in cmd[0]

    def test_gradle_wrapper_cmd_returns_gradlew_bat_when_present(self) -> None:
        """_gradle_wrapper_cmd returns [gradlew.bat] when gradlew.bat exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle").write_text("")
            _ = (Path(tmpdir) / "gradlew.bat").write_text("@echo off\n")
            adapter = JavaAdapter(str(tmpdir))
            cmd = adapter.gradle_wrapper_cmd()
            assert len(cmd) == 1
            assert "gradlew.bat" in cmd[0]

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_run_tests_returns_error_when_no_build_tool(
        self, mock_run: MagicMock
    ) -> None:
        """run_tests returns error when no Maven/Gradle build found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            result = adapter.run_tests()
            mock_run.assert_not_called()
            assert result.success is False
            assert "No Maven" in result.output or "Gradle" in result.output

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_run_tests_maven_success(self, mock_run: MagicMock) -> None:
        """run_tests returns success when mvn test exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Tests run: 5, Failures: 0"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "mvn" in call_args
            assert "test" in call_args

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_run_tests_gradle_success(self, mock_run: MagicMock) -> None:
        """run_tests returns success when gradle test exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle").write_text("")
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Tests run: 3, Failures: 0"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "gradle" in str(call_args) or "gradlew" in str(call_args)
            assert "test" in str(call_args)

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_run_tests_timeout(self, mock_run: MagicMock) -> None:
        """run_tests returns failure when execution times out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_run.side_effect = subprocess.TimeoutExpired("mvn", 30)

            adapter = JavaAdapter(str(tmpdir))
            result = adapter.run_tests(timeout=30)

            assert result.success is False
            assert (
                "timeout" in result.output.lower()
                or "timed out" in result.output.lower()
            )

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_run_tests_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """run_tests returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_run.side_effect = RuntimeError("mvn not found")
            adapter = JavaAdapter(str(tmpdir))
            result = adapter.run_tests()
            assert result.success is False
            assert "mvn not found" in result.output

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_format_code_returns_error_when_no_build_tool(
        self, mock_run: MagicMock
    ) -> None:
        """format_code returns error when no build file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            result = adapter.format_code()
            mock_run.assert_not_called()
            assert result.success is False
            assert result.check_type == "format"

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_format_code_maven_success(self, mock_run: MagicMock) -> None:
        """format_code returns success when mvn spotless:apply exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is True
            assert "spotless" in str(mock_run.call_args)

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_type_check_returns_error_when_no_build_tool(
        self, mock_run: MagicMock
    ) -> None:
        """type_check returns error when no build file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            result = adapter.type_check()
            mock_run.assert_not_called()
            assert result.success is False
            assert result.check_type == "type_check"

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_type_check_maven_success(self, mock_run: MagicMock) -> None:
        """type_check returns success when mvn compile exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is True
            call_args = mock_run.call_args[0][0]
            assert "mvn" in call_args
            assert "compile" in call_args

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_lint_code_returns_error_when_no_build_tool(
        self, mock_run: MagicMock
    ) -> None:
        """lint_code returns error when no build file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            result = adapter.lint_code()
            mock_run.assert_not_called()
            assert result.success is False
            assert result.check_type == "lint"

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_fix_errors_delegates_to_format_code(self, mock_run: MagicMock) -> None:
        """fix_errors delegates to format_code when formatting requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = JavaAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["formatting"])

            assert result.check_type == "fix_errors"
            assert result.success is True

    def test_fix_errors_without_formatting_returns_success(self) -> None:
        """fix_errors returns success when error_types excludes formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["linting"])
            assert result.check_type == "fix_errors"
            assert result.success is True
            assert result.errors == []

    def test_extract_test_counts_infers_from_build_success(self) -> None:
        """_extract_test_counts infers (1,0) when output has BUILD SUCCESS and no counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            passed, failed = adapter.extract_test_counts("BUILD SUCCESS")
            assert passed == 1
            assert failed == 0

    def test_extract_test_counts_infers_from_build_failure(self) -> None:
        """_extract_test_counts infers (0,1) when output has BUILD FAILURE and no counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            passed, failed = adapter.extract_test_counts("BUILD FAILURE")
            assert passed == 0
            assert failed == 1

    def test_extract_test_counts_infers_from_successful(self) -> None:
        """_extract_test_counts infers (1,0) when output has SUCCESSFUL and no counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            passed, failed = adapter.extract_test_counts("SUCCESSFUL")
            assert passed == 1
            assert failed == 0

    def test_extract_test_counts_infers_from_failed(self) -> None:
        """_extract_test_counts infers (0,1) when output has FAILED and no counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = JavaAdapter(str(tmpdir))
            passed, failed = adapter.extract_test_counts("FAILED")
            assert passed == 0
            assert failed == 1

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_format_code_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """format_code returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_run.side_effect = RuntimeError("mvn not found")
            adapter = JavaAdapter(str(tmpdir))
            result = adapter.format_code()
            assert result.success is False
            assert result.check_type == "format"
            assert "mvn not found" in result.output

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_type_check_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """type_check returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_run.side_effect = RuntimeError("mvn not found")
            adapter = JavaAdapter(str(tmpdir))
            result = adapter.type_check()
            assert result.success is False
            assert result.check_type == "type_check"

    @patch("cortex.services.framework_adapters.java_adapter.subprocess.run")
    def test_lint_code_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """lint_code returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_run.side_effect = RuntimeError("mvn not found")
            adapter = JavaAdapter(str(tmpdir))
            result = adapter.lint_code()
            assert result.success is False
            assert result.check_type == "lint"

    def test_no_build_check_result_returns_expected_structure(self) -> None:
        """_no_build_check_result returns CheckResult with no build message."""
        r = no_build_check_result("format")
        assert r.check_type == "format"
        assert r.success is False
        assert "No Maven" in r.output
        assert r.errors == ["No build file found"]

    def test_error_check_result_returns_expected_structure(self) -> None:
        """_error_check_result returns CheckResult with exception message."""
        e = ValueError("bad")
        r = error_check_result("type_check", e)
        assert r.check_type == "type_check"
        assert r.success is False
        assert "bad" in r.output
        assert r.errors == ["bad"]

    def test_infer_from_build_status_returns_passed_failed_unchanged(
        self,
    ) -> None:
        """_infer_from_build_status returns (passed, failed) when not zero/zero."""
        assert infer_from_build_status("", 5, 2) == (5, 2)
        assert infer_from_build_status("other", 0, 1) == (0, 1)
