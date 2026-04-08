"""Tests for cortex://analysis resource (zero-arg session config + truncation defaults)."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.analysis.token_budget import TokenBudgetEntry
from cortex.tools.context.analysis_operations import analyze


@contextmanager
def _structure_target_and_token_budget(tmp_path: Path) -> Iterator[None]:
    """Patches for analyze() when session target is structure."""
    entry = TokenBudgetEntry(path="CLAUDE.md", word_count=10, is_candidate=False)
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
        patch(
            "cortex.tools.context.analysis_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.context.analysis_operations.compute_token_budget",
            return_value=[entry],
        ),
    ):
        yield None


@pytest.mark.timeout(20)
class TestAnalyzeResource:
    """Test analyze resource (Phase 43 Phase 5 Analysis resource)."""

    @pytest.mark.asyncio
    async def test_analyze_returns_json_for_valid_target(self, tmp_path: Path) -> None:
        """analyze returns valid JSON (zero-arg, reads session config)."""
        with _structure_target_and_token_budget(tmp_path):
            result = await analyze()
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "structure"
        assert "token_budget" in result_data
        assert "## Token Budget" in result_data["token_budget"]["markdown"]

    @pytest.mark.asyncio
    async def test_analyze_default_target_is_context(self, tmp_path: Path) -> None:
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
            patch(
                "cortex.tools.context.analysis_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.context.analysis_operations.compute_token_budget",
                return_value=[],
            ),
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
