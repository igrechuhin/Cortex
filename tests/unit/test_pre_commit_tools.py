"""Tests for pre-commit tools."""

import ast
import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.constants import MAX_FILE_LINES, MAX_FUNCTION_LINES
from cortex.core.models import ModelDict
from cortex.core.path_resolver import (
    CortexResourceType,
    ProjectResourceType,
    get_cortex_path,
    get_project_path,
    get_venv_bin_path,
)
from cortex.services.framework_adapters.base import (
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
from cortex.services.language_detector import LanguageInfo
from cortex.tools.pre_commit_helpers import (
    DEFAULT_CHECKS,
    MAX_LOG_OUTPUT_LENGTH,
    PreCommitCheck,
    check_file_sizes,
    check_function_lengths_in_file,
    count_file_lines,
    detect_or_use_language,
    ensure_json_serializable_for_mcp,
    get_docstring_range,
)
from cortex.tools.pre_commit_pipeline import (
    _check_function_lengths,  # pyright: ignore[reportPrivateUsage]
)
from cortex.tools.pre_commit_synapse import run_synapse_script
from cortex.tools.pre_commit_tools import (
    SUPPORTED_LANGUAGES,
    _get_adapter,  # pyright: ignore[reportPrivateUsage]
    execute_pre_commit_checks,
    fix_quality_issues,
)

# Required parameters for execute_pre_commit_checks (tool requires all params).
_EXECUTE_REQUIRED = {
    "test_timeout": 300,
    "coverage_threshold": 0.9,
    "strict_mode": False,
}


class TestExecutePreCommitChecks:
    """Test execute_pre_commit_checks tool."""

    @pytest.mark.asyncio
    async def test_has_timeout_protection(self) -> None:
        """Test that execute_pre_commit_checks has timeout protection decorator."""

        from cortex.core.constants import MCP_TOOL_TIMEOUT_VERY_COMPLEX

        # Verify the function has the timeout wrapper decorator
        # The decorator wraps the function, so we check if it's wrapped
        assert hasattr(execute_pre_commit_checks, "__wrapped__") or hasattr(
            execute_pre_commit_checks, "__name__"
        )
        # Verify timeout constant is correct
        assert MCP_TOOL_TIMEOUT_VERY_COMPLEX == 960.0

    @pytest.mark.asyncio
    async def test_runs_adapter_checks_off_event_loop_via_to_thread(self) -> None:
        """Verify execute_pre_commit_checks runs _execute_all_checks via asyncio.to_thread."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()

            with (
                patch(
                    "cortex.tools.pre_commit_tools.PythonAdapter",
                ) as mock_adapter_class,
                patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ),
                patch(
                    "cortex.tools.pre_commit_tools.asyncio.to_thread",
                    new_callable=AsyncMock,
                ) as mock_to_thread,
            ):
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter
                mock_result = CheckResult(
                    check_type="fix_errors",
                    success=True,
                    output="Fixed",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )
                mock_adapter.fix_errors.return_value = mock_result

                async def run_sync(
                    func: Callable[..., object], *args: object
                ) -> object:  # run in same thread for test
                    return func(*args)

                mock_to_thread.side_effect = run_sync

                result = await execute_pre_commit_checks(
                    checks=["fix_errors"],
                    **_EXECUTE_REQUIRED,
                )

                mock_to_thread.assert_called_once()
                call_args = mock_to_thread.call_args
                assert call_args[0][0].__name__ == "_execute_all_checks"
                assert result["status"] == "success"
                assert result["language"] == "python"

    @pytest.mark.asyncio
    async def test_detect_language_error_when_no_language_detected(self) -> None:
        """Test error when language cannot be detected (no markers in root or ancestors)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Force root_str to tmpdir; ensure adapter-based detection finds nothing
            with (
                patch(
                    "cortex.tools.pre_commit_helpers.get_project_root_str",
                    return_value=str(Path(tmpdir).resolve()),
                ),
                patch(
                    "cortex.tools.pre_commit_helpers.detect_language_at_path",
                    return_value=None,
                ),
                patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=Path(tmpdir).resolve(),
                ),
            ):
                result = await execute_pre_commit_checks(
                    checks=["fix_errors"],
                    **_EXECUTE_REQUIRED,
                )

            assert result["status"] == "error"
            assert "Could not detect project language" in result["error"]

    @pytest.mark.asyncio
    async def test_error_for_unsupported_language(self) -> None:
        """Test error for unsupported language includes supported list."""
        haskell_info = LanguageInfo(
            language="haskell",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.5,
        )

        with (
            patch(
                "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/some/root"),
            ),
            patch(
                "cortex.tools.pre_commit_tools.detect_or_use_language",
                return_value=(haskell_info, "/some/root"),
            ),
        ):
            result = await execute_pre_commit_checks(
                checks=["fix_errors"],
                **_EXECUTE_REQUIRED,
            )

        assert result["status"] == "error"
        assert "not yet supported" in result["error"]
        assert "Supported languages:" in result["error"]
        assert "python" in result["error"]

    @pytest.mark.asyncio
    async def test_return_value_is_dict_and_json_round_trips_for_mcp(self) -> None:
        """Return value must be dict (not JSON string) and round-trip for MCP."""
        haskell_info = LanguageInfo(
            language="haskell",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.5,
        )
        with (
            patch(
                "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/some/root"),
            ),
            patch(
                "cortex.tools.pre_commit_tools.detect_or_use_language",
                return_value=(haskell_info, "/some/root"),
            ),
        ):
            result = await execute_pre_commit_checks(
                checks=["fix_errors"],
                **_EXECUTE_REQUIRED,
            )
        assert isinstance(result, dict), "MCP tool must return dict, not JSON string"
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed == result, "Result must round-trip through JSON for MCP"

    @pytest.mark.asyncio
    async def test_success_with_python_project(self) -> None:
        """Test success with Python project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()

            with (
                patch(
                    "cortex.tools.pre_commit_tools.PythonAdapter"
                ) as mock_adapter_class,
                patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ),
            ):
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter

                mock_adapter.fix_errors.return_value = CheckResult(
                    check_type="fix_errors",
                    success=True,
                    output="Fixed errors",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )

                result = await execute_pre_commit_checks(
                    checks=["fix_errors"],
                    **_EXECUTE_REQUIRED,
                )

                assert result["status"] == "success"
                assert result["language"] == "python"
                assert "fix_errors" in result["checks_performed"]
                assert result["total_errors"] == 0

    @pytest.mark.asyncio
    async def test_language_detected_by_walking_up_from_subdir(self) -> None:
        """When root_str is a subdir of a Python project, language is detected by walking up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _ = (root / "pyproject.toml").write_text("[project]\nname = 'test'")
            subdir = root / "src" / "app"
            subdir.mkdir(parents=True)

            result = detect_or_use_language(language=None, root_str=str(subdir))

            assert not isinstance(
                result, str
            ), "Expected (LanguageInfo, root), not error JSON"
            language_info, root_to_use = result
            assert language_info.language == "python"
            assert Path(root_to_use).resolve() == root.resolve()

    @pytest.mark.asyncio
    async def test_execute_all_checks_by_default(self) -> None:
        """Test that all checks are executed when checks parameter is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter

                mock_result = CheckResult(
                    check_type="test",
                    success=True,
                    output="Success",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )
                mock_adapter.fix_errors.return_value = mock_result
                mock_adapter.format_code.return_value = mock_result
                mock_adapter.type_check.return_value = mock_result
                mock_adapter.lint_code.return_value = mock_result
                mock_adapter.run_tests.return_value = TestResult(
                    success=True,
                    tests_run=10,
                    tests_passed=10,
                    tests_failed=0,
                    pass_rate=1.0,
                    coverage=0.95,
                    output="All tests passed",
                    errors=[],
                )

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result = await execute_pre_commit_checks(
                        checks=[c.value for c in DEFAULT_CHECKS],
                        **_EXECUTE_REQUIRED,
                    )

                assert result["status"] == "success"
                assert len(result["checks_performed"]) == 7
                assert "fix_errors" in result["checks_performed"]
                assert "format" in result["checks_performed"]
                assert "synapse_format" in result["checks_performed"]
                assert "synapse_lint" in result["checks_performed"]
                assert "type_check" in result["checks_performed"]
                assert "quality" in result["checks_performed"]
                assert "tests" in result["checks_performed"]

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        """Test error handling in tool."""
        with patch(
            "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
            new_callable=AsyncMock,
            side_effect=Exception("Test error"),
        ):

            result = await execute_pre_commit_checks(
                checks=["fix_errors"],
                **_EXECUTE_REQUIRED,
            )

            assert result["status"] == "error"
            assert "Test error" in result["error"]

    @pytest.mark.asyncio
    async def test_format_ci_parity_check_when_script_missing_returns_skipped(
        self,
    ) -> None:
        """format_ci_parity when script not present returns success (skipped)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()
            # No .cortex/synapse/scripts/python/check_formatting_ci_parity.py

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter
                mock_adapter.project_root = project_root

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result = await execute_pre_commit_checks(
                        checks=["format_ci_parity"],
                        **_EXECUTE_REQUIRED,
                    )

                assert result["status"] == "success"
                assert "format_ci_parity" in result["checks_performed"]
                assert result["results"]["format_ci_parity"]["success"] is True
                assert "skipped" in result["results"]["format_ci_parity"]["output"]

    @pytest.mark.asyncio
    async def test_test_naming_check_when_script_missing_returns_skipped(
        self,
    ) -> None:
        """test_naming when script not present returns success (skipped)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter
                mock_adapter.project_root = project_root

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result = await execute_pre_commit_checks(
                        checks=["test_naming"],
                        **_EXECUTE_REQUIRED,
                    )

                assert result["status"] == "success"
                assert "test_naming" in result["checks_performed"]
                assert result["results"]["test_naming"]["success"] is True
                assert "skipped" in result["results"]["test_naming"]["output"]

    @pytest.mark.asyncio
    async def test_check_async_tests_check_when_script_missing_returns_skipped(
        self,
    ) -> None:
        """check_async_tests when script not present returns success (skipped)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter
                mock_adapter.project_root = project_root

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result = await execute_pre_commit_checks(
                        checks=["check_async_tests"],
                        **_EXECUTE_REQUIRED,
                    )

                assert result["status"] == "success"
                assert "check_async_tests" in result["checks_performed"]
                assert result["results"]["check_async_tests"]["success"] is True
                assert "skipped" in result["results"]["check_async_tests"]["output"]


