"""Tests for script_capture_tools MCP handlers."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.script_capture_tools import (
    analyze_session_scripts,
    analyze_session_scripts_resource,
    capture_session_script,
    list_session_scripts,
    list_session_scripts_resource,
    manage_session_scripts,
    promote_session_script,
    suggest_tool_improvements,
    suggest_tool_improvements_resource,
)


class TestCaptureSessionScript:
    """Tests for capture_session_script MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_success_with_script_id_and_timestamp(self) -> None:
        """capture_session_script returns JSON with status, script_id, timestamp."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "cortex.tools.script_capture_tools.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                result = await capture_session_script(
                    script_path="scripts/foo.py",
                    script_content="print(1)",
                    task_description="Test",
                )
                data = json.loads(result)
            assert data["status"] == "success"
            assert "script_id" in data
            assert "timestamp" in data
            assert "message" in data
            assert "Captured script" in data["message"]

    @pytest.mark.asyncio
    async def test_persists_capture_so_list_returns_it(self) -> None:
        """Captured script appears in list_session_scripts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "cortex.tools.script_capture_tools.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                capture_result = await capture_session_script(
                    script_path="bar.py",
                    script_content="x = 1",
                    task_description="Bar task",
                    script_type="python",
                )
                capture_data = json.loads(capture_result)
                script_id = capture_data["script_id"]
                list_result = await list_session_scripts()
                list_data = json.loads(list_result)
            assert list_data["status"] == "success"
            assert list_data["count"] == 1
            assert len(list_data["scripts"]) == 1
            assert list_data["scripts"][0]["script_id"] == script_id
            assert list_data["scripts"][0]["script_path"] == "bar.py"


class TestListSessionScripts:
    """Tests for list_session_scripts MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_success_with_count_and_scripts_list(self) -> None:
        """list_session_scripts returns JSON with status, count, scripts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "cortex.tools.script_capture_tools.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                result = await list_session_scripts()
                data = json.loads(result)
            assert data["status"] == "success"
            assert data["count"] == 0
            assert data["scripts"] == []

    @pytest.mark.asyncio
    async def test_returns_captured_scripts_in_list(self) -> None:
        """list_session_scripts returns summaries of previously captured scripts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "cortex.tools.script_capture_tools.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                _ = await capture_session_script(
                    script_path="a.py",
                    script_content="a",
                    task_description="A",
                )
                _ = await capture_session_script(
                    script_path="b.sh",
                    script_content="b",
                    task_description="B",
                    script_type="shell",
                )
                result = await list_session_scripts()
                data = json.loads(result)
            assert data["status"] == "success"
            assert data["count"] == 2
            paths = {s["script_path"] for s in data["scripts"]}
            assert paths == {"a.py", "b.sh"}
            shell_script = next(
                s for s in data["scripts"] if s["script_path"] == "b.sh"
            )
            assert shell_script["script_type"] == "shell"


class TestAnalyzeSessionScripts:
    """Tests for analyze_session_scripts MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_success_with_count_and_analyses(self) -> None:
        """analyze_session_scripts returns JSON with status, count, analyses."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "cortex.tools.script_capture_tools.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                result = await analyze_session_scripts()
                data = json.loads(result)
            assert data["status"] == "success"
            assert "count" in data
            assert "analyses" in data
            assert data["count"] == len(data["analyses"])

    @pytest.mark.asyncio
    async def test_analyzes_captured_scripts(self) -> None:
        """analyze_session_scripts returns analysis for each captured script."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "cortex.tools.script_capture_tools.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                _ = await capture_session_script(
                    script_path="foo.py",
                    script_content="def main(): pass",
                    task_description="Format code",
                )
                result = await analyze_session_scripts()
                data = json.loads(result)
            assert data["status"] == "success"
            assert data["count"] == 1
            analysis = data["analyses"][0]
            assert "script_id" in analysis
            assert "use_case_label" in analysis
            assert "gap_reason" in analysis
            assert "promotion_potential" in analysis


class TestSuggestToolImprovements:
    """Tests for suggest_tool_improvements MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_success_with_recommendations(self) -> None:
        """suggest_tool_improvements returns JSON with status and recommendations."""
        with tempfile.TemporaryDirectory():
            result = await suggest_tool_improvements(
                task_description="format Python files",
                max_results=5,
            )
            data = json.loads(result)
            assert data["status"] == "success"
            assert "recommendations" in data
            assert "task_description" in data
            for rec in data["recommendations"]:
                assert "name" in rec
                assert "type" in rec
                assert "score" in rec


class TestPromoteSessionScript:
    """Tests for promote_session_script MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_error_when_script_not_found(self) -> None:
        """promote_session_script returns error when script_id not found."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "cortex.tools.script_capture_tools.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                result = await promote_session_script(
                    script_id="nonexistent-id",
                )
            data = json.loads(result)
            assert data["status"] == "error"
            assert "not found" in data.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_returns_validation_and_template_when_script_exists(self) -> None:
        """promote_session_script returns validation and template for existing script."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "cortex.tools.script_capture_tools.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                cap = await capture_session_script(
                    script_path="format.py",
                    script_content="def main(): pass",
                    task_description="Format code",
                )
                cap_data = json.loads(cap)
                script_id = cap_data["script_id"]
                result = await promote_session_script(
                    script_id=script_id,
                    output_type="tool",
                )
            data = json.loads(result)
            assert data["status"] == "success"
            assert data["script_id"] == script_id
            assert "validation_passed" in data
            assert "quality_score" in data
            assert "template_content" in data


