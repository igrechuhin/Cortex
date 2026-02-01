"""Tests for script_capture_tools MCP handlers."""

import json
import tempfile
from pathlib import Path

import pytest

from cortex.tools.script_capture_tools import (
    capture_session_script,
    list_session_scripts,
)


class TestCaptureSessionScript:
    """Tests for capture_session_script MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_success_with_script_id_and_timestamp(self) -> None:
        """capture_session_script returns JSON with status, script_id, timestamp."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = await capture_session_script(
                script_path="scripts/foo.py",
                script_content="print(1)",
                task_description="Test",
                project_root=str(root),
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
            capture_result = await capture_session_script(
                script_path="bar.py",
                script_content="x = 1",
                task_description="Bar task",
                script_type="python",
                project_root=str(root),
            )
            capture_data = json.loads(capture_result)
            script_id = capture_data["script_id"]
            list_result = await list_session_scripts(project_root=str(root))
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
            result = await list_session_scripts(project_root=str(root))
            data = json.loads(result)
            assert data["status"] == "success"
            assert data["count"] == 0
            assert data["scripts"] == []

    @pytest.mark.asyncio
    async def test_returns_captured_scripts_in_list(self) -> None:
        """list_session_scripts returns summaries of previously captured scripts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            await capture_session_script(
                script_path="a.py",
                script_content="a",
                task_description="A",
                project_root=str(root),
            )
            await capture_session_script(
                script_path="b.sh",
                script_content="b",
                task_description="B",
                script_type="shell",
                project_root=str(root),
            )
            result = await list_session_scripts(project_root=str(root))
            data = json.loads(result)
            assert data["status"] == "success"
            assert data["count"] == 2
            paths = {s["script_path"] for s in data["scripts"]}
            assert paths == {"a.py", "b.sh"}
            shell_script = next(
                s for s in data["scripts"] if s["script_path"] == "b.sh"
            )
            assert shell_script["script_type"] == "shell"
