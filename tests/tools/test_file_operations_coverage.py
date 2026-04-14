"""manage_file coverage completion tests."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import DetailedFileMetadata
from cortex.tools.files.operation_helpers import (
    FileOperation,
)
from cortex.tools.files.operations import (
    manage_file,
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
                assert "metadata" in result
                assert result["metadata"]["size_bytes"] == 100

    async def test_manage_file_log_result_non_dict_response(self):
        """Test _log_result_by_status when result is not a dict (line 447)."""
        from cortex.tools.files.manage_file_helpers import log_result_by_status

        # Arrange
        file_name = "test.md"
        result_str = '["not", "a", "dict"]'  # JSON array, not dict
        parsed_op = FileOperation.READ

        ctx = MagicMock()

        with patch(
            "cortex.tools.files.manage_file_helpers.log_client",
            new_callable=AsyncMock,
        ) as mock_log_client:
            # Act - call _log_result_by_status directly with non-dict JSON
            await log_result_by_status(ctx, file_name, parsed_op, result_str)

            # Assert - should have logged without error (handles non-dict gracefully)
            # The function should complete without raising
            # When result is not a dict, it should still call log_client
            assert mock_log_client.called

    async def test_write_file_with_hash_check_existing_file(self):
        """Test _write_file_with_hash_check when file exists (line 924-926)."""
        from cortex.tools.files.crud_flow import write_file_with_hash_check

        # Arrange
        content = "new content"
        expected_hash = "existing_hash"

        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=("old content", expected_hash))
        mock_fs.write_file = AsyncMock(return_value=None)

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        # Act
        await write_file_with_hash_check(mock_path, content, mock_fs)

        # Assert
        mock_fs.read_file.assert_called_once_with(mock_path)
        mock_fs.write_file.assert_called_once_with(
            mock_path, content, expected_hash=expected_hash
        )

    async def test_resolve_schema_validator_exception_handling(self):
        """Test _resolve_schema_validator exception handling (line 1023-1024)."""

        from cortex.managers.types import ManagersDict
        from cortex.tools.files.manage_file_helpers import resolve_schema_validator

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
        result = await resolve_schema_validator(managers)

        # Assert - should return None when schema_validator not available
        assert result is None

    async def test_get_managers_for_root_creates_new_when_root_differs(self):
        """Test get_managers_for_root creates new managers when root differs."""
        from cortex.core.usage_context import (
            set_current_managers,
            set_current_project_root,
        )
        from cortex.tools.files.manage_file_helpers import get_managers_for_root

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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            # Act
            managers, fs = await get_managers_for_root(new_root)

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
            "cortex.tools.files.manage_file_helpers.get_managers",
            new_callable=AsyncMock,
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                with patch(
                    "cortex.tools.files.manage_file_helpers.get_manager",
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
        from cortex.tools.files.crud_flow import handle_write_operation

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
                mock_fs.write_file.assert_called_once()
                write_call = mock_fs.write_file.await_args
                assert write_call is not None
                assert write_call.args[0] == mock_path
                assert write_call.kwargs["expected_hash"] == "disk_hash"
                assert content in str(write_call.args[1])
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
                assert "Cannot create new Memory Bank file" in result["error"]
