"""get_file_resource tests."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.tools.files.operations import (
    get_file_resource,
)
from tests.helpers.managers import make_test_managers


@pytest.mark.asyncio
class TestGetFileResource:
    """Test get_file_resource (Phase 43 memory-bank file read resource)."""

    async def test_get_file_resource_returns_json_with_content(self):
        """Test get_file_resource returns valid JSON with status/file_name/content."""
        # Arrange
        file_name = "projectBrief.md"
        content = "# Project Brief"
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(return_value=None)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.crud_operations.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await get_file_resource(file_name=file_name)

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["file_name"] == file_name
                assert result["content"] == content