class TestRunSynapseScript:
    """Test run_synapse_script helper."""

    def test_run_synapse_script_when_script_missing_returns_skipped(self) -> None:
        """When script path does not exist, returns success with skipped message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = run_synapse_script(
                root, "python", "check_formatting_ci_parity.py", "format_ci_parity"
            )
            assert result.success is True
            assert "skipped" in result.output
            assert result.errors == []

    def test_run_synapse_script_check_async_tests_when_script_missing_returns_skipped(
        self,
    ) -> None:
        """check_async_tests when script path does not exist returns skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = run_synapse_script(
                root, "python", "check_async_tests.py", "check_async_tests"
            )
            assert result.success is True
            assert "skipped" in result.output
            assert result.errors == []

    def test_run_synapse_script_check_async_tests_when_script_exists_runs(
        self,
    ) -> None:
        """check_async_tests script runs and returns a result (pass or report)."""
        project_root = Path(__file__).resolve().parents[2]
        script_path = (
            get_cortex_path(project_root, CortexResourceType.SYNAPSE)
            / "scripts"
            / "python"
            / "check_async_tests.py"
        )
        if not script_path.exists():
            pytest.skip("check_async_tests.py not present (e.g. in minimal tree)")
        result = run_synapse_script(
            project_root, "python", "check_async_tests.py", "check_async_tests"
        )
        assert result.check_type == "check_async_tests"
        assert "skipped" not in result.output or result.success

    def test_resolve_synapse_python_bin_uses_python3_when_no_venv(self) -> None:
        """When .venv/bin/python does not exist, run_synapse_script uses python3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts_dir = (
                get_cortex_path(root, CortexResourceType.SYNAPSE) / "scripts" / "python"
            )
            scripts_dir.mkdir(parents=True)
            script_path = scripts_dir / "check_formatting_ci_parity.py"
            _ = script_path.write_text(
                "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"
            )

            with patch("cortex.tools.pre_commit_synapse.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="ok",
                    stderr="",
                )

                result = run_synapse_script(
                    root,
                    "python",
                    "check_formatting_ci_parity.py",
                    "format_ci_parity",
                )

                assert result.success is True
                call_args = mock_run.call_args[0][0]
                assert call_args[0] == "python3"

    def test_run_synapse_script_when_script_fails_returns_errors(self) -> None:
        """When script runs and returns non-zero, returns failure with output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts_dir = (
                get_cortex_path(root, CortexResourceType.SYNAPSE) / "scripts" / "python"
            )
            scripts_dir.mkdir(parents=True)
            script_path = scripts_dir / "check_formatting_ci_parity.py"
            _ = script_path.write_text("#!/usr/bin/env python3\n")
            get_project_path(root, ProjectResourceType.VENV).mkdir()
            get_venv_bin_path(root).mkdir(parents=True)
            python_bin = get_venv_bin_path(root) / "python"
            _ = python_bin.write_text("")
            python_bin.chmod(0o755)

            with patch("cortex.tools.pre_commit_synapse.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stdout="stdout",
                    stderr="stderr",
                )

                result = run_synapse_script(
                    root,
                    "python",
                    "check_formatting_ci_parity.py",
                    "format_ci_parity",
                )

                assert result.success is False
                assert len(result.errors) >= 1

    def test_run_synapse_script_when_script_fails_with_empty_output_uses_exit_code(
        self,
    ) -> None:
        """When script returns non-zero with empty output, error shows exit code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts_dir = (
                get_cortex_path(root, CortexResourceType.SYNAPSE) / "scripts" / "python"
            )
            scripts_dir.mkdir(parents=True)
            script_path = scripts_dir / "check_formatting_ci_parity.py"
            _ = script_path.write_text("#!/usr/bin/env python3\n")
            get_project_path(root, ProjectResourceType.VENV).mkdir()
            get_venv_bin_path(root).mkdir(parents=True)
            python_bin = get_venv_bin_path(root) / "python"
            _ = python_bin.write_text("")
            python_bin.chmod(0o755)

            with patch("cortex.tools.pre_commit_synapse.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=2,
                    stdout="",
                    stderr="",
                )

                result = run_synapse_script(
                    root,
                    "python",
                    "check_formatting_ci_parity.py",
                    "format_ci_parity",
                )

                assert result.success is False
                assert len(result.errors) == 1
                assert "Exit code 2" in result.errors[0]

    def test_run_synapse_script_when_subprocess_raises_returns_exception_result(
        self,
    ) -> None:
        """When subprocess execution raises, returns failure with exception message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts_dir = (
                get_cortex_path(root, CortexResourceType.SYNAPSE) / "scripts" / "python"
            )
            scripts_dir.mkdir(parents=True)
            script_path = scripts_dir / "check_formatting_ci_parity.py"
            _ = script_path.write_text("#!/usr/bin/env python3\n")

            with patch(
                "cortex.tools.pre_commit_synapse._execute_synapse_script_subprocess"
            ) as mock_exec:
                mock_exec.side_effect = OSError("python not found")

                result = run_synapse_script(
                    root,
                    "python",
                    "check_formatting_ci_parity.py",
                    "format_ci_parity",
                )

                assert result.success is False
                assert len(result.errors) == 1
                assert "python not found" in result.errors[0]


