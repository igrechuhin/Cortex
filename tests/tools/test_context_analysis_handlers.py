import json
from unittest.mock import MagicMock, patch

import pytest

from cortex.tools.context_analysis_handlers import (
    analyze_context_effectiveness_resource,
    get_context_usage_statistics_resource,
)


@pytest.mark.asyncio
@pytest.mark.timeout(60)
class TestContextAnalysisResources:
    """Test Phase 43 context analysis resources (cortex://optimization/...)."""

    async def test_analyze_context_effectiveness_resource_returns_json(self) -> None:
        """analyze_context_effectiveness_resource returns JSON (Phase 43)."""
        analysis_result = MagicMock(
            model_dump=MagicMock(return_value={"status": "success"})
        )
        with patch(
            "cortex.tools.context_analysis_handlers.analyze_current_session",
            return_value=analysis_result,
        ):
            result_str = await analyze_context_effectiveness_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"

    async def test_get_context_usage_statistics_resource_returns_json(self) -> None:
        """get_context_usage_statistics_resource returns JSON (Phase 43)."""
        stats_result = MagicMock(
            model_dump=MagicMock(return_value={"status": "success"})
        )
        with patch(
            "cortex.tools.context_analysis_handlers.get_context_statistics",
            return_value=stats_result,
        ):
            result_str = await get_context_usage_statistics_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"