@pytest.mark.asyncio
class TestSessionScriptsDispatcher:
    """Tests for consolidated manage_session_scripts MCP tool dispatcher."""

    async def test_capture_operation_dispatches_to_capture_session_script(
        self,
    ) -> None:
        """manage_session_scripts('capture', ...) forwards to capture_session_script."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "cortex.tools.script_capture_tools.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ):
                result = await manage_session_scripts(
                    operation="capture",
                    script_path="scripts/foo.py",
                    script_content="print(1)",
                    task_description="Test capture",
                )
        data = json.loads(result)
        assert data["status"] == "success"
        assert "script_id" in data

    async def test_list_operation_dispatches_to_list_session_scripts(self) -> None:
        """manage_session_scripts('list') forwards to list_session_scripts."""
        payload = json.dumps(
            {"status": "success", "count": 0, "scripts": []},
            indent=2,
        )
        with patch(
            "cortex.tools.script_capture_tools.list_session_scripts",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mocked_list:
            result = await manage_session_scripts(operation="list")
        mocked_list.assert_awaited_once()
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["count"] == 0

    async def test_analyze_operation_dispatches_to_analyze_session_scripts(
        self,
    ) -> None:
        """manage_session_scripts('analyze') forwards to analyze_session_scripts."""
        payload = json.dumps(
            {"status": "success", "count": 0, "analyses": []},
            indent=2,
        )
        with patch(
            "cortex.tools.script_capture_tools.analyze_session_scripts",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mocked_analyze:
            result = await manage_session_scripts(operation="analyze")
        mocked_analyze.assert_awaited_once()
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["count"] == 0

    async def test_suggest_operation_requires_task_description(self) -> None:
        """manage_session_scripts('suggest') without task_description returns error."""
        result = await manage_session_scripts(operation="suggest")
        data = json.loads(result)
        assert data["status"] == "error"
        assert "task_description is required" in data["error"]

    async def test_promote_operation_requires_script_id(self) -> None:
        """manage_session_scripts('promote') without script_id returns error."""
        result = await manage_session_scripts(operation="promote")
        data = json.loads(result)
        assert data["status"] == "error"
        assert "script_id is required" in data["error"]

    async def test_unknown_operation_returns_error(self) -> None:
        """manage_session_scripts with unknown operation returns error."""
        result = await manage_session_scripts(operation="unknown-op")
        data = json.loads(result)
        assert data["status"] == "error"
        assert "Unsupported operation" in data["error"]


@pytest.mark.asyncio
class TestScriptCaptureResources:
    """Tests for Phase 43 script capture resources (cortex://scripts/...)."""

    async def test_list_session_scripts_resource_returns_json(self) -> None:
        """list_session_scripts_resource returns JSON (Phase 43)."""
        payload = json.dumps({"status": "success", "count": 0, "scripts": []}, indent=2)
        with patch(
            "cortex.tools.script_capture_tools.list_session_scripts",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result_str = await list_session_scripts_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["count"] == 0
        assert result["scripts"] == []

    async def test_analyze_session_scripts_resource_returns_json(self) -> None:
        """analyze_session_scripts_resource returns JSON (Phase 43)."""
        payload = json.dumps(
            {"status": "success", "count": 0, "analyses": []}, indent=2
        )
        with patch(
            "cortex.tools.script_capture_tools.analyze_session_scripts",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mocked_analyze:
            result_str = await analyze_session_scripts_resource()
        _, kwargs = mocked_analyze.call_args
        assert "project_root" not in kwargs
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["count"] == 0
        assert "analyses" in result

    async def test_suggest_tool_improvements_resource_returns_json(
        self,
    ) -> None:
        """suggest_tool_improvements_resource returns JSON (Phase 43)."""
        payload = json.dumps(
            {
                "status": "success",
                "task_description": "format code",
                "recommendations": [],
            },
            indent=2,
        )
        with patch(
            "cortex.tools.script_capture_tools.suggest_tool_improvements",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result_str = await suggest_tool_improvements_resource(
                task_description="format%20code"
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["task_description"] == "format code"