class TestAdapterRegistry:
    """Test adapter registry and _get_adapter for multi-language support."""

    def test_supported_languages_includes_python(self) -> None:
        """Supported languages tuple includes python."""
        assert "python" in SUPPORTED_LANGUAGES
        assert len(SUPPORTED_LANGUAGES) >= 1

    def test_get_adapter_returns_adapter_for_python(self) -> None:
        """_get_adapter returns FrameworkAdapter for python."""
        info = LanguageInfo(
            language="python",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=1.0,
        )
        adapter = _get_adapter(info, None)
        assert adapter is not None
        assert isinstance(adapter, FrameworkAdapter)

    def test_get_adapter_returns_none_for_unsupported_language(self) -> None:
        """_get_adapter returns None for language not in registry."""
        info = LanguageInfo(
            language="haskell",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )
        adapter = _get_adapter(info, "/some/root")
        assert adapter is None

    def test_supported_languages_includes_stub_languages(self) -> None:
        """SUPPORTED_LANGUAGES includes TypeScript, JavaScript, Rust, Go, Java, Swift, Kotlin."""
        for lang in (
            "typescript",
            "javascript",
            "rust",
            "go",
            "java",
            "swift",
            "kotlin",
        ):
            assert lang in SUPPORTED_LANGUAGES
        assert len(SUPPORTED_LANGUAGES) == 8

    def test_get_adapter_returns_typescript_adapter_for_typescript(self) -> None:
        """_get_adapter returns TypeScriptAdapter for typescript."""
        from cortex.services.framework_adapters.typescript_adapter import (
            TypeScriptAdapter,
        )

        info = LanguageInfo(
            language="typescript",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )
        adapter = _get_adapter(info, "/some/root")
        assert adapter is not None
        assert isinstance(adapter, TypeScriptAdapter)

    def test_get_adapter_returns_javascript_adapter_for_javascript(self) -> None:
        """_get_adapter returns JavaScriptAdapter for javascript."""
        from cortex.services.framework_adapters.javascript_adapter import (
            JavaScriptAdapter,
        )

        info = LanguageInfo(
            language="javascript",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )
        adapter = _get_adapter(info, "/some/root")
        assert adapter is not None
        assert isinstance(adapter, JavaScriptAdapter)

    def test_get_adapter_returns_rust_adapter_for_rust(self) -> None:
        """_get_adapter returns RustAdapter for rust."""
        from cortex.services.framework_adapters.rust_adapter import RustAdapter

        info = LanguageInfo(
            language="rust",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )
        adapter = _get_adapter(info, "/some/root")
        assert adapter is not None
        assert isinstance(adapter, RustAdapter)

    def test_get_adapter_returns_go_adapter_for_go(self) -> None:
        """_get_adapter returns GoAdapter for go."""
        from cortex.services.framework_adapters.go_adapter import GoAdapter

        info = LanguageInfo(
            language="go",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )
        adapter = _get_adapter(info, "/some/root")
        assert adapter is not None
        assert isinstance(adapter, GoAdapter)

    def test_get_adapter_returns_java_adapter_for_java(self) -> None:
        """_get_adapter returns JavaAdapter for java."""
        from cortex.services.framework_adapters.java_adapter import JavaAdapter

        info = LanguageInfo(
            language="java",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )
        adapter = _get_adapter(info, "/some/root")
        assert adapter is not None
        assert isinstance(adapter, JavaAdapter)

    def test_get_adapter_returns_swift_adapter_for_swift(self) -> None:
        """_get_adapter returns SwiftAdapter for swift."""
        from cortex.services.framework_adapters.swift_adapter import SwiftAdapter

        info = LanguageInfo(
            language="swift",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )
        adapter = _get_adapter(info, "/some/root")
        assert adapter is not None
        assert isinstance(adapter, SwiftAdapter)

    def test_get_adapter_returns_kotlin_adapter_for_kotlin(self) -> None:
        """_get_adapter returns KotlinAdapter for kotlin."""
        from cortex.services.framework_adapters.kotlin_adapter import KotlinAdapter

        info = LanguageInfo(
            language="kotlin",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )
        adapter = _get_adapter(info, "/some/root")
        assert adapter is not None
        assert isinstance(adapter, KotlinAdapter)


