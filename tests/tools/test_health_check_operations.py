"""Tests for health_check_operations MCP tool."""

import json
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.session.health_check_operations import (
    analyze_health_check,
    analyze_health_check_resource,
    empty_prompt_result,
    empty_rule_result,
    empty_tool_result,
    get_project_root,
    run_health_check_analysis,
)


@contextmanager
def _temp_project() -> Generator[Path]:
    """Yield a temporary project path with .cortex/synapse layout."""
    with tempfile.TemporaryDirectory() as tmp:
        path: Path = Path(tmp)
        synapse_dir = get_cortex_path(path, CortexResourceType.SYNAPSE)
        (synapse_dir / "prompts").mkdir(parents=True)
        (synapse_dir / "rules" / "general").mkdir(parents=True)
        (path / "src" / "cortex" / "tools").mkdir(parents=True)
        yield path


class TestGetProjectRoot:
    """Tests for get_project_root."""

    def test_get_project_root_returns_path(self) -> None:
        """get_project_root with None uses resolver default."""
        with _temp_project() as root:
            with patch(
                "cortex.tools.session.health_check_operations._get_project_root",
                return_value=root,
            ):
                result = get_project_root(None)
            assert result == root

    def test_get_project_root_with_string_passes_through(self) -> None:
        """get_project_root with string passes to resolver."""
        with _temp_project() as root:
            with patch(
                "cortex.tools.session.health_check_operations._get_project_root",
                return_value=root,
            ):
                result = get_project_root(str(root))
            assert result == root


class TestEmptyResults:
    """Tests for empty result helpers."""

    def test_empty_prompt_result_has_zero_total(self) -> None:
        """empty_prompt_result returns total=0 and empty lists."""
        r = empty_prompt_result()
        assert r["total"] == 0
        assert r["merge_opportunities"] == []
        assert r["optimization_opportunities"] == []

    def test_empty_rule_result_has_zero_total(self) -> None:
        """empty_rule_result returns total=0 and empty categories."""
        r = empty_rule_result()
        assert r["total"] == 0
        assert r["categories"] == []
        assert r["merge_opportunities"] == []
        assert r["optimization_opportunities"] == []

    def test_empty_tool_result_has_zero_total(self) -> None:
        """empty_tool_result returns total=0 and empty lists."""
        r = empty_tool_result()
        assert r["total"] == 0
        assert r["merge_opportunities"] == []
        assert r["optimization_opportunities"] == []
        assert r["consolidation_opportunities"] == []


class TestRunHealthCheckAnalysis:
    """Tests for run_health_check_analysis."""

    @pytest.mark.asyncio
    async def test_returns_valid_json_with_prompts_only(self) -> None:
        """Analysis type prompts returns JSON with prompts section."""
        with _temp_project() as root:
            result = await run_health_check_analysis(
                analysis_type="prompts",
                similarity_threshold=0.75,
                include_dependencies=False,
                validate_quality=False,
                project_root=root,
            )
            data = json.loads(result)
            assert data["status"] == "success"
            assert data["analysis_type"] == "prompts"
            assert "prompts" in data
            assert "rules" in data
            assert "tools" in data
            assert data["rules"]["total"] == 0
            assert data["tools"]["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_valid_json_with_all_types(self) -> None:
        """Analysis type all returns JSON with all sections."""
        with _temp_project() as root:
            result = await run_health_check_analysis(
                analysis_type="all",
                similarity_threshold=0.75,
                include_dependencies=False,
                validate_quality=False,
                project_root=root,
            )
            data = json.loads(result)
            assert data["status"] == "success"
            assert data["analysis_type"] == "all"
            assert "prompts" in data
            assert "rules" in data
            assert "tools" in data
            assert "recommendations" in data

    @pytest.mark.asyncio
    async def test_include_dependencies_adds_prompt_deps_when_prompts_analyzed(
        self,
    ) -> None:
        """When include_dependencies and prompts analyzed, report has prompt_dependencies."""
        with _temp_project() as root:
            result = await run_health_check_analysis(
                analysis_type="prompts",
                similarity_threshold=0.75,
                include_dependencies=True,
                validate_quality=False,
                project_root=root,
            )
            data = json.loads(result)
            assert "prompt_dependencies" in data
            assert isinstance(data["prompt_dependencies"], dict)

    @pytest.mark.asyncio
    async def test_validate_quality_true_runs_quality_validator(self) -> None:
        """When validate_quality=True, quality validator is applied to opportunities."""
        with _temp_project() as root:
            result = await run_health_check_analysis(
                analysis_type="all",
                similarity_threshold=0.75,
                include_dependencies=False,
                validate_quality=True,
                project_root=root,
            )
            data = json.loads(result)
            assert data["status"] == "success"
            assert "recommendations" in data


class TestAnalyzeHealthCheck:
    """Tests for analyze_health_check MCP tool."""

    @pytest.mark.asyncio
    async def test_analyze_health_check_returns_success_json(self) -> None:
        """analyze_health_check returns valid JSON with status success."""
        mock_report = json.dumps(
            {
                "status": "success",
                "analysis_type": "prompts",
                "prompts": empty_prompt_result().model_dump(),
                "rules": empty_rule_result().model_dump(),
                "tools": empty_tool_result().model_dump(),
                "recommendations": [],
            },
            indent=2,
        )
        with patch(
            "cortex.tools.session.health_check_operations.run_health_check_analysis",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            result_str = await analyze_health_check(
                analysis_type="prompts",
                similarity_threshold=0.75,
                include_dependencies=False,
                validate_quality=False,
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["analysis_type"] == "prompts"
        assert "prompts" in result
        assert "rules" in result
        assert "tools" in result

    @pytest.mark.asyncio
    async def test_analyze_health_check_resolves_root_via_resolver(self) -> None:
        """analyze_health_check uses resolve_project_root_async for root."""
        with _temp_project() as root:
            with patch(
                "cortex.tools.session.health_check_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                result_str = await analyze_health_check(
                    analysis_type="tools",
                    similarity_threshold=0.75,
                    include_dependencies=False,
                    validate_quality=False,
                )
            result = json.loads(result_str)
            assert result["status"] == "success"
            assert result["analysis_type"] == "tools"
            assert result["tools"]["total"] >= 0


@pytest.mark.asyncio
@pytest.mark.timeout(15)
class TestAnalyzeHealthCheckResource:
    """Tests for analyze_health_check_resource (Phase 43 cortex://health/analyze)."""

    @pytest.mark.timeout(15)
    async def test_analyze_health_check_resource_returns_json(self) -> None:
        """analyze_health_check_resource returns JSON (Phase 43)."""
        success_json = json.dumps(
            {
                "status": "success",
                "analysis_type": "all",
                "prompts": {"total": 0},
                "rules": {"total": 0},
                "tools": {"total": 0},
                "recommendations": [],
            },
            indent=2,
        )
        with _temp_project() as root:
            with (
                patch(
                    "cortex.tools.session.health_check_operations.resolve_project_root_async",
                    new_callable=AsyncMock,
                    return_value=root,
                ),
                patch(
                    "cortex.tools.session.health_check_operations.run_health_check_analysis",
                    new_callable=AsyncMock,
                    return_value=success_json,
                ),
            ):
                result_str = await analyze_health_check_resource(analysis_type="all")
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["analysis_type"] == "all"
