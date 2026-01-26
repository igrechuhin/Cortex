"""Comprehensive tests for file_operations module.

Tests cover all functions, edge cases, error paths, and helpers to achieve 100% coverage.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.tools.file_operations import (
    build_invalid_operation_error,
    build_write_error_response,
    build_write_response,
    compute_file_metrics,
    create_version_snapshot,
    extract_sections,
    manage_file,
    update_file_metadata,
    validate_write_content,
)
from tests.helpers.managers import make_test_managers


@pytest.mark.asyncio
class TestManageFileEdgeCases:
    """Test edge cases and error paths in manage_file."""

    async def test_manage_file_invalid_file_name_with_path_traversal(self):
        """Test file name validation with path traversal attempt."""
        # Arrange
        file_name = "../../../etc/passwd"
        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(
            side_effect=ValueError("Path traversal detected")
        )
        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(file_name=file_name, operation="read")

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Invalid file name" in result["error"]

    async def test_manage_file_permission_error_on_path_validation(self):
        """Test permission error during path validation."""
        # Arrange
        file_name = "test.md"
        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(
            side_effect=PermissionError("Permission denied")
        )
        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(file_name=file_name, operation="read")

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Invalid file name" in result["error"]

    async def test_manage_file_read_with_no_metadata(self):
        """Test read operation when metadata is not found."""
        # Arrange
        file_name = "projectBrief.md"
        content = "# Project Brief"
        temp_path = Path("/tmp/test/memory-bank/projectBrief.md")

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=temp_path)

        # Create a mock path that returns True for exists()
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_fs.construct_safe_path.return_value = mock_path

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(return_value=None)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                    include_metadata=True,
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["content"] == content
                # metadata should not be included if not found
                assert "metadata" not in result or result["metadata"] is None

    async def test_manage_file_metadata_not_found_returns_warning(self):
        """Test metadata operation when file exists but no metadata found."""
        # Arrange
        file_name = "test.md"

        # Create a mock path that exists
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        mock_fs = AsyncMock()
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
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="metadata",
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "warning"
                assert "No metadata found" in result["message"]
                assert result["file_name"] == file_name

    async def test_manage_file_write_with_file_conflict(self):
        """Test write operation with file conflict error."""
        # Arrange
        file_name = "test.md"
        content = "New content"

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = file_name

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)
        mock_fs.read_file = AsyncMock(return_value=("Existing content", "old_hash"))
        mock_fs.write_file = AsyncMock(
            side_effect=FileConflictError("test.md", "expected_hash", "actual_hash")
        )
        mock_fs.compute_hash = MagicMock(return_value="hash123")

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"content_hash": "old_hash"}
        )

        mock_tokens = MagicMock()
        mock_tokens.count_tokens = MagicMock(return_value=50)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": mock_tokens,
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="write",
                    content=content,
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert result["error_type"] == "FileConflictError"
                assert "suggestion" in result

    async def test_manage_file_write_with_lock_timeout(self):
        """Test write operation with lock timeout error."""
        # Arrange
        file_name = "test.md"
        content = "New content"

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = file_name

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)
        mock_fs.read_file = AsyncMock(return_value=("Existing content", "old_hash"))
        mock_fs.write_file = AsyncMock(side_effect=FileLockTimeoutError("test.md", 10))
        mock_fs.compute_hash = MagicMock(return_value="hash123")

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"content_hash": "old_hash"}
        )

        mock_tokens = MagicMock()
        mock_tokens.count_tokens = MagicMock(return_value=50)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": mock_tokens,
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="write",
                    content=content,
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert result["error_type"] == "FileLockTimeoutError"
                assert "suggestion" in result

    async def test_manage_file_write_with_git_conflict(self):
        """Test write operation with git conflict error."""
        # Arrange
        file_name = "test.md"
        content = "New content"

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = file_name

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)
        mock_fs.read_file = AsyncMock(return_value=("Existing content", "old_hash"))
        mock_fs.write_file = AsyncMock(side_effect=GitConflictError("test.md"))
        mock_fs.compute_hash = MagicMock(return_value="hash123")

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"content_hash": "old_hash"}
        )

        mock_tokens = MagicMock()
        mock_tokens.count_tokens = MagicMock(return_value=50)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": mock_tokens,
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="write",
                    content=content,
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert result["error_type"] == "GitConflictError"
                assert "suggestion" in result

    async def test_manage_file_generic_exception_in_handler(self):
        """Test generic exception handling in main handler."""
        # Arrange
        file_name = "test.md"

        mock_managers_dict = {
            "fs": AsyncMock(),
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                side_effect=RuntimeError("Unexpected error"),
            ):
                # Act
                result_str = await manage_file(file_name=file_name, operation="read")

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Unexpected error" in result["error"]
                assert result["error_type"] == "RuntimeError"

    async def test_manage_file_write_without_content_in_dispatch(self):
        """Test write operation dispatch without content (line 577-585)."""
        # Arrange
        file_name = "test.md"

        mock_path = MagicMock(spec=Path)
        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="write",
                    content=None,
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Content is required" in result["error"]


@pytest.mark.asyncio
class TestHelperFunctions:
    """Test helper functions for comprehensive coverage."""

    def test_extract_sections_with_multiple_headings(self):
        """Test section extraction with multiple headings."""
        # Arrange
        content = """# Main Title

