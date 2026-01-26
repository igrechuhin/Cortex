import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.tools.context_analysis_handlers import (
    analyze_context_effectiveness,
    get_context_usage_statistics,
)


@pytest.mark.asyncio
class TestContextAnalysisHandlers:
    async def test_analyze_context_effectiveness_when_current_session_returns_success(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        analysis_result = MagicMock(
            model_dump=MagicMock(return_value={"status": "success"})
        )
        with (
            patch(
                "cortex.tools.context_analysis_handlers.phase4_opt.get_project_root",
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.context_analysis_handlers.analyze_current_session",
                return_value=analysis_result,
            ),
        ):
            # Act
            result_str = await analyze_context_effectiveness(
                project_root=str(tmp_path), analyze_all_sessions=False
            )
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "success"

    async def test_analyze_context_effectiveness_when_all_sessions_returns_success(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        analysis_result = MagicMock(
            model_dump=MagicMock(return_value={"status": "success"})
        )
        with (
            patch(
                "cortex.tools.context_analysis_handlers.phase4_opt.get_project_root",
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.context_analysis_handlers.analyze_session_logs",
                return_value=analysis_result,
            ),
        ):
            # Act
            result_str = await analyze_context_effectiveness(
                project_root=str(tmp_path), analyze_all_sessions=True
            )
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "success"

    async def test_get_context_usage_statistics_returns_success(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        stats_result = MagicMock(
            model_dump=MagicMock(return_value={"status": "success"})
        )
        with (
            patch(
                "cortex.tools.context_analysis_handlers.phase4_opt.get_project_root",
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.context_analysis_handlers.get_context_statistics",
                return_value=stats_result,
            ),
        ):
            # Act
            result_str = await get_context_usage_statistics(project_root=str(tmp_path))
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "success"

    async def test_analyze_context_effectiveness_when_exception_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        with patch(
            "cortex.tools.context_analysis_handlers.phase4_opt.get_project_root",
            side_effect=RuntimeError("boom"),
        ):
            # Act
            result_str = await analyze_context_effectiveness(
                project_root=str(tmp_path), analyze_all_sessions=False
            )
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert result["error"] == "boom"
        assert result["error_type"] == "RuntimeError"

    async def test_get_context_usage_statistics_when_exception_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        with patch(
            "cortex.tools.context_analysis_handlers.phase4_opt.get_project_root",
            side_effect=RuntimeError("boom"),
        ):
            # Act
            result_str = await get_context_usage_statistics(project_root=str(tmp_path))
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert result["error"] == "boom"
        assert result["error_type"] == "RuntimeError"