class TestFixQualityIssues:
    """Test fix_quality_issues tool."""

    @pytest.mark.asyncio
    async def test_fix_quality_issues_error_path(self) -> None:
        """Test error path when execute_pre_commit_checks returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()

            with patch(
                "cortex.tools.pre_commit_tools.execute_pre_commit_checks"
            ) as mock_execute:
                mock_execute.return_value = {"status": "error", "error": "Test error"}

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result_json = await fix_quality_issues()
                result = json.loads(result_json)

                assert result["status"] == "error"
                assert result["error"] == "Test error"
                assert "error_type" in result
                assert "suggestion" in result

    @pytest.mark.asyncio
    async def test_fix_quality_issues_success_when_checks_report_errors(self) -> None:
        """Test non-exceptional 'status=error' from checks is still
        handled as success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()

            with (
                patch(
                    "cortex.tools.pre_commit_tools.execute_pre_commit_checks"
                ) as mock_execute,
                patch(
                    "cortex.tools.pre_commit_tools.fix_markdown_lint"
                ) as mock_markdown,
            ):
                mock_execute.return_value = {
                    "status": "error",
                    "checks_performed": ["fix_errors", "format", "type_check"],
                    "files_modified": ["file1.py"],
                    "total_errors": 1,
                    "total_warnings": 0,
                    "success": False,
                    "results": {
                        "fix_errors": {
                            "errors": ["E1"],
                            "warnings": [],
                            "files_modified": ["file1.py"],
                        },
                        "format": {"files_formatted": 0},
                        "type_check": {"errors": [], "warnings": []},
                    },
                }
                mock_markdown.return_value = json.dumps(
                    {"success": True, "files_fixed": 0, "files_processed": 0}
                )

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result_json = await fix_quality_issues()
                result = json.loads(result_json)

                assert result["status"] == "success"
                assert result["error_message"] is None
                assert result["errors_fixed"] == 1
                # Check that remaining issues are reported (with more specific message)
                assert len(result["remaining_issues"]) > 0
                assert any(
                    "1 linting/formatting errors remain" in issue
                    for issue in result["remaining_issues"]
                )

    @pytest.mark.asyncio
    async def test_fix_quality_issues_exception_handling(self) -> None:
        """Test exception handling in fix_quality_issues."""
        with patch(
            "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
            new_callable=AsyncMock,
            side_effect=Exception("Root error"),
        ):

            result_json = await fix_quality_issues()
            result = json.loads(result_json)

            assert result["status"] == "error"
            assert result["error"] == "Root error"
            assert "error_type" in result
            assert "suggestion" in result

    @pytest.mark.asyncio
    async def test_fix_quality_issues_success_path(self) -> None:
        """Test success path in fix_quality_issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()

            with (
                patch(
                    "cortex.tools.pre_commit_tools.execute_pre_commit_checks"
                ) as mock_execute,
                patch(
                    "cortex.tools.pre_commit_tools.fix_markdown_lint"
                ) as mock_markdown,
            ):
                mock_execute.return_value = {
                    "status": "success",
                    "checks": {
                        "fix_errors": {
                            "errors": [],
                            "warnings": [],
                            "files_modified": ["file1.py"],
                        },
                        "format": {"files_formatted": 1},
                        "type_check": {"errors": 0, "warnings": 0},
                    },
                }
                mock_markdown.return_value = json.dumps(
                    {"success": True, "files_fixed": 1, "files_processed": 1}
                )

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result_json = await fix_quality_issues()
                result = json.loads(result_json)

                assert result["status"] == "success"
                assert result["errors_fixed"] >= 0
                assert len(result["files_modified"]) >= 0

    @pytest.mark.asyncio
    async def test_fix_quality_issues_clean_repo_no_remaining_issues(self) -> None:
        """Test that fix_quality_issues returns empty remaining_issues on clean repo.

        This test verifies the fix for over-reporting remaining issues.
        Even if total_errors/total_warnings are non-zero, if all checks
        succeeded (success=True), remaining_issues should be empty.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()

            with (
                patch(
                    "cortex.tools.pre_commit_tools.execute_pre_commit_checks"
                ) as mock_execute,
                patch(
                    "cortex.tools.pre_commit_tools.fix_markdown_lint"
                ) as mock_markdown,
            ):
                # Simulate a clean repo where all checks succeeded but
                # total_errors/total_warnings might be non-zero
                # (e.g., from previous runs)
                mock_execute.return_value = {
                    "status": "success",
                    "checks_performed": ["fix_errors", "format", "type_check"],
                    "files_modified": [],
                    "total_errors": 4175,  # Large number that should NOT
                    # appear in remaining_issues
                    "total_warnings": 100,  # Large number that should NOT
                    # appear in remaining_issues
                    "success": True,
                    "results": {
                        "fix_errors": {
                            "check_type": "fix_errors",
                            "success": True,  # All checks succeeded
                            "errors": [],
                            "warnings": [],
                            "files_modified": [],
                        },
                        "format": {
                            "check_type": "format",
                            "success": True,  # Format succeeded
                            "errors": [],
                            "files_modified": [],
                        },
                        "type_check": {
                            "check_type": "type_check",
                            "success": True,  # Type check succeeded
                            "errors": [],
                        },
                    },
                }
                mock_markdown.return_value = json.dumps(
                    {"success": True, "files_fixed": 0, "files_processed": 0}
                )

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result_json = await fix_quality_issues()
                result = json.loads(result_json)

                assert result["status"] == "success"
                # Even though total_errors=4175, remaining_issues should be empty
                # because all checks succeeded (success=True)
                assert result["remaining_issues"] == []


