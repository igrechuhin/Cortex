"""Tests for cortex://analysis resource (zero-arg session config + truncation defaults)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.context.analysis_operations import analyze


@pytest.mark.timeout(20)
class TestAnalyzeResource:
    """Test analyze resource (Phase 43 Phase 5 Analysis resource)."""

    @pytest.mark.asyncio
    async def test_analyze_returns_json_for_valid_target(self, tmp_path: Path) -> None:
        """analyze returns valid JSON (zero-arg, reads session config)."""
        _ = tmp_path
        with (
            patch(
                "cortex.core.session_config.read_session_config",
                return_value={"analysis_target": "structure"},
            ),
            patch(
                "cortex.tools.context.analysis_operations.analyze_impl",
                new_callable=AsyncMock,
                return_value=json.dumps(
                    {"status": "success", "target": "structure", "analysis": {}},
                    indent=2,
                ),
            ),
        ):
            result = await analyze()
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "structure"

    @pytest.mark.asyncio
    async def test_analyze_default_target_is_context(self) -> None:
        """analyze defaults to 'context' and passes truncation caps for resource reads."""
        with (
            patch(
                "cortex.core.session_config.read_session_config",
                return_value={},
            ),
            patch(
                "cortex.tools.context.analysis_operations.analyze_impl",
                new_callable=AsyncMock,
                return_value=json.dumps({"status": "success", "target": "context"}),
            ) as mock_analyze,
        ):
            result = await analyze()
        mock_analyze.assert_called_once_with(
            target="context",
            time_window_days=None,
            export_format="json",
            categories=None,
            max_sessions=3,
            max_calls_per_session=10,
        )
        assert json.loads(result)["status"] == "success"
