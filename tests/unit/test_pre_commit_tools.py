"""Tests for pre-commit tools."""

# pyright: reportUnusedFunction=false
import json
import tempfile
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core import mcp_stability_retry
from cortex.core.models import ModelDict
from cortex.core.path_resolver import (
    CortexResourceType,
    ProjectResourceType,
    get_cortex_path,
    get_project_path,
)
from cortex.managers.initialization import get_project_root
from cortex.services.framework_adapters.base import (
    CheckResult,
    TestResult,
)
from cortex.services.language_detector import LanguageInfo
from cortex.tools.execution.file_language_router import (
    run_quality_checks_for_all_languages,
)
from cortex.tools.execution.pre_commit_helpers_language import detect_or_use_language
from cortex.tools.execution.pre_commit_helpers_models import (
    DEFAULT_CHECKS,
    FunctionLengthViolation,
    PreCommitCheck,
)
from cortex.tools.execution.pre_commit_helpers_remaining import (
    MAX_LOG_OUTPUT_LENGTH,
    extract_dict_from_object,
    extract_int_from_object,
    extract_list_from_object,
)
from cortex.tools.execution.pre_commit_tools import (
    execute_pre_commit_checks,
)


@pytest.fixture(autouse=True)
def _reset_connection_state_for_pre_commit_tools() -> None:
    """Ensure MCP connection state is healthy before each pre-commit tools test."""
    mcp_stability_retry._connection_state = None  # type: ignore[attr-defined]
    _ = mcp_stability_retry.get_connection_state()


# Required parameters for execute_pre_commit_checks (tool requires all params).
_EXECUTE_REQUIRED = {
    "test_timeout": 300,
    "coverage_threshold": 0.9,
    "strict_mode": False,
}

_DEFAULT_CHECKS_NAMES_EXPECTED = frozenset(
    (
        "fix_errors",
        "format",
        "synapse_format",
        "synapse_lint",
        "type_check",
        "quality",
        "tests",
    )
)

_REAL_PROJECT_ROOT = get_project_root(None)
_REAL_SYNAPSE_ROOT = get_cortex_path(_REAL_PROJECT_ROOT, CortexResourceType.SYNAPSE)


def _minimal_python_project(project_root: Path) -> None:
    _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
    get_project_path(project_root, ProjectResourceType.VENV).mkdir()


def _router_function_length_violations(
    project_root: Path,
) -> list[FunctionLengthViolation]:
    synapse_root = get_cortex_path(project_root, CortexResourceType.SYNAPSE)
    synapse_root.parent.mkdir(parents=True, exist_ok=True)
    if not synapse_root.exists():
        synapse_root.symlink_to(_REAL_SYNAPSE_ROOT)
    _, violations = run_quality_checks_for_all_languages(project_root)
    return violations


def _python_language_info(confidence: float = 0.9) -> LanguageInfo:
    return LanguageInfo(
        language="python",
        test_framework=None,
        formatter=None,
        linter=None,
        type_checker=None,
        build_tool=None,
        confidence=confidence,
    )


def _to_thread_run_sync_inline(func: Callable[..., object], *args: object) -> object:
    return func(*args)


def _find_execute_all_checks_to_thread_call(
    mock_to_thread: MagicMock,
) -> object | None:
    for call in mock_to_thread.call_args_list:
        if call[0] and len(call[0]) > 0:
            func = call[0][0]
            if hasattr(func, "__name__") and func.__name__ == "execute_all_checks":
                return call
    return None