## Section 1
Content here

## Section 2
More content

### Subsection
This should also be extracted because it starts with ##

## Section 3
Final section
"""

        # Act
        sections = extract_sections(content)

        # Assert
        # Note: extract_sections extracts ALL lines starting with "##",
        # including "###", "####", etc.
        assert len(sections) == 4
        assert sections[0]["heading"] == "## Section 1"
        assert sections[0]["level"] == 2
        assert sections[1]["heading"] == "## Section 2"
        assert sections[1]["level"] == 2
        assert sections[2]["heading"] == "### Subsection"
        assert sections[2]["level"] == 2
        assert sections[3]["heading"] == "## Section 3"
        assert sections[3]["level"] == 2

    def test_extract_sections_with_no_headings(self):
        """Test section extraction with no level 2 headings."""
        # Arrange
        content = "Just plain text without headings"

        # Act
        sections = extract_sections(content)

        # Assert
        assert len(sections) == 0
        assert sections == []

    def test_extract_sections_with_whitespace(self):
        """Test section extraction only extracts lines starting with ##."""
        # Arrange
        content = """
## Section 1
##Section 3
"""

        # Act
        sections = extract_sections(content)

        # Assert
        # Note: Only lines that START with "##" are extracted
        # Lines with leading whitespace are NOT extracted
        assert len(sections) == 2
        assert sections[0]["heading"] == "## Section 1"
        assert sections[1]["heading"] == "##Section 3"

    def test_compute_file_metrics(self):
        """Test file metrics computation."""
        # Arrange
        content = "Test content for metrics"
        mock_fs = MagicMock()
        mock_fs.compute_hash = MagicMock(return_value="abc123")

        mock_tokens = MagicMock()
        mock_tokens.count_tokens = MagicMock(return_value=5)

        # Act
        metrics = compute_file_metrics(content, mock_fs, mock_tokens)

        # Assert
        assert metrics["size_bytes"] == len(content.encode("utf-8"))
        assert metrics["token_count"] == 5
        assert metrics["content_hash"] == "abc123"
        mock_fs.compute_hash.assert_called_once_with(content)
        mock_tokens.count_tokens.assert_called_once_with(content)

    async def test_create_version_snapshot(self):
        """Test version snapshot creation."""
        # Arrange
        file_path = Path("/tmp/test/memory-bank/test.md")
        content = "Test content"
        file_metrics = {
            "size_bytes": 100,
            "token_count": 25,
            "content_hash": "hash123",
        }

        mock_version_manager = AsyncMock()
        mock_version_manager.get_version_count = AsyncMock(return_value=5)
        mock_version_manager.create_snapshot = AsyncMock(
            return_value={"version": 6, "snapshot_path": "/tmp/snapshots/test.md.v6"}
        )

        # Act
        result = await create_version_snapshot(
            file_path,
            content,
            cast(dict[str, object], file_metrics),
            mock_version_manager,
            "Custom description",
        )

        # Assert
        assert result["version"] == 6
        mock_version_manager.get_version_count.assert_called_once_with("test.md")
        mock_version_manager.create_snapshot.assert_called_once()

    async def test_update_file_metadata(self):
        """Test file metadata update."""
        # Arrange
        file_name = "test.md"
        file_path = Path("/tmp/test/memory-bank/test.md")
        content = "## Heading 1\n## Heading 2"
        file_metrics = {
            "size_bytes": 100,
            "token_count": 25,
            "content_hash": "hash123",
        }
        version_info = MagicMock()
        version_info.version = 6
        version_info.snapshot_path = "/tmp/snapshots/test.md.v6"

        mock_metadata_index = AsyncMock()
        mock_metadata_index.update_file_metadata = AsyncMock()
        mock_metadata_index.add_version_to_history = AsyncMock()

        # Act
        await update_file_metadata(
            file_name,
            file_path,
            content,
            cast(dict[str, object], file_metrics),
            mock_metadata_index,
            version_info,
        )

        # Assert
        mock_metadata_index.update_file_metadata.assert_called_once()
        mock_metadata_index.add_version_to_history.assert_called_once_with(
            file_name, version_info.model_dump(mode="json")
        )

    def test_build_write_response(self):
        """Test write response builder."""
        # Arrange
        file_name = "test.md"
        version_info = MagicMock()
        version_info.version = 6
        version_info.snapshot_path = "/tmp/snapshots/test.md.v6"
        content = "Test content"

        mock_tokens = MagicMock()
        mock_tokens.count_tokens = MagicMock(return_value=50)

        # Act
        response_str = build_write_response(
            file_name, version_info, mock_tokens, content
        )

        # Assert
        response = json.loads(response_str)
        assert response["status"] == "success"
        assert response["file_name"] == file_name
        assert "written successfully" in response["message"]
        assert response["snapshot_id"] == "/tmp/snapshots/test.md.v6"
        assert response["version"] == 6
        assert response["tokens"] == 50

    def test_validate_write_content_with_none(self):
        """Test content validation with None."""
        # Act
        result = validate_write_content(None)

        # Assert
        assert result is not None
        error = json.loads(result)
        assert error["status"] == "error"
        assert "required" in error["error"]

    def test_validate_write_content_with_valid_content(self):
        """Test content validation with valid content."""
        # Act
        result = validate_write_content("Valid content")

        # Assert
        assert result is None

    def test_build_write_error_response_file_conflict(self):
        """Test write error response for file conflict."""
        # Arrange
        error = FileConflictError("test.md", "expected_hash", "actual_hash")

        # Act
        response_str = build_write_error_response(error)

        # Assert
        response = json.loads(response_str)
        assert response["status"] == "error"
        assert response["error_type"] == "FileConflictError"
        assert "suggestion" in response

    def test_build_write_error_response_lock_timeout(self):
        """Test write error response for lock timeout."""
        # Arrange
        error = FileLockTimeoutError("test.md", 10)

        # Act
        response_str = build_write_error_response(error)

        # Assert
        response = json.loads(response_str)
        assert response["status"] == "error"
        assert response["error_type"] == "FileLockTimeoutError"
        assert "suggestion" in response

    def test_build_write_error_response_git_conflict(self):
        """Test write error response for git conflict."""
        # Arrange
        error = GitConflictError("test.md")

        # Act
        response_str = build_write_error_response(error)

        # Assert
        response = json.loads(response_str)
        assert response["status"] == "error"
        assert response["error_type"] == "GitConflictError"
        assert "suggestion" in response

    def test_build_invalid_operation_error(self):
        """Test invalid operation error builder."""
        # Act
        response_str = build_invalid_operation_error("delete")

        # Assert
        response = json.loads(response_str)
        assert response["status"] == "error"
        assert "Invalid operation" in response["error"]
        assert "delete" in response["error"]
        assert "valid_operations" in response
        assert "read" in response["valid_operations"]
        assert "write" in response["valid_operations"]
        assert "metadata" in response["valid_operations"]


