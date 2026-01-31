"""Tests for Kotlin framework adapter."""

# pyright: reportPrivateUsage=false
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.kotlin_adapter import KotlinAdapter


class TestKotlinAdapter:
    """Test Kotlin framework adapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter initializes with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = KotlinAdapter(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root(self) -> None:
        """Adapter initializes with cwd when project_root is None."""
        adapter = KotlinAdapter()
        assert adapter.project_root == Path.cwd()

    def test_build_tool_returns_maven_when_pom_xml_exists(self) -> None:
        """_build_tool returns maven when pom.xml is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            adapter = KotlinAdapter(str(tmpdir))
            assert adapter._build_tool() == "maven"

    def test_build_tool_returns_gradle_when_build_gradle_kts_exists(self) -> None:
        """_build_tool returns gradle when build.gradle.kts is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle.kts").write_text("")
            adapter = KotlinAdapter(str(tmpdir))
            assert adapter._build_tool() == "gradle"

    def test_build_tool_returns_none_when_no_build_file(self) -> None:
        """_build_tool returns None when no Maven/Gradle build file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = KotlinAdapter(str(tmpdir))
            assert adapter._build_tool() is None

    def test_gradle_wrapper_cmd_returns_gradlew_when_present(self) -> None:
        """_gradle_wrapper_cmd returns [gradlew] when gradlew exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle.kts").write_text("")
            _ = (Path(tmpdir) / "gradlew").write_text("#!/bin/sh\n")
            adapter = KotlinAdapter(str(tmpdir))
            cmd = adapter._gradle_wrapper_cmd()
            assert len(cmd) == 1
            assert "gradlew" in cmd[0]

    def test_gradle_wrapper_cmd_returns_gradlew_bat_when_present(self) -> None:
        """_gradle_wrapper_cmd returns [gradlew.bat] when gradlew.bat exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle.kts").write_text("")
            _ = (Path(tmpdir) / "gradlew.bat").write_text("@echo off\n")
            adapter = KotlinAdapter(str(tmpdir))
            cmd = adapter._gradle_wrapper_cmd()
            assert len(cmd) == 1
            assert "gradlew.bat" in cmd[0]

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_run_tests_returns_error_when_no_build_tool(
        self, mock_run: MagicMock
    ) -> None:
        """run_tests returns error when no Maven/Gradle build found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.run_tests()
            mock_run.assert_not_called()
            assert result.success is False
            assert "No Maven" in result.output or "Gradle" in result.output

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_run_tests_gradle_success(self, mock_run: MagicMock) -> None:
        """run_tests returns success when gradle test exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle.kts").write_text("")
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "BUILD SUCCESSFUL"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            call_args = mock_run.call_args[0][0]
            assert "test" in call_args

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_run_tests_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """run_tests returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle.kts").write_text("")
            mock_run.side_effect = RuntimeError("gradle not found")
            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.run_tests()
            assert result.success is False
            assert "gradle not found" in result.output

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_format_code_returns_error_when_no_build_tool(
        self, mock_run: MagicMock
    ) -> None:
        """format_code returns error when no build file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.format_code()
            mock_run.assert_not_called()
            assert result.success is False
            assert result.check_type == "format"

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_format_code_gradle_success(self, mock_run: MagicMock) -> None:
        """format_code returns success when gradle spotlessApply exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle.kts").write_text("")
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is True
            assert "spotlessApply" in str(mock_run.call_args)

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_type_check_returns_error_when_no_build_tool(
        self, mock_run: MagicMock
    ) -> None:
        """type_check returns error when no build file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.type_check()
            mock_run.assert_not_called()
            assert result.success is False
            assert result.check_type == "type_check"

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_type_check_gradle_compile_kotlin_success(
        self, mock_run: MagicMock
    ) -> None:
        """type_check runs compileKotlin for Gradle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle.kts").write_text("")
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is True
            call_args = mock_run.call_args[0][0]
            assert "compileKotlin" in call_args

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_lint_code_returns_error_when_no_build_tool(
        self, mock_run: MagicMock
    ) -> None:
        """lint_code returns error when no build file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.lint_code()
            mock_run.assert_not_called()
            assert result.success is False
            assert result.check_type == "lint"

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_fix_errors_delegates_to_format_code(self, mock_run: MagicMock) -> None:
        """fix_errors delegates to format_code when formatting requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "build.gradle.kts").write_text("")
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["formatting"])

            assert result.check_type == "fix_errors"
            assert result.success is True

    def test_fix_errors_without_formatting_returns_success(self) -> None:
        """fix_errors returns success when error_types excludes formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["linting"])
            assert result.check_type == "fix_errors"
            assert result.success is True
            assert result.errors == []

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_format_code_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """format_code returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_run.side_effect = RuntimeError("mvn not found")
            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.format_code()
            assert result.success is False
            assert result.check_type == "format"
            assert "mvn not found" in result.output

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_type_check_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """type_check returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_run.side_effect = RuntimeError("mvn not found")
            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.type_check()
            assert result.success is False
            assert result.check_type == "type_check"

    @patch("cortex.services.framework_adapters.kotlin_adapter.subprocess.run")
    def test_lint_code_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """lint_code returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pom.xml").write_text("<project/>")
            mock_run.side_effect = RuntimeError("mvn not found")
            adapter = KotlinAdapter(str(tmpdir))
            result = adapter.lint_code()
            assert result.success is False
            assert result.check_type == "lint"
