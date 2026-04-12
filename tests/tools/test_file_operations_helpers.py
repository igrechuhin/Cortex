"""file_operations helper and metrics tests."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.tools.files.operation_helpers import (
    FileOperation,
    build_invalid_operation_error,
    build_schema_validation_error_response,
    build_write_error_response,
    parse_file_operation,
    validate_write_content,
)
from cortex.tools.files.operations import (
    build_write_response,
    compute_file_metrics,
    create_version_snapshot,
    extract_sections,
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
        from cortex.tools.files.operation_helpers import validate_write_request

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