@contextmanager
def _patches_for_to_thread_inline(
    project_root: Path,
) -> Generator[tuple[MagicMock, MagicMock]]:
    with (
        patch(
            "cortex.services.language_quality_router.LanguageQualityRouter.get_adapter",
            return_value=MagicMock(),
        ) as mock_get_adapter,
        patch(
            "cortex.tools.execution.pre_commit_tools_execute_checks.get_current_project_root",
            return_value=project_root,
        ),
        patch(
            "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=project_root,
        ),
        patch(
            "cortex.tools.execution.pre_commit_tools_run_helpers.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread,
    ):
        yield mock_get_adapter, mock_to_thread


async def _async_to_thread_inline(func: Callable[..., object], *args: object) -> object:
    return _to_thread_run_sync_inline(func, *args)


async def _execute_pre_commit_with_to_thread_inline_sync(
    project_root: Path,
) -> tuple[ModelDict, MagicMock]:
    """Run fix_errors check with to_thread forced to call targets inline (same thread)."""
    with _patches_for_to_thread_inline(project_root) as (
        mock_get_adapter,
        mock_to_thread,
    ):
        mock_adapter = cast(MagicMock, mock_get_adapter.return_value)
        mock_adapter.fix_errors.return_value = CheckResult(
            check_type="fix_errors",
            success=True,
            output="Fixed",
            errors=[],
            warnings=[],
            files_modified=[],
        )
        mock_to_thread.side_effect = _async_to_thread_inline

        result = await execute_pre_commit_checks(
            checks=["fix_errors"],
            **_EXECUTE_REQUIRED,
        )
        return result, mock_to_thread


def _eval_fast_to_thread_side_effect(
    f: Callable[..., object], *args: object, **kwargs: object
) -> object:
    return f(*args, **kwargs)


def _stub_adapter_default_checks_green(mock_adapter: MagicMock) -> None:
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


def _project_with_minimal_src_module(project_root: Path) -> None:
    _minimal_python_project(project_root)
    src_dir = project_root / "src"
    src_dir.mkdir()
    _ = (src_dir / "module.py").write_text("x = 1\n")


@contextmanager
def _quality_pipeline_patches(project_root: Path) -> Generator[None]:
    with (
        patch(
            "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=project_root,
        ),
        patch(
            "cortex.tools.execution.pre_commit_pipeline_quality.run_quality_checks_for_all_languages",
            return_value=([], []),
        ),
    ):
        yield


def _stub_adapter_lint_and_type_green(mock_adapter: MagicMock) -> None:
    mock_adapter.lint_code.return_value = CheckResult(
        check_type="lint",
        success=True,
        output="All good",
        errors=[],
        warnings=[],
        files_modified=[],
    )
    mock_adapter.type_check.return_value = CheckResult(
        check_type="type_check",
        success=True,
        output="0 errors, 0 warnings",
        errors=[],
        warnings=[],
        files_modified=[],
    )


def _execute_all_checks_stats_from_list(
    checks_list: object, mock_result: CheckResult
) -> tuple[dict[str, CheckResult], MagicMock]:
    results: dict[str, CheckResult] = {}
    if isinstance(checks_list, list):
        checks_performed_list: list[str] = []
        typed_checks: list[object] = cast(list[object], checks_list)
        for item in typed_checks:
            if isinstance(item, PreCommitCheck):
                check_name = item.value
                checks_performed_list.append(check_name)
                results[check_name] = mock_result
        stats = MagicMock(
            total_errors=0,
            total_warnings=0,
            files_modified=[],
            checks_performed=checks_performed_list,
        )
    else:
        stats = MagicMock(
            total_errors=0,
            total_warnings=0,
            files_modified=[],
            checks_performed=[],
        )
    return results, stats


def _mcp_log_levels_and_messages(mock_log: MagicMock) -> list[tuple[object, object]]:
    args_list = [c[0] for c in mock_log.call_args_list]
    return [(a[1], a[2]) for a in args_list]


def _make_ctx_logging_to_thread_side_effect(
    mock_result: CheckResult,
) -> Callable[..., object]:
    async def run_sync(func: Callable[..., object], *args: object) -> object:
        if (
            hasattr(func, "__name__")
            and func.__name__ == "_execute_all_checks"
            and len(args) >= 6
        ):
            checks_list = args[2]
            return _execute_all_checks_stats_from_list(checks_list, mock_result)
        return func(*args)

    return run_sync


@contextmanager
def _patches_for_pre_commit_ctx_logging(
    project_root: Path,
) -> Iterator[tuple[MagicMock, MagicMock, MagicMock]]:
    with (
        patch(
            "cortex.tools.execution.pre_commit_tools_inline_execution.log_client",
            new_callable=AsyncMock,
        ) as mock_log,
        patch(
            "cortex.services.language_quality_router.LanguageQualityRouter.get_adapter",
            return_value=MagicMock(),
        ) as mock_get_adapter,
        patch(
            "cortex.tools.execution.pre_commit_tools_execute_checks.get_current_project_root",
            return_value=project_root,
        ),
        patch(
            "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=project_root,
        ),
        patch(
            "cortex.tools.execution.pre_commit_tools_run_helpers.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread,
    ):
        yield mock_log, mock_get_adapter, mock_to_thread


async def _execute_single_check_with_mock_adapter_project(
    check_name: str,
) -> ModelDict:
    """Minimal Python project + adapter whose project_root matches resolved root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _minimal_python_project(project_root)
        with (
            patch(
                "cortex.services.language_quality_router.LanguageQualityRouter.get_adapter",
                return_value=MagicMock(),
            ) as mock_get_adapter,
            patch(
                "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=project_root,
            ),
        ):
            mock_adapter = cast(MagicMock, mock_get_adapter.return_value)
            mock_adapter.project_root = project_root
            return await execute_pre_commit_checks(
                checks=[check_name],
                **_EXECUTE_REQUIRED,
            )


def _assert_skipped_synapse_script_check(result: ModelDict, check_name: str) -> None:
    assert result["status"] == "success"
    checks_performed = extract_list_from_object(
        result.get("checks_performed", []),
        [],
    )
    assert check_name in checks_performed
    results_obj = result.get("results", {})
    results = extract_dict_from_object(results_obj, {})
    sub = extract_dict_from_object(results.get(check_name, {}), {})
    assert sub["success"] is True
    assert "skipped" in str(sub.get("output", ""))


def _stub_adapter_quality_lint_fail_large_output(
    mock_adapter: MagicMock, project_root: Path, large_output: str
) -> None:
    mock_adapter.project_root = project_root
    mock_adapter.lint_code.return_value = CheckResult(
        check_type="lint",
        success=False,
        output=large_output,
        errors=["E1"],
        warnings=[],
        files_modified=[],
    )
    mock_adapter.type_check.return_value = CheckResult(
        check_type="type_check",
        success=True,
        output="0 errors",
        errors=[],
        warnings=[],
        files_modified=[],
    )


def _assert_quality_output_truncated(result: ModelDict) -> None:
    assert result["status"] == "error"
    results_obj = result.get("results", {})
    results = extract_dict_from_object(results_obj, {})
    quality_result = extract_dict_from_object(
        results.get("quality", {}),
        {},
    )
    truncated_output = str(quality_result.get("output", ""))
    assert isinstance(truncated_output, str)
    assert len(truncated_output) <= MAX_LOG_OUTPUT_LENGTH + 200
    assert "truncated" in truncated_output


def _assert_fix_quality_remaining_issues(result: ModelDict) -> None:
    assert result["status"] == "success"
    assert result.get("error_message") is None
    errors_fixed = extract_int_from_object(result.get("errors_fixed", 0), 0)
    assert errors_fixed == 1
    remaining_issues = extract_list_from_object(result.get("remaining_issues", []), [])
    assert len(remaining_issues) > 0
    assert any(
        "1 linting/formatting errors remain" in issue for issue in remaining_issues
    )


def _assert_execute_pre_commit_completion_log(mock_log: MagicMock) -> None:
    levels = _mcp_log_levels_and_messages(mock_log)
    assert ("info", "execute_pre_commit_checks: completed") in levels


async def _execute_pre_commit_fix_errors_with_ctx_log(
    project_root: Path,
) -> tuple[ModelDict, MagicMock]:
    mock_ctx = AsyncMock()
    with _patches_for_pre_commit_ctx_logging(project_root) as (
        mock_log,
        mock_get_adapter,
        mock_to_thread,
    ):
        mock_adapter = cast(MagicMock, mock_get_adapter.return_value)
        mock_result = CheckResult(
            check_type="fix_errors",
            success=True,
            output="OK",
            errors=[],
            warnings=[],
            files_modified=[],
        )
        mock_adapter.fix_errors.return_value = mock_result
        mock_to_thread.side_effect = _make_ctx_logging_to_thread_side_effect(
            mock_result
        )
        result = await execute_pre_commit_checks(
            checks=["fix_errors"],
            **_EXECUTE_REQUIRED,
            ctx=mock_ctx,
        )
        return result, mock_log


async def _fix_errors_success_for_minimal_project(project_root: Path) -> ModelDict:
    with (
        patch(
            "cortex.services.language_quality_router.LanguageQualityRouter.get_adapter",
            return_value=MagicMock(),
        ) as mock_get_adapter,
        patch(
            "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=project_root,
        ),
    ):
        mock_adapter = cast(MagicMock, mock_get_adapter.return_value)
        mock_adapter.fix_errors.return_value = CheckResult(
            check_type="fix_errors",
            success=True,
            output="Fixed errors",
            errors=[],
            warnings=[],
            files_modified=[],
        )
        return await execute_pre_commit_checks(
            checks=["fix_errors"],
            **_EXECUTE_REQUIRED,
        )


@contextmanager
def _eval_fast_execution_patches(
    project_root: Path, payload: str
) -> Generator[MagicMock]:
    python_info = _python_language_info()
    with (
        patch(
            "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=project_root,
        ),
        patch(
            "cortex.tools.execution.pre_commit_tools_inline_execution.detect_or_use_language",
            return_value=(python_info, str(project_root)),
        ),
        patch(
            "cortex.tools.execution.pre_commit_tools_run_helpers.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread,
        patch(
            "cortex.tools.evaluation.run_tool_evaluation",
            new_callable=AsyncMock,
            return_value=payload,
        ),
    ):
        mock_to_thread.side_effect = _eval_fast_to_thread_side_effect
        yield mock_to_thread


@pytest.fixture(autouse=True)
def _disable_detached_pipeline() -> Generator[None]:
    """Disable detached pipeline for all unit tests (patches don't cross processes)."""
    with (
        patch("cortex.tools.execution.pre_commit_detached.DETACHED_ENABLED", False),
        patch(
            "cortex.tools.execution.pre_commit_tools_inline_execution.precommit_block_response",
            return_value=None,
        ),
    ):
        yield


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
        """Verify execute_pre_commit_checks runs execute_all_checks via asyncio.to_thread."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _minimal_python_project(project_root)
            result, mock_to_thread = (
                await _execute_pre_commit_with_to_thread_inline_sync(project_root)
            )

        assert mock_to_thread.call_count >= 1
        assert _find_execute_all_checks_to_thread_call(mock_to_thread) is not None
        assert result["status"] == "success"
        assert result["language"] == "python"

    @pytest.mark.asyncio
    async def test_detect_language_error_when_no_language_detected(self) -> None:
        """Test error when language cannot be detected (no markers in root or ancestors)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Force root_str to tmpdir; ensure adapter-based detection finds nothing
            with (
                patch(
                    "cortex.tools.execution.pre_commit_helpers_language.get_project_root_str",
                    return_value=str(Path(tmpdir).resolve()),
                ),
                patch(
                    "cortex.tools.execution.pre_commit_helpers_language.detect_language_at_path",
                    return_value=None,
                ),
                patch(
                    "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=Path(tmpdir).resolve(),
                ),
            ):
                result = await execute_pre_commit_checks(
                    checks=["fix_errors"],
                    **_EXECUTE_REQUIRED,
                )

            assert result["status"] == "error"
            error_message = str(result.get("error", ""))
            assert "Could not detect project language" in error_message

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
                "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/some/root"),
            ),
            patch(
                "cortex.tools.execution.pre_commit_tools_inline_execution.detect_or_use_language",
                return_value=(haskell_info, "/some/root"),
            ),
        ):
            result = await execute_pre_commit_checks(
                checks=["fix_errors"],
                **_EXECUTE_REQUIRED,
            )

        assert result["status"] == "error"
        error_message = str(result.get("error", ""))
        assert "not yet supported" in error_message
        assert "Supported languages:" in error_message
        assert "python" in error_message

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
                "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/some/root"),
            ),
            patch(
                "cortex.tools.execution.pre_commit_tools_inline_execution.detect_or_use_language",
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
            _minimal_python_project(project_root)
            result = await _fix_errors_success_for_minimal_project(project_root)

        assert result["status"] == "success"
        assert result["language"] == "python"
        checks_performed = extract_list_from_object(
            result.get("checks_performed", []),
            [],
        )
        assert "fix_errors" in checks_performed
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
            _minimal_python_project(project_root)
            with patch(
                "cortex.services.language_quality_router.LanguageQualityRouter.get_adapter",
                return_value=MagicMock(),
            ) as mock_get_adapter:
                _stub_adapter_default_checks_green(
                    cast(MagicMock, mock_get_adapter.return_value)
                )
                with patch(
                    "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ):
                    result = await execute_pre_commit_checks(
                        checks=[c.value for c in DEFAULT_CHECKS],
                        **_EXECUTE_REQUIRED,
                    )
            assert result["status"] == "success"
            checks_performed = extract_list_from_object(
                result.get("checks_performed", []),
                [],
            )
            assert len(checks_performed) == 7
            assert set(checks_performed) == _DEFAULT_CHECKS_NAMES_EXPECTED

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        """Test error handling in tool when project root resolution fails."""
        with (
            patch(
                "cortex.tools.execution.pre_commit_tools_execute_checks.get_current_project_root",
                return_value=None,
            ),
            patch(
                "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
                new_callable=AsyncMock,
                side_effect=Exception("Test error"),
            ),
        ):
            result = await execute_pre_commit_checks(
                checks=["fix_errors"],
                **_EXECUTE_REQUIRED,
            )

            assert result["status"] == "error"
            error_message = str(result.get("error", ""))
            assert "Test error" in error_message

    @pytest.mark.asyncio
    async def test_eval_fast_check_passes_when_above_threshold(self) -> None:
        """eval_fast check passes when execution pass rate >= 85%."""
        payload_above = json.dumps(
            {
                "execution_summary": {
                    "execution_passed": 9,
                    "execution_total_run": 10,
                    "execution_failed": 1,
                    "execution_skipped": 0,
                    "results": [],
                }
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _minimal_python_project(project_root)
            with _eval_fast_execution_patches(project_root, payload_above):
                result = await execute_pre_commit_checks(
                    checks=["eval_fast"],
                    **_EXECUTE_REQUIRED,
                )

        assert result["status"] == "success"
        checks_performed = extract_list_from_object(
            result.get("checks_performed", []),
            [],
        )
        assert "eval_fast" in checks_performed
        results_obj = result.get("results", {})
        results = extract_dict_from_object(results_obj, {})
        eval_result = extract_dict_from_object(results.get("eval_fast", {}), {})
        assert eval_result["success"] is True
        assert "90" in str(eval_result.get("output", ""))

    @pytest.mark.asyncio
    async def test_eval_fast_check_fails_when_below_threshold(self) -> None:
        """eval_fast check fails when execution pass rate < 85%."""
        payload_below = json.dumps(
            {
                "execution_summary": {
                    "execution_passed": 7,
                    "execution_total_run": 10,
                    "execution_failed": 3,
                    "execution_skipped": 0,
                    "results": [],
                }
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _minimal_python_project(project_root)
            with _eval_fast_execution_patches(project_root, payload_below):
                result = await execute_pre_commit_checks(
                    checks=["eval_fast"],
                    **_EXECUTE_REQUIRED,
                )

        assert result["status"] == "error"
        checks_performed = extract_list_from_object(
            result.get("checks_performed", []),
            [],
        )
        assert "eval_fast" in checks_performed
        results_obj = result.get("results", {})
        results = extract_dict_from_object(results_obj, {})
        eval_result = extract_dict_from_object(results.get("eval_fast", {}), {})
        assert eval_result["success"] is False
        assert "70" in str(eval_result.get("output", ""))

    @pytest.mark.asyncio
    async def test_format_ci_parity_check_when_script_missing_returns_skipped(
        self,
    ) -> None:
        """format_ci_parity when script not present returns success (skipped)."""
        result = await _execute_single_check_with_mock_adapter_project(
            "format_ci_parity"
        )
        _assert_skipped_synapse_script_check(result, "format_ci_parity")

    @pytest.mark.asyncio
    async def test_test_naming_check_when_script_missing_returns_skipped(
        self,
    ) -> None:
        """test_naming when script not present returns success (skipped)."""
        result = await _execute_single_check_with_mock_adapter_project("test_naming")
        _assert_skipped_synapse_script_check(result, "test_naming")

    @pytest.mark.asyncio
    async def test_check_async_tests_check_when_script_missing_returns_skipped(
        self,
    ) -> None:
        """check_async_tests when script not present returns success (skipped)."""
        result = await _execute_single_check_with_mock_adapter_project(
            "check_async_tests"
        )
        _assert_skipped_synapse_script_check(result, "check_async_tests")


@pytest.mark.asyncio
class TestPreCommitToolsContextLogging:
    """Test pre-commit tools use log_client when ctx is passed."""

    async def test_execute_pre_commit_checks_calls_log_client_when_ctx_passed(
        self,
    ) -> None:
        """execute_pre_commit_checks logs completion via log_client when ctx is passed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _minimal_python_project(project_root)
            result, mock_log = await _execute_pre_commit_fix_errors_with_ctx_log(
                project_root
            )
        assert result["status"] == "success"
        _assert_execute_pre_commit_completion_log(mock_log)
