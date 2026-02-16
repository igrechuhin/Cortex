import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.tools.context_analysis_handlers import (
    _analyze_context_effectiveness_impl,  # type: ignore[reportPrivateUsage]
    analyze_context_effectiveness,
    analyze_context_effectiveness_resource,
    get_context_usage_statistics,
    get_context_usage_statistics_resource,
)


@pytest.mark.asyncio
@pytest.mark.timeout(60)
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
                "cortex.tools.context_analysis_handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.context_analysis_handlers.analyze_current_session",
                return_value=analysis_result,
            ),
        ):
            # Act
            result_str = await analyze_context_effectiveness(analyze_all_sessions=False)
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
                "cortex.tools.context_analysis_handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.context_analysis_handlers.analyze_session_logs",
                return_value=analysis_result,
            ),
        ):
            # Act
            result_str = await analyze_context_effectiveness(analyze_all_sessions=True)
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
                "cortex.tools.context_analysis_handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.context_analysis_handlers.get_context_statistics",
                return_value=stats_result,
            ),
        ):
            # Act
            result_str = await get_context_usage_statistics()
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "success"

    async def test_analyze_context_effectiveness_when_exception_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        with patch(
            "cortex.tools.context_analysis_handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            # Act
            result_str = await analyze_context_effectiveness(analyze_all_sessions=False)
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
            "cortex.tools.context_analysis_handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            # Act
            result_str = await get_context_usage_statistics()
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert result["error"] == "boom"
        assert result["error_type"] == "RuntimeError"


@pytest.mark.asyncio
@pytest.mark.timeout(60)
class TestContextAnalysisContextLogging:
    """Test context analysis handlers use log_client when ctx is passed."""

    async def test_analyze_context_effectiveness_calls_log_client_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, analyze_context_effectiveness logs start and completion."""
        mock_ctx = AsyncMock()
        analysis_result = MagicMock(
            model_dump=MagicMock(return_value={"status": "success"})
        )
        with (
            patch(
                "cortex.tools.context_analysis_handlers.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.context_analysis_handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.context_analysis_handlers.analyze_current_session",
                return_value=analysis_result,
            ),
        ):
            result_str = await analyze_context_effectiveness(
                analyze_all_sessions=False,
                ctx=mock_ctx,
            )
            result = json.loads(result_str)
        assert result["status"] == "success"
        args_list = [c[0] for c in mock_log.call_args_list]
        levels_and_messages = [(a[1], a[2]) for a in args_list]
        assert (
            "info",
            "analyze_context_effectiveness: starting",
        ) in levels_and_messages
        assert (
            "info",
            "analyze_context_effectiveness: completed",
        ) in levels_and_messages


@pytest.mark.asyncio
@pytest.mark.timeout(60)
class TestContextAnalysisResources:
    """Test Phase 43 context analysis resources (cortex://optimization/...)."""

    async def test_analyze_context_effectiveness_resource_returns_json(
        self, tmp_path: Path
    ) -> None:
        """analyze_context_effectiveness_resource returns JSON (Phase 43)."""
        analysis_result = MagicMock(
            model_dump=MagicMock(return_value={"status": "success"})
        )
        with (
            patch(
                "cortex.tools.context_analysis_handlers.analyze_context_effectiveness",
                new_callable=AsyncMock,
                return_value=json.dumps(analysis_result.model_dump()),
            ),
        ):
            result_str = await analyze_context_effectiveness_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"

    async def test_get_context_usage_statistics_resource_returns_json(
        self, tmp_path: Path
    ) -> None:
        """get_context_usage_statistics_resource returns JSON (Phase 43)."""
        stats_result = MagicMock(
            model_dump=MagicMock(return_value={"status": "success"})
        )
        with (
            patch(
                "cortex.tools.context_analysis_handlers.get_context_usage_statistics",
                new_callable=AsyncMock,
                return_value=json.dumps(stats_result.model_dump()),
            ),
        ):
            result_str = await get_context_usage_statistics_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"


@pytest.mark.asyncio
@pytest.mark.timeout(60)
class TestAnalyzeContextEffectivenessImpl:
    """Test _analyze_context_effectiveness_impl function directly."""

    def test_analyze_context_effectiveness_impl_current_session(
        self, tmp_path: Path
    ) -> None:
        """Test _analyze_context_effectiveness_impl with current session."""
        analysis_result = MagicMock(
            model_dump=MagicMock(
                return_value={"status": "success", "sessions_analyzed": 1}
            )
        )
        with patch(
            "cortex.tools.context_analysis_handlers.analyze_current_session",
            return_value=analysis_result,
        ):
            result_str = _analyze_context_effectiveness_impl(
                tmp_path, analyze_all_sessions=False
            )
            result = json.loads(result_str)
        assert result["status"] == "success"

    def test_analyze_context_effectiveness_impl_all_sessions(
        self, tmp_path: Path
    ) -> None:
        """Test _analyze_context_effectiveness_impl with all sessions."""
        analysis_result = MagicMock(
            model_dump=MagicMock(
                return_value={"status": "success", "sessions_analyzed": 5}
            )
        )
        with patch(
            "cortex.tools.context_analysis_handlers.analyze_session_logs",
            return_value=analysis_result,
        ):
            result_str = _analyze_context_effectiveness_impl(
                tmp_path, analyze_all_sessions=True
            )
            result = json.loads(result_str)
        assert result["status"] == "success"

    def test_analyze_context_effectiveness_impl_raises_exception(
        self, tmp_path: Path
    ) -> None:
        """Test _analyze_context_effectiveness_impl when underlying function raises."""
        with patch(
            "cortex.tools.context_analysis_handlers.analyze_current_session",
            side_effect=ValueError("Test error"),
        ):
            with pytest.raises(ValueError, match="Test error"):
                _ = _analyze_context_effectiveness_impl(
                    tmp_path, analyze_all_sessions=False
                )
