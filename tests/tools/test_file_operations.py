"""Comprehensive tests for file_operations module.

Tests cover all functions, edge cases, error paths, and helpers to
achieve 100% coverage.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.models import DetailedFileMetadata, ResponseStatus
from cortex.tools.files.file_operation_helpers import (
    FileOperation,
    build_invalid_operation_error,
    build_schema_validation_error_response,
    build_write_error_response,
    parse_file_operation,
    validate_write_content,
)
from cortex.tools.files.file_operations import (
    build_write_response,
    compute_file_metrics,
    create_version_snapshot,
    extract_sections,
    get_file_resource,
    manage_file,
    update_file_metadata,
)
from cortex.validation.models import (
    ValidationError as ValidationErrorModel,
)
from cortex.validation.models import (
    ValidationResult as ValidationResultModel,
)
from cortex.validation.models import (
    ValidationSeverity,
)
from tests.helpers.managers import make_test_managers


class ManageFileErrorDetails(BaseModel):
    missing: list[str]
    required: list[str]
    operation_values: list[str]


class ManageFileErrorResponse(BaseModel):
    status: ResponseStatus
    error: str
    details: ManageFileErrorDetails


@pytest.mark.asyncio
@pytest.mark.timeout(15)
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(file_name=file_name, operation="read")

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Invalid file name" in result["error"]

    @pytest.mark.parametrize(
        "operation",
        ["read", "write", "metadata", "rollback"],
        ids=["read", "write", "metadata", "rollback"],
    )
    async def test_manage_file_invalid_file_name_returns_error_for_operation(
        self, operation: str
    ) -> None:
        """Invalid file name (path traversal) returns error for each operation."""
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                kwargs: dict[str, object] = {
                    "file_name": file_name,
                    "operation": operation,
                }
                if operation == "write":
                    kwargs["content"] = "# dummy"
                if operation == "rollback":
                    kwargs["version"] = 1
                result_str = await manage_file(**kwargs)
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Invalid file name" in result["error"]

    _EDGE_FILE_NAMES: list[tuple[str, str]] = [
        ("", "empty_string"),
        ("a" * 600, "very_long_path"),
        ("café_naïve.md", "unicode"),
        ("  \t  ", "whitespace_only"),
        (".", "dot_only"),
    ]

    @pytest.mark.parametrize(
        "file_name,scenario",
        _EDGE_FILE_NAMES,
        ids=[s for _, s in _EDGE_FILE_NAMES],
    )
    async def test_manage_file_edge_case_file_name_returns_error(
        self, file_name: str, scenario: str
    ) -> None:
        """Edge-case file_name values (empty, long, unicode, etc.) return error."""
        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(
            side_effect=ValueError("Invalid or disallowed file name")
        )
        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }
        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                )
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "error" in result

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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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

        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=Path("/tmp/test"),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_managers",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Unexpected error"),
            ):
                # Act
                result_str = await manage_file(file_name=file_name, operation="read")

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Unexpected error" in result["error"]
                assert result["error_type"] == "RuntimeError"

    async def test_manage_file_log_result_handles_invalid_json_response(self):
        """_log_result_by_status handles non-JSON result without raising."""
        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=Path("/tmp/test"),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.execute_file_operation",
                new_callable=AsyncMock,
                return_value="not valid json",
            ):
                result_str = await manage_file(file_name="test.md", operation="read")
                assert result_str == "not valid json"

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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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

    async def test_manage_file_missing_both_required_parameters_returns_friendly_error(
        self,
    ) -> None:
        """manage_file() should return structured error when both parameters missing."""
        # Act
        result_str = await manage_file()  # type: ignore[call-arg]

        # Assert
        payload = ManageFileErrorResponse.model_validate_json(result_str)
        assert payload.status == "error"
        assert "missing required parameters" in payload.error.lower()
        assert payload.details.missing == ["file_name", "operation"]
        assert payload.details.required == ["file_name", "operation"]
        assert payload.details.operation_values == [
            "read",
            "write",
            "metadata",
            "rollback",
        ]

    async def test_manage_file_missing_file_name_only_returns_friendly_error(
        self,
    ) -> None:
        """manage_file() should return structured error when file_name is missing."""
        # Act
        result_str = await manage_file(operation="read")

        # Assert
        payload = ManageFileErrorResponse.model_validate_json(result_str)
        assert payload.status == "error"
        assert "missing required parameters" in payload.error.lower()
        assert payload.details.missing == ["file_name"]
        assert payload.details.required == ["file_name", "operation"]
        assert payload.details.operation_values == [
            "read",
            "write",
            "metadata",
            "rollback",
        ]

    async def test_manage_file_missing_operation_only_returns_friendly_error(
        self,
    ) -> None:
        """manage_file() should return structured error when operation is missing."""
        # Act
        result_str = await manage_file(file_name="projectBrief.md")

        # Assert
        payload = ManageFileErrorResponse.model_validate_json(result_str)
        assert payload.status == "error"
        assert "missing required parameters" in payload.error.lower()
        assert payload.details.missing == ["operation"]
        assert payload.details.required == ["file_name", "operation"]
        assert payload.details.operation_values == [
            "read",
            "write",
            "metadata",
            "rollback",
        ]


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
        # Note: extract_sections extracts ALL headings (# through ######)
        # that match the pattern ^(#{1,6})\s+(.+)$
        assert len(sections) == 5
        assert sections[0]["heading"] == "# Main Title"
        assert sections[0]["level"] == 1
        assert sections[1]["heading"] == "## Section 1"
        assert sections[1]["level"] == 2
        assert sections[2]["heading"] == "## Section 2"
        assert sections[2]["level"] == 2
        assert sections[3]["heading"] == "### Subsection"
        assert sections[3]["level"] == 3
        assert sections[4]["heading"] == "## Section 3"
        assert sections[4]["level"] == 2

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
        """Test section extraction requires whitespace after # symbols."""
        # Arrange
        content = """
## Section 1
##Section 3
"""

        # Act
        sections = extract_sections(content)

        # Assert
        # Note: The regex pattern ^(#{1,6})\s+(.+)$ requires whitespace
        # after the # symbols. "##Section 3" doesn't match (no space after ##)
        assert len(sections) == 1
        assert sections[0]["heading"] == "## Section 1"

    def test_parse_file_operation_returns_none_for_none(self) -> None:
        """parse_file_operation(None) returns None."""
        assert parse_file_operation(None) is None

    def test_parse_file_operation_returns_enum_for_valid_values(self) -> None:
        """parse_file_operation returns FileOperation for valid strings."""
        assert parse_file_operation("read") is FileOperation.READ
        assert parse_file_operation("write") is FileOperation.WRITE
        assert parse_file_operation("metadata") is FileOperation.METADATA

    def test_parse_file_operation_returns_none_for_invalid_value(self) -> None:
        """parse_file_operation returns None for invalid string."""
        assert parse_file_operation("invalid") is None
        assert parse_file_operation("") is None

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
        from cortex.core.models import ModelDict

        result = await create_version_snapshot(
            file_path,
            content,
            cast(ModelDict, file_metrics),
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
        from cortex.core.models import ModelDict

        await update_file_metadata(
            file_name,
            file_path,
            content,
            cast(ModelDict, file_metrics),
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

    def test_validate_write_content_rejects_null_bytes(self):
        """Test content validation rejects null bytes to avoid corrupted records."""
        # Act
        result = validate_write_content("Valid\x00content")

        # Assert
        assert result is not None
        error = json.loads(result)
        assert error["status"] == "error"
        assert "null" in error["error"].lower()

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

    def test_build_schema_validation_error_response(self):
        """Test schema validation error response for pre-write validation failures."""
        # Arrange
        err = ValidationErrorModel(
            type="missing_section",
            severity=ValidationSeverity.ERROR,
            message="Missing required section: Goals",
            suggestion="Add ## Goals",
        )
        result = ValidationResultModel(
            valid=False,
            errors=[err],
            warnings=[],
            score=40,
        )

        # Act
        response_str = build_schema_validation_error_response("projectBrief.md", result)

        # Assert
        response = json.loads(response_str)
        assert response["status"] == "error"
        assert response["file_name"] == "projectBrief.md"
        assert "schema" in response["error"].lower()
        assert response["validation"]["valid"] is False
        assert response["validation"]["score"] == 40
        assert len(response["validation"]["errors"]) == 1
        assert response["validation"]["errors"][0]["message"] == (
            "Missing required section: Goals"
        )

    def test_build_invalid_operation_error(self):
        """Test invalid operation error builder."""
        # Act
        response_str = build_invalid_operation_error("delete")

        # Assert
        response = json.loads(response_str)
        assert response["status"] == "error"
        assert "Invalid operation" in response["error"]

    def test_validate_write_request_content_none(self):
        """Test validate_write_request when content is None."""
        from cortex.tools.files.file_operation_helpers import validate_write_request

        # Arrange
        file_path = Path("/tmp/test.md")
        file_name = "test.md"
        content = None

        # Act
        result: str | None = validate_write_request(file_path, file_name, content)

        # Assert
        assert result is not None
        error_response: dict[str, object] = json.loads(result)
        assert error_response.get("status") == "error"
        assert "Content is required" in str(error_response.get("error", ""))


@pytest.mark.asyncio
@pytest.mark.timeout(15)
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(file_name=file_name, operation="read")

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "does not exist" in result["error"]
                assert "available_files" in result["context"]

    async def test_manage_file_read_with_sections(self):
        """Test read operation with section extraction."""
        # Arrange
        file_name = "projectBrief.md"
        content = (
            "# Project Brief\n\n## Section 1\ncontent 1\n\n## Section 2\ncontent 2"
        )
        temp_path = Path("/tmp/test/memory-bank/projectBrief.md")

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=temp_path)

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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                    sections=["## Section 1"],
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "## Section 1" in result["content"]
                assert "content 1" in result["content"]
                assert "## Section 2" not in result["content"]

    async def test_manage_file_read_with_multiple_sections(self):
        """Test read operation with multiple section extraction."""
        # Arrange
        file_name = "projectBrief.md"
        content = "# Project Brief\n\n## Section 1\ncontent 1\n\n## Section 2\ncontent 2\n\n## Section 3\ncontent 3"
        temp_path = Path("/tmp/test/memory-bank/projectBrief.md")

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=temp_path)

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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                    sections=["## Section 1", "## Section 3"],
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "## Section 1" in result["content"]
                assert "content 1" in result["content"]
                assert "## Section 3" in result["content"]
                assert "content 3" in result["content"]
                assert "## Section 2" not in result["content"]
                assert "---" in result["content"]  # Sections should be separated

    async def test_manage_file_read_with_nested_section(self):
        """Test read operation with nested section extraction using / separator."""
        # Arrange
        file_name = "projectBrief.md"
        content = "# Project Brief\n\n## Parent\nparent content\n### Child\nchild content\n## Other"
        temp_path = Path("/tmp/test/memory-bank/projectBrief.md")

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=temp_path)

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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                    sections=["## Parent/### Child"],
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "### Child" in result["content"]
                assert "child content" in result["content"]
                assert "## Parent" not in result["content"]  # Should only have child

    async def test_manage_file_read_with_section_not_found(self):
        """Test read operation when requested section is not found."""
        # Arrange
        file_name = "projectBrief.md"
        content = "# Project Brief\n\n## Section 1\ncontent 1"
        temp_path = Path("/tmp/test/memory-bank/projectBrief.md")

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=temp_path)

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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                    sections=["## Missing Section"],
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                # When section not found, extract_sections_from_content returns empty string with warning
                # (extracted_parts is empty when warning exists)
                assert "warning" in result
                assert "not found" in result["warning"].lower()
                # Content may be empty when section not found (extracted_parts is empty)
                assert result["content"] == "" or "# Project Brief" in result["content"]

    async def test_manage_file_read_with_metadata_found(self):
        """Test read with metadata when metadata exists (line 299)."""
        # Arrange
        file_name = "test.md"
        content = "Test content"
        metadata_model = DetailedFileMetadata(
            path="/tmp/test/.cortex/memory-bank/test.md",
            exists=True,
            size_bytes=100,
            token_count=25,
            token_model="cl100k_base",
            last_modified="2026-01-01T00:00:00",
            content_hash="hash123",
        )

        # Create mock path that exists
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(return_value=metadata_model)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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

    async def test_manage_file_log_result_non_dict_response(self):
        """Test _log_result_by_status when result is not a dict (line 447)."""
        from cortex.tools.files.file_manage_file_helpers import (
            _log_result_by_status,  # type: ignore[reportPrivateUsage]
        )
        from cortex.tools.files.file_operation_helpers import (
            FileOperation,  # type: ignore[reportPrivateImportUsage]
        )

        # Arrange
        file_name = "test.md"
        result_str = '["not", "a", "dict"]'  # JSON array, not dict
        parsed_op = FileOperation.READ

        ctx = MagicMock()

        with patch(
            "cortex.tools.files.file_manage_file_helpers.log_client",
            new_callable=AsyncMock,
        ) as mock_log_client:
            # Act - call _log_result_by_status directly with non-dict JSON
            await _log_result_by_status(ctx, file_name, parsed_op, result_str)

            # Assert - should have logged without error (handles non-dict gracefully)
            # The function should complete without raising
            # When result is not a dict, it should still call log_client
            assert mock_log_client.called

    async def test_write_file_with_hash_check_existing_file(self):
        """Test _write_file_with_hash_check when file exists (line 924-926)."""
        from cortex.tools.files.file_crud_flow import (
            _write_file_with_hash_check,  # type: ignore[reportPrivateUsage]
        )

        # Arrange
        content = "new content"
        expected_hash = "existing_hash"

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=("old content", expected_hash))
        mock_fs.write_file = AsyncMock(return_value=None)

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        # Act
        await _write_file_with_hash_check(mock_path, content, mock_fs)

        # Assert
        mock_fs.read_file.assert_called_once_with(mock_path)
        mock_fs.write_file.assert_called_once_with(
            mock_path, content, expected_hash=expected_hash
        )

    async def test_resolve_schema_validator_exception_handling(self):
        """Test _resolve_schema_validator exception handling (line 1023-1024)."""
        from typing import cast

        from cortex.managers.types import ManagersDict
        from cortex.tools.files.file_manage_file_helpers import (
            _resolve_schema_validator,  # type: ignore[reportPrivateUsage]
        )

        # Arrange - managers dict without schema_validator

        managers = cast(
            ManagersDict,
            {
                "fs": AsyncMock(),
                "index": AsyncMock(),
                "tokens": MagicMock(),
            },
        )

        # Act
        result = await _resolve_schema_validator(managers)  # type: ignore[reportUnknownVariableType]

        # Assert - should return None when schema_validator not available
        assert result is None

    async def test_get_managers_for_root_creates_new_when_root_differs(self):
        """Test _get_managers_for_root creates new managers when root differs."""
        from cortex.core.usage_context import (
            set_current_managers,
            set_current_project_root,
        )
        from cortex.tools.files.file_manage_file_helpers import (
            _get_managers_for_root,  # type: ignore[reportPrivateUsage]
        )

        # Arrange
        current_root = Path("/tmp/current")
        new_root = Path("/tmp/new")
        current_mgrs = {
            "fs": AsyncMock(),
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        # Set current managers with different root
        set_current_managers(current_mgrs)
        set_current_project_root(current_root)

        mock_fs = AsyncMock()
        mock_index = AsyncMock()
        mock_tokens = MagicMock()
        mock_versions = AsyncMock()

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": mock_tokens,
            "versions": mock_versions,
        }

        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            # Act
            managers, fs = await _get_managers_for_root(new_root)  # type: ignore[reportUnknownVariableType]

            # Assert - should create new managers
            assert managers is not None
            assert fs is not None

    async def test_manage_file_read_with_sections_and_metadata_and_warning(self):
        """Test read operation with sections, metadata, and warning when section not found."""
        # Arrange
        file_name = "projectBrief.md"
        content = "# Project Brief\n\n## Section 1\ncontent 1"
        temp_path = Path("/tmp/test/memory-bank/projectBrief.md")
        metadata_model = DetailedFileMetadata(
            path=str(temp_path),
            exists=True,
            size_bytes=100,
            token_count=25,
            token_model="cl100k_base",
            last_modified="2026-01-01T00:00:00",
            content_hash="hash123",
        )

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=temp_path)

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_fs.construct_safe_path.return_value = mock_path

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(return_value=metadata_model)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                    sections=["## Missing Section"],
                    include_metadata=True,
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "warning" in result
                assert "not found" in result["warning"].lower()
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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
        metadata_model = DetailedFileMetadata(
            path="/tmp/test/.cortex/memory-bank/test.md",
            exists=True,
            size_bytes=200,
            token_count=50,
            token_model="cl100k_base",
            last_modified="2026-01-01T00:00:00",
            content_hash="hash456",
        )

        # Create mock path that exists
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(return_value=metadata_model)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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

    async def test_manage_file_write_rejected_by_schema_validation(self):
        """Test write rejected when content fails pre-write schema validation."""
        # Arrange: content missing required sections for projectBrief.md
        file_name = "projectBrief.md"
        content = "# Project Brief\n\nNo required sections here."

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = file_name

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        schema_result = ValidationResultModel(
            valid=False,
            errors=[
                ValidationErrorModel(
                    type="missing_section",
                    severity=ValidationSeverity.ERROR,
                    message="Missing required section: Goals",
                    suggestion="Add ## Goals",
                ),
            ],
            warnings=[],
            score=30,
        )
        mock_schema_validator = MagicMock()
        mock_schema_validator.get_schema.return_value = MagicMock()
        mock_schema_validator.validate_file = AsyncMock(return_value=schema_result)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                with patch(
                    "cortex.tools.files.file_manage_file_helpers.get_manager",
                    new_callable=AsyncMock,
                    return_value=mock_schema_validator,
                ):
                    # Act
                    result_str = await manage_file(
                        file_name=file_name,
                        operation="write",
                        content=content,
                    )

        # Assert: write rejected, no disk write
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "schema" in result["error"].lower()
        assert result["file_name"] == file_name
        assert result["validation"]["valid"] is False
        mock_fs.write_file.assert_not_called()

    async def test_handle_write_operation_schema_validation_invalid_result(self):
        """Test handle_write_operation when schema validation returns invalid result (line 647-648)."""
        from cortex.tools.files.file_crud_flow import handle_write_operation

        # Arrange
        file_path = Path("/tmp/test/projectBrief.md")
        file_name = "projectBrief.md"
        content = "# Project Brief\n\nMissing required sections."

        mock_fs = AsyncMock()
        mock_tokens = MagicMock()
        mock_versions = AsyncMock()

        schema_result = ValidationResultModel(
            valid=False,
            errors=[
                ValidationErrorModel(
                    type="missing_section",
                    severity=ValidationSeverity.ERROR,
                    message="Missing required section: Goals",
                    suggestion="Add ## Goals",
                ),
            ],
            warnings=[],
            score=30,
        )
        mock_schema_validator = MagicMock()
        mock_schema_validator.get_schema.return_value = MagicMock()  # Schema exists
        mock_schema_validator.validate_file = AsyncMock(return_value=schema_result)

        mock_index = AsyncMock()

        # Mock file_path.exists() to return True
        with patch("pathlib.Path.exists", return_value=True):
            # Act
            result_str = await handle_write_operation(
                file_path=file_path,
                file_name=file_name,
                content=content,
                change_description=None,
                fs_manager=mock_fs,
                metadata_index=mock_index,
                token_counter=mock_tokens,
                version_manager=mock_versions,
                schema_validator=mock_schema_validator,
            )

            # Assert - should return schema validation error (line 647-648)
            assert isinstance(result_str, str), "write operation returns JSON str"
            result = json.loads(result_str)
            assert result["status"] == "error"
            err_msg = str(result.get("error", ""))
            assert "schema" in err_msg.lower() or "validation" in err_msg.lower()
            mock_schema_validator.validate_file.assert_called_once_with(
                file_name, content
            )

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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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

    async def test_manage_file_write_applies_corruption_fix_for_progress_md(self):
        """When writing progress.md, phrase corruption is fixed before write."""
        # Arrange: progress.md with phrase corruption (90.32coverage -> 90.32% coverage)
        file_name = "progress.md"
        corrupted = "## 2026-02-10\n\n- Item with 90.32coverage and 89.89to\n"
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = file_name

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)
        mock_fs.read_file = AsyncMock(return_value=("Existing progress", "disk_hash"))
        mock_fs.write_file = AsyncMock(return_value="new_hash")
        mock_fs.compute_hash = MagicMock(return_value="new_hash")

        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"content_hash": "stale_hash"}
        )
        mock_index.update_file_metadata = AsyncMock()
        mock_index.add_version_to_history = AsyncMock()

        mock_tokens = MagicMock()
        mock_tokens.count_tokens = MagicMock(return_value=30)

        mock_versions = AsyncMock()
        mock_versions.get_version_count = AsyncMock(return_value=1)
        version_info = MagicMock()
        version_info.version = 2
        version_info.snapshot_path = "/tmp/snapshots/progress.md.v2"
        mock_versions.create_snapshot = AsyncMock(return_value=version_info)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": mock_tokens,
            "versions": mock_versions,
        }

        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result_str = await manage_file(
                    file_name=file_name,
                    operation="write",
                    content=corrupted,
                    change_description="Test progress update",
                )

                # Assert
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["file_name"] == file_name
                written_content = mock_fs.write_file.call_args[0][1]
                assert "90.32% coverage" in written_content
                assert "89.89% to" in written_content

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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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

    async def test_manage_file_write_disallows_new_memory_bank_files(self):
        """Test write operation does not create new Memory Bank files."""
        # Arrange
        file_name = "newfile.md"
        content = "New content for nonexistent file"

        mock_parent = MagicMock()
        mock_parent.glob.return_value = []

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = False
        mock_path.name = file_name
        mock_path.parent = mock_parent

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
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
                assert "Cannot create new Memory Bank file" in result["error"]


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
            "cortex.tools.files.file_manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.file_crud_operations.get_or_resolve_project_root",
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
