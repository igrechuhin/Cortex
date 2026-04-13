"""Adapter registry and fix-quality tests extracted from test_pre_commit_tools."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.models import ModelDict
from cortex.services.framework_adapters.base import FrameworkAdapter
from cortex.services.language_detector import LanguageInfo
from cortex.services.language_quality_router import LanguageQualityRouter
from cortex.tools.execution.pre_commit_helpers_remaining import (
    extract_int_from_object,
    extract_list_from_object,
)
from cortex.tools.execution.pre_commit_tools import (
    SUPPORTED_LANGUAGES,
    execute_pre_commit_checks,
)

_EXECUTE_REQUIRED = {
    "test_timeout": 300,
    "coverage_threshold": 0.9,
    "strict_mode": False,
}


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


class TestAdapterRegistry:
    def test_supported_languages_includes_python(self) -> None:
        assert "python" in SUPPORTED_LANGUAGES
        assert len(SUPPORTED_LANGUAGES) >= 1

    def test_get_adapter_returns_adapter_for_python(self) -> None:
        info = LanguageInfo(
            language="python",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=1.0,
        )
        adapter = LanguageQualityRouter.get_adapter(info.language, None)
        assert adapter is not None
        assert isinstance(adapter, FrameworkAdapter)

    def test_get_adapter_returns_none_for_unsupported_language(self) -> None:
        info = LanguageInfo(
            language="haskell",
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )
        adapter = LanguageQualityRouter.get_adapter(info.language, "/some/root")
        assert adapter is None

    def test_supported_languages_includes_stub_languages(self) -> None:
        for lang in (
            "typescript",
            "javascript",
            "rust",
            "go",
            "java",
            "swift",
            "kotlin",
            "csharp",
        ):
            assert lang in SUPPORTED_LANGUAGES
        assert len(SUPPORTED_LANGUAGES) == 9


class TestFixQualityCheck:
    def _make_success_json(
        self,
        errors_fixed: int = 0,
        warnings_fixed: int = 0,
        formatting_issues_fixed: int = 0,
        type_errors_fixed: int = 0,
        markdown_issues_fixed: int = 0,
        files_modified: list[str] | None = None,
        remaining_issues: list[str] | None = None,
    ) -> str:
        from cortex.tools.execution.pre_commit_fix_quality import (
            build_quality_response_json,
        )

        return build_quality_response_json(
            errors_fixed=errors_fixed,
            warnings_fixed=warnings_fixed,
            formatting_issues_fixed=formatting_issues_fixed,
            markdown_issues_fixed=markdown_issues_fixed,
            type_errors_fixed=type_errors_fixed,
            files_modified=files_modified or [],
            remaining_issues=remaining_issues or [],
        )

    @pytest.mark.asyncio
    async def test_fix_quality_error_path(self) -> None:
        from cortex.tools.execution.pre_commit_fix_quality import (
            create_quality_error_response,
        )

        error_json = create_quality_error_response("Test error")
        with patch(
            "cortex.tools.execution.pre_commit_tools_execute_checks.autofix_impl",
            new_callable=AsyncMock,
            return_value=error_json,
        ):
            with patch(
                "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ):
                result = await execute_pre_commit_checks(
                    checks=["fix_quality"], **_EXECUTE_REQUIRED
                )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_fix_quality_success_when_checks_report_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            fix_json = self._make_success_json(
                errors_fixed=1,
                files_modified=["file1.py"],
                remaining_issues=["1 linting/formatting errors remain"],
            )
            with (
                patch(
                    "cortex.tools.execution.pre_commit_tools_execute_checks.autofix_impl",
                    new_callable=AsyncMock,
                    return_value=fix_json,
                ),
                patch(
                    "cortex.tools.execution.pre_commit_tools_execute_checks.get_or_resolve_project_root",
                    new_callable=AsyncMock,
                    return_value=project_root,
                ),
            ):
                result = await execute_pre_commit_checks(
                    checks=["fix_quality"], **_EXECUTE_REQUIRED
                )

            _assert_fix_quality_remaining_issues(result)