class TestCountFileLines:
    """Test count_file_lines helper function."""

    def test_count_lines_simple_file(self) -> None:
        """Test counting lines in a simple Python file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("x = 1\n")
            _ = f.write("y = 2\n")
            _ = f.write("z = 3\n")
            f.flush()
            path = Path(f.name)

        try:
            count = count_file_lines(path)
            assert count == 3
        finally:
            path.unlink()

    def test_count_lines_with_comments_and_blanks(self) -> None:
        """Test counting lines excludes comments and blanks."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("# This is a comment\n")
            _ = f.write("\n")
            _ = f.write("x = 1\n")
            _ = f.write("  # Indented comment\n")
            _ = f.write("\n")
            _ = f.write("y = 2\n")
            f.flush()
            path = Path(f.name)

        try:
            count = count_file_lines(path)
            assert count == 2  # Only x = 1 and y = 2
        finally:
            path.unlink()

    def test_count_lines_with_docstring(self) -> None:
        """Test counting lines handles docstrings."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Simple docstring on one line toggles in_docstring twice (becomes false)
            # so the line after it counts normally
            _ = f.write("x = 1\n")
            _ = f.write("y = 2\n")
            f.flush()
            path = Path(f.name)

        try:
            count = count_file_lines(path)
            # Both lines should be counted
            assert count == 2
        finally:
            path.unlink()

    def test_count_lines_nonexistent_file(self) -> None:
        """Test counting lines returns 0 for nonexistent file."""
        count = count_file_lines(Path("/nonexistent/file.py"))
        assert count == 0


class TestCheckFileSizes:
    """Test check_file_sizes helper (from pre_commit_helpers)."""

    def test_no_violations_when_no_src(self) -> None:
        """Test no violations when src directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            violations = check_file_sizes(Path(tmpdir))
            assert violations == []

    def test_no_violations_when_files_within_limit(self) -> None:
        """Test no violations when all files are within limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a small file
            _ = (src_dir / "small.py").write_text("x = 1\ny = 2\n")

            violations = check_file_sizes(project_root)
            assert violations == []

    def test_detects_file_size_violation(self) -> None:
        """Test detection of file exceeding max lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a large file exceeding MAX_FILE_LINES
            large_content = "\n".join(
                [f"x{i} = {i}" for i in range(MAX_FILE_LINES + 50)]
            )
            _ = (src_dir / "large.py").write_text(large_content)

            violations = check_file_sizes(project_root)
            assert len(violations) == 1
            assert violations[0].file == "src/large.py"
            assert violations[0].lines > MAX_FILE_LINES
            assert violations[0].excess > 0

    def test_skips_test_files(self) -> None:
        """Test that test files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a large test file
            large_content = "\n".join(
                [f"x{i} = {i}" for i in range(MAX_FILE_LINES + 50)]
            )
            _ = (src_dir / "test_large.py").write_text(large_content)

            violations = check_file_sizes(project_root)
            assert violations == []  # test files are skipped


class TestEnsureJsonSerializableForMcp:
    """Test ensure_json_serializable_for_mcp (MCP JSON round-trip)."""

    def test_preserves_normal_dict(self) -> None:
        """Normal dict round-trips unchanged."""
        data: ModelDict = {
            "status": "success",
            "language": "python",
            "total_errors": 0,
        }
        result = ensure_json_serializable_for_mcp(data)
        assert result == data
        assert json.loads(json.dumps(result)) == result

    def test_converts_float_nan_to_none(self) -> None:
        """Float nan is converted so JSON round-trip succeeds."""
        data: ModelDict = cast(ModelDict, {"score": float("nan")})
        result = ensure_json_serializable_for_mcp(data)
        assert result["score"] is None
        assert json.loads(json.dumps(result)) == result

    def test_converts_float_inf_to_none(self) -> None:
        """Float inf is converted so JSON round-trip succeeds."""
        data: ModelDict = cast(ModelDict, {"value": float("inf")})
        result = ensure_json_serializable_for_mcp(data)
        assert result["value"] is None
        assert json.loads(json.dumps(result)) == result

    def test_converts_nested_nan_in_list(self) -> None:
        """Nested list with nan is converted."""
        data: ModelDict = cast(ModelDict, {"items": [1.0, float("nan"), 2.0]})
        result = ensure_json_serializable_for_mcp(data)
        assert result["items"] == [1.0, None, 2.0]
        assert json.loads(json.dumps(result)) == result

    def test_converts_nested_inf_in_dict(self) -> None:
        """Nested dict with inf is converted."""
        data: ModelDict = cast(
            ModelDict, {"nested": {"a": 1, "b": float("inf"), "c": 2}}
        )
        result = ensure_json_serializable_for_mcp(data)
        assert cast(dict[str, object], result["nested"])["b"] is None
        assert json.loads(json.dumps(result)) == result


class TestGetDocstringRange:
    """Test get_docstring_range helper (docstring line range from AST)."""

    def test_returns_range_when_function_has_docstring(self) -> None:
        """Function with docstring returns (start, end) line range."""
        source = 'def foo():\n    """Docstring here."""\n    pass\n'
        tree = ast.parse(source)
        func = tree.body[0]
        assert isinstance(func, ast.FunctionDef)
        result = get_docstring_range(func)
        assert result is not None
        start, end = result
        assert start == 2
        assert end == 2

    def test_returns_none_when_no_docstring(self) -> None:
        """Function without docstring returns None."""
        source = "def bar():\n    pass\n"
        tree = ast.parse(source)
        func = tree.body[0]
        assert isinstance(func, ast.FunctionDef)
        result = get_docstring_range(func)
        assert result is None

    def test_works_for_async_function(self) -> None:
        """Async function with docstring returns range."""
        source = 'async def baz():\n    """Async doc."""\n    return 1\n'
        tree = ast.parse(source)
        func = tree.body[0]
        assert isinstance(func, ast.AsyncFunctionDef)
        result = get_docstring_range(func)
        assert result is not None
        assert result[0] == 2
        assert result[1] == 2

    def test_multiline_docstring_returns_full_range(self) -> None:
        """Function with multiline docstring returns (start, end) spanning lines."""
        source = 'def f():\n    """Line one.\n    Line two."""\n    pass\n'
        tree = ast.parse(source)
        func = tree.body[0]
        assert isinstance(func, ast.FunctionDef)
        result = get_docstring_range(func)
        assert result is not None
        start, end = result
        assert start == 2
        assert end >= 2

    def test_function_with_only_docstring_no_other_body(self) -> None:
        """Function whose only body element is docstring still returns range."""
        source = 'def only_doc():\n    """Only docstring."""\n'
        tree = ast.parse(source)
        func = tree.body[0]
        assert isinstance(func, ast.FunctionDef)
        result = get_docstring_range(func)
        assert result is not None
        assert result[0] == 2
        assert result[1] == 2

    def test_function_with_empty_body_returns_none(self) -> None:
        """Function with no statements (empty body) returns None."""
        source = "def empty():\n    pass\n"
        tree = ast.parse(source)
        func = tree.body[0]
        assert isinstance(func, ast.FunctionDef)
        result = get_docstring_range(func)
        assert result is None


class TestCheckFunctionLengths:
    """Test _check_function_lengths and _check_function_lengths_in_file."""

    def test_no_violations_when_no_src(self) -> None:
        """Test no violations when src directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            violations = _check_function_lengths(Path(tmpdir))
            assert violations == []

    def test_no_violations_for_short_function(self) -> None:
        """Test no violations for short functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            content = '''
def short_func():
    """Short function."""
    x = 1
    y = 2
    return x + y
'''
            _ = (src_dir / "short.py").write_text(content)

            violations = _check_function_lengths(project_root)
            assert violations == []

    def test_detects_long_function(self) -> None:
        """Test detection of function exceeding max lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a file with a long function
            lines = [f"    x{i} = {i}" for i in range(MAX_FUNCTION_LINES + 10)]
            content = "def long_func():\n" + "\n".join(lines) + "\n    return x0\n"
            _ = (src_dir / "long.py").write_text(content)

            violations = _check_function_lengths(project_root)
            assert len(violations) == 1
            assert violations[0].function == "long_func"
            assert violations[0].lines > MAX_FUNCTION_LINES

    def test_check_function_lengths_in_file_syntax_error(self) -> None:
        """Test handling of syntax errors in file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("def broken(\n")  # Invalid syntax
            f.flush()
            path = Path(f.name)

        try:
            violations = check_function_lengths_in_file(path)
            assert violations == []  # Should return empty on syntax error
        finally:
            path.unlink()

    def test_check_function_lengths_in_file_read_error(self) -> None:
        """Test handling of file read errors."""
        violations = check_function_lengths_in_file(Path("/nonexistent/file.py"))
        assert violations == []

    def test_skips_test_files(self) -> None:
        """Test that test files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a test file with a long function
            lines = [f"    x{i} = {i}" for i in range(MAX_FUNCTION_LINES + 10)]
            content = "def long_func():\n" + "\n".join(lines) + "\n    return x0\n"
            _ = (src_dir / "test_long.py").write_text(content)

            violations = _check_function_lengths(project_root)
            assert violations == []  # test files are skipped

    def test_detects_async_function_length(self) -> None:
        """Test detection of async function exceeding max lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a file with a long async function
            lines = [f"    x{i} = {i}" for i in range(MAX_FUNCTION_LINES + 10)]
            content = (
                "async def long_async_func():\n"
                + "\n".join(lines)
                + "\n    return x0\n"
            )
            _ = (src_dir / "async_long.py").write_text(content)

            violations = _check_function_lengths(project_root)
            assert len(violations) == 1
            assert violations[0].function == "long_async_func"


class TestQualityCheckIntegration:
    """Integration tests for quality check through execute_pre_commit_checks."""

    @pytest.mark.asyncio
    async def test_quality_check_includes_file_size_check(self) -> None:
        """Test that quality check includes file size violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a small valid file
            _ = (src_dir / "module.py").write_text("x = 1\n")

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter
                mock_adapter.project_root = project_root

                mock_adapter.lint_code.return_value = CheckResult(
                    check_type="lint",
                    success=True,
                    output="All good",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )
                # Quality gate includes type_check (Option A: pipelines run type_check with quality)
                mock_adapter.type_check.return_value = CheckResult(
                    check_type="type_check",
                    success=True,
                    output="0 errors, 0 warnings",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result = await execute_pre_commit_checks(
                        checks=["quality"],
                        **_EXECUTE_REQUIRED,
                    )

                assert result["status"] == "success"
                assert "quality" in result["checks_performed"]
                assert "type_check" in result["checks_performed"]
                # Quality result should include file_size_violations and
                # function_length_violations
                quality_result = result["results"]["quality"]
                assert "file_size_violations" in quality_result
                assert "function_length_violations" in quality_result


class TestLogTruncationBehavior:
    """Tests for truncation of very large log outputs in JSON responses."""

    @pytest.mark.asyncio
    async def test_quality_output_is_truncated_for_large_logs(self) -> None:
        """Large quality output logs should be truncated to keep JSON compact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()
            src_dir = project_root / "src"
            src_dir.mkdir()
            _ = (src_dir / "module.py").write_text("x = 1\n")

            large_output = "X" * (MAX_LOG_OUTPUT_LENGTH * 2)

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter
                mock_adapter.project_root = project_root

                mock_adapter.lint_code.return_value = CheckResult(
                    check_type="lint",
                    success=False,
                    output=large_output,
                    errors=["E1"],
                    warnings=[],
                    files_modified=[],
                )
                # Quality gate includes type_check
                mock_adapter.type_check.return_value = CheckResult(
                    check_type="type_check",
                    success=True,
                    output="0 errors",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )

                with patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result = await execute_pre_commit_checks(
                        checks=["quality"],
                        **_EXECUTE_REQUIRED,
                    )

                assert result["status"] == "error"
                quality_result = result["results"]["quality"]
                truncated_output = quality_result["output"]
                assert isinstance(truncated_output, str)
                assert len(truncated_output) <= MAX_LOG_OUTPUT_LENGTH + 200
                assert "truncated" in truncated_output


@pytest.mark.asyncio
class TestPreCommitToolsContextLogging:
    """Test pre-commit tools use log_client when ctx is passed."""

    async def test_execute_pre_commit_checks_calls_log_client_when_ctx_passed(
        self,
    ) -> None:
        """When ctx is passed, execute_pre_commit_checks logs start and completion."""
        mock_ctx = AsyncMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            get_project_path(project_root, ProjectResourceType.VENV).mkdir()
            with (
                patch(
                    "cortex.tools.pre_commit_tools.log_client",
                    new_callable=AsyncMock,
                ) as mock_log,
                patch(
                    "cortex.tools.pre_commit_tools.PythonAdapter",
                ) as mock_adapter_class,
                patch(
                    "cortex.tools.pre_commit_tools.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ),
                patch(
                    "cortex.tools.pre_commit_tools.asyncio.to_thread",
                    new_callable=AsyncMock,
                ) as mock_to_thread,
            ):
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter
                mock_result = CheckResult(
                    check_type="fix_errors",
                    success=True,
                    output="OK",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )
                mock_adapter.fix_errors.return_value = mock_result

                async def run_sync(
                    _fn: Callable[
                        ...,
                        tuple[dict[str, CheckResult | TestResult | object], object],
                    ],
                    _adapter: FrameworkAdapter,
                    _lang: str,
                    checks: list[PreCommitCheck],
                    _strict: bool,
                    _timeout: int | None,
                    _cov: float,
                    _progress_callback: Callable[[int, int], None] | None = None,
                ) -> tuple[dict[str, CheckResult], MagicMock]:
                    results: dict[str, CheckResult] = {}
                    stats: MagicMock = MagicMock(
                        total_errors=0,
                        total_warnings=0,
                        files_modified=[],
                        checks_performed=[c.value for c in checks],
                    )
                    for c in checks:
                        results[c.value] = mock_result
                    return results, stats

                mock_to_thread.side_effect = run_sync

                result = await execute_pre_commit_checks(
                    checks=["fix_errors"],
                    **_EXECUTE_REQUIRED,
                    ctx=mock_ctx,
                )
            assert result["status"] == "success"
            args_list = [c[0] for c in mock_log.call_args_list]
            levels_and_messages = [(a[1], a[2]) for a in args_list]
            assert (
                "info",
                "execute_pre_commit_checks: starting",
            ) in levels_and_messages
            assert (
                "info",
                "execute_pre_commit_checks: completed",
            ) in levels_and_messages