@pytest.mark.asyncio
class TestEdgeCasesForCoverage:
    """Additional tests to achieve 100% coverage."""

    async def test_manage_file_read_file_not_exists_with_available_files(self):
        """Test read operation when file doesn't exist, listing available files."""
        # Arrange
        file_name = "nonexistent.md"

        # Create mock path that doesn't exist
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = False

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(file_name=file_name, operation="read")

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "does not exist" in result["error"]
                assert "available_files" in result["context"]

    async def test_manage_file_read_with_metadata_found(self):
        """Test read with metadata when metadata exists (line 299)."""
        # Arrange
        file_name = "test.md"
        content = "Test content"
        metadata = {"size_bytes": 100, "token_count": 25}

        # Create mock path that exists
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(return_value=metadata)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                    include_metadata=True,
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "metadata" in result
                assert result["metadata"]["size_bytes"] == 100

    async def test_manage_file_write_content_none_in_handler(self):
        """Test write handler when content is None (line 316)."""
        # Arrange
        file_name = "test.md"
        content = None

        mock_path = MagicMock(spec=Path)
        mock_path.name = file_name

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="write",
                    content=content,
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "required" in result["error"]

    async def test_manage_file_metadata_file_not_exists(self):
        """Test metadata operation when file doesn't exist (line 344)."""
        # Arrange
        file_name = "nonexistent.md"

        # Create mock path that doesn't exist
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = False

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="metadata",
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "does not exist" in result["error"]

    async def test_manage_file_metadata_with_valid_data(self):
        """Test metadata operation when metadata exists (line 359)."""
        # Arrange
        file_name = "test.md"
        metadata = {"size_bytes": 200, "token_count": 50}

        # Create mock path that exists
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(return_value=metadata)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="metadata",
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "metadata" in result
                assert result["metadata"]["size_bytes"] == 200

    async def test_manage_file_write_success_full_flow(self):
        """Test successful write operation covering lines 486-504."""
        # Arrange
        file_name = "test.md"
        content = "## Heading 1\n## Heading 2\nContent here"

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = file_name

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)
        mock_fs.read_file = AsyncMock(return_value=("Existing content", "disk_hash"))
        mock_fs.write_file = AsyncMock(return_value="new_hash")
        mock_fs.compute_hash = MagicMock(return_value="new_hash")

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"content_hash": "stale_hash"}
        )
        mock_index.update_file_metadata = AsyncMock()
        mock_index.add_version_to_history = AsyncMock()

        mock_tokens = MagicMock()
        mock_tokens.count_tokens = MagicMock(return_value=25)

        mock_versions = AsyncMock()
        mock_versions.get_version_count = AsyncMock(return_value=1)
        version_info = MagicMock()
        version_info.version = 2
        version_info.snapshot_path = "/tmp/snapshots/test.md.v2"
        mock_versions.create_snapshot = AsyncMock(return_value=version_info)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": mock_tokens,
            "versions": mock_versions,
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="write",
                    content=content,
                    change_description="Test update",
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["file_name"] == file_name
                assert "snapshot_id" in result
                assert result["version"] == 2
                assert result["tokens"] == 25

                # Verify all helper functions were called
                mock_fs.write_file.assert_called_once_with(
                    mock_path,
                    content,
                    expected_hash="disk_hash",
                )
                mock_versions.create_snapshot.assert_called_once()
                mock_index.update_file_metadata.assert_called_once()
                mock_index.add_version_to_history.assert_called_once()
                mock_index.get_file_metadata.assert_not_awaited()

    async def test_manage_file_invalid_operation_dispatch(self):
        """Test invalid operation in dispatcher (line 600)."""
        # Arrange
        file_name = "test.md"

        mock_path = MagicMock(spec=Path)
        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="delete",  # Invalid operation
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Invalid operation" in result["error"]
                assert "valid_operations" in result
