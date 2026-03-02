"""Fuzz/adversarial input tests for MCP tool parameter sanitization.

Covers plan-security-and-resilience Step 1: MCP Tool Input Sanitization Audit.
Verifies critical tools reject path traversal, oversized inputs, and invalid data.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.constants import (
    MAX_MANAGE_FILE_CONTENT_BYTES,
    MAX_SECTIONS_LIST_SIZE,
    MAX_TASK_DESCRIPTION_CHARS,
)


class TestManageFileInputSanitization:
    """Test manage_file rejects adversarial and oversized inputs."""

    @pytest.mark.asyncio
    async def test_manage_file_rejects_oversized_content(self):
        """Test manage_file rejects content exceeding MAX_MANAGE_FILE_CONTENT_BYTES."""
        from cortex.tools.files.operations import manage_file

        # Content 1 byte over limit (UTF-8: 1 char = 1 byte for ASCII)
        oversized = "x" * (MAX_MANAGE_FILE_CONTENT_BYTES + 1)

        result_str = await manage_file(
            file_name="activeContext.md",
            operation="write",
            content=oversized,
        )

        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "too large" in result["error"].lower()
        assert str(MAX_MANAGE_FILE_CONTENT_BYTES) in result["error"]

    @pytest.mark.asyncio
    async def test_manage_file_rejects_oversized_sections_list(self):
        """Test manage_file rejects sections list exceeding MAX_SECTIONS_LIST_SIZE."""
        from cortex.tools.files.operations import manage_file

        sections = ["## Section"] * (MAX_SECTIONS_LIST_SIZE + 1)

        result_str = await manage_file(
            file_name="activeContext.md",
            operation="read",
            sections=sections,
        )

        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "sections" in result["error"].lower()
        assert "too long" in result["error"].lower()
        assert str(MAX_SECTIONS_LIST_SIZE) in result["error"]

    @pytest.mark.asyncio
    async def test_manage_file_accepts_content_at_limit(self):
        """Test manage_file accepts content at exactly the limit."""
        from cortex.tools.files.crud_operations import manage_file

        content = "x" * MAX_MANAGE_FILE_CONTENT_BYTES

        with patch(
            "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=Path("/tmp/test"),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers._manage_file_run_or_error",
                new_callable=AsyncMock,
                return_value='{"status":"success","file_name":"activeContext.md"}',
            ):
                result_str = await manage_file(
                    file_name="activeContext.md",
                    operation="write",
                    content=content,
                )

        result = json.loads(result_str)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_manage_file_accepts_sections_at_limit(self):
        """Test manage_file accepts sections list at exactly the limit."""
        from cortex.tools.files.crud_operations import manage_file

        sections = ["## Section"] * MAX_SECTIONS_LIST_SIZE

        with patch(
            "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=Path("/tmp/test"),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers._manage_file_run_or_error",
                new_callable=AsyncMock,
                return_value='{"status":"success","content":""}',
            ):
                result_str = await manage_file(
                    file_name="activeContext.md",
                    operation="read",
                    sections=sections,
                )

        result = json.loads(result_str)
        assert result["status"] == "success"


class TestLoadContextInputSanitization:
    """Test load_context rejects oversized task_description."""

    @pytest.mark.asyncio
    async def test_load_context_rejects_oversized_task_description(self):
        """Test load_context rejects task_description exceeding limit."""
        from cortex.tools.optimization import load_context

        oversized = "x" * (MAX_TASK_DESCRIPTION_CHARS + 1)

        result_str = await load_context(task_description=oversized)

        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "task_description" in result["error"].lower()
        assert "too long" in result["error"].lower()
        assert str(MAX_TASK_DESCRIPTION_CHARS) in result["error"]

    @pytest.mark.asyncio
    async def test_load_context_accepts_task_description_at_limit(self):
        """Test load_context accepts task_description at exactly the limit."""
        from cortex.tools.optimization import load_context

        task_description = "x" * MAX_TASK_DESCRIPTION_CHARS

        with patch(
            "cortex.tools.optimization.handlers.resolve_load_context_budget",
            return_value=(10_000, None),
        ):
            with patch(
                "cortex.tools.optimization.handlers.execute_load_context_with_logging",
                new_callable=AsyncMock,
                return_value='{"status":"success","files_map":{}}',
            ):
                result_str = await load_context(task_description=task_description)

        result = json.loads(result_str)
        assert result["status"] == "success"


class TestPathTraversalBlocked:
    """Verify path traversal is blocked for file operations (integration with InputValidator)."""

    def test_construct_safe_path_rejects_traversal(self):
        """FileSystemManager.construct_safe_path rejects path traversal in file_name."""
        import tempfile

        from cortex.core.file_system import FileSystemManager
        from cortex.core.path_resolver import CortexResourceType, get_cortex_path

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mb_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
            mb_dir.mkdir(parents=True)
            fs = FileSystemManager(project_root=root)

            with pytest.raises(
                (ValueError, PermissionError), match="traversal|outside"
            ):
                _ = fs.construct_safe_path(mb_dir, "../../../etc/passwd")
