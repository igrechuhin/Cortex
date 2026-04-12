"""manage_file edge-case tests."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.models import ResponseStatus
from cortex.tools.files.operations import (
    manage_file,
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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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

    async def test_manage_file_read_log_md_returns_content(self) -> None:
        """manage_file read supports log.md content retrieval."""
        file_name = "log.md"
        content = (
            "# Cortex Operations Log\n\n## [2026-04-07T14:01] plan | Created plan\n\n"
        )

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = file_name

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash-log"))
        mock_fs.construct_safe_path = MagicMock(return_value=mock_path)

        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                result_str = await manage_file(file_name=file_name, operation="read")

        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["file_name"] == file_name and result["content"] == content

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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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
            "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=Path("/tmp/test"),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_managers",
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
            "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=Path("/tmp/test"),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.execute_file_operation",
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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
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

    async def test_manage_file_zero_arg_defaults_to_read_active_context(
        self,
    ) -> None:
        """manage_file() with no args defaults to reading activeContext.md (zero-arg safe)."""
        # Act — zero-arg call should use defaults, not error
        result_str = await manage_file()  # type: ignore[call-arg]
        result = json.loads(result_str)

        # Assert — should succeed or return file-not-found (not missing-params error)
        assert result["status"] in ("success", "error")
        if result["status"] == "error":
            # File may not exist in test env, but error should be about the file
            assert "missing required parameters" not in result.get("error", "").lower()

    async def test_manage_file_missing_file_name_defaults_to_active_context(
        self,
    ) -> None:
        """manage_file(operation=read) with no file_name defaults to activeContext.md."""
        # Act
        result_str = await manage_file(operation="read")
        result = json.loads(result_str)

        # Assert — should use default file_name, not error about missing params
        assert result["status"] in ("success", "error")
        if result["status"] == "error":
            assert "missing required parameters" not in result.get("error", "").lower()

    async def test_manage_file_missing_operation_defaults_to_read(
        self,
    ) -> None:
        """manage_file(file_name=X) with no operation defaults to read."""
        # Act
        result_str = await manage_file(file_name="projectBrief.md")
        result = json.loads(result_str)

        # Assert — should default to read, not error about missing params
        assert result["status"] in ("success", "error")
        if result["status"] == "error":
            assert "missing required parameters" not in result.get("error", "").lower()
