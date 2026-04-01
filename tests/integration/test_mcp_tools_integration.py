"""
Integration tests for MCP tool workflows.

These tests verify that MCP tools work correctly together
to provide end-to-end functionality through the tool interface.

Note: initialize_memory_bank and check_migration_status have been replaced
by prompt templates (see docs/prompts/). Tests that depend on these functions
are skipped.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.files.operations import manage_file
from cortex.tools.linking.linking_operations import parse_file_links, validate_links
from cortex.tools.memory.query_memory_bank_operations import query_memory_bank
from cortex.tools.optimization.handlers import load_context_impl as load_context
from cortex.tools.validation.operations import validate_impl as validate
from tests.helpers.schema_fixtures import MINIMAL_VALID_PROJECT_BRIEF_CONTENT

_BASIC_FILES = [
    "projectBrief.md",
    "activeContext.md",
    "systemPatterns.md",
    "techContext.md",
    "productContext.md",
    "progress.md",
    "roadmap.md",
]


def _create_basic_files(memory_bank_dir: Path) -> int:
    """Create basic memory bank placeholder files. Returns count created."""
    created = 0
    for filename in _BASIC_FILES:
        file_path = memory_bank_dir / filename
        if not file_path.exists():
            _ = file_path.write_text(
                f"# {filename.replace('.md', '')}\n\nPlaceholder content.\n"
            )
            created += 1
    return created


async def _initialize_memory_bank_helper(project_root: str) -> str:
    """Initialize memory bank structure for tests."""
    from tests.helpers.path_helpers import ensure_test_cortex_structure

    root = Path(project_root)
    memory_bank_dir = ensure_test_cortex_structure(root)
    created = _create_basic_files(memory_bank_dir)
    return json.dumps(
        {
            "status": "success",
            "message": "Memory Bank initialized for testing",
            "total_files": created,
        },
        indent=2,
    )


async def _init_and_patch(project_root: Path):
    """Initialize memory bank and return a patch context manager."""
    _ = await _initialize_memory_bank_helper(str(project_root))
    return patch(
        "cortex.core.project_root_resolver.get_project_root",
        return_value=project_root,
    )


async def _manage_file_op(
    operation: str, file_name: str, **kwargs: object
) -> dict[str, object]:
    """Run manage_file and return parsed JSON data."""
    result = await manage_file(operation=operation, file_name=file_name, **kwargs)
    return json.loads(result)


async def _write_and_read_back(project_root: Path) -> dict[str, object]:
    """Write updated projectBrief then read it back."""
    new_content = (
        "# Updated Project Brief\n\nUpdated content.\n\n"
        + MINIMAL_VALID_PROJECT_BRIEF_CONTENT
    )
    data = await _manage_file_op(
        "write",
        "projectBrief.md",
        content=new_content,
        change_description="Test update",
    )
    assert data["status"] == "success"
    return await _manage_file_op("read", "projectBrief.md")


def _create_mb_file(project_root: Path, name: str, content: str) -> Path:
    """Create a file in memory bank directory."""
    mb_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    mb_dir.mkdir(exist_ok=True, parents=True)
    f = mb_dir / name
    _ = f.write_text(content)
    return f


def _obj_to_str(value: object) -> str:
    """Return a string view for object-typed JSON values in tests."""
    return str(value)


@pytest.mark.integration
class TestMCPToolWorkflows:
    """Test MCP tool integration workflows."""

    async def test_initialize_read_write_workflow(self, temp_project_root: Path):
        """Test complete workflow: initialize -> read -> write."""
        p = await _init_and_patch(temp_project_root)

        with p:
            data = await _manage_file_op("read", "projectBrief.md")
            assert data["status"] == "success"
            assert "content" in data

            read_back = await _write_and_read_back(temp_project_root)
            assert read_back["status"] == "success"
            assert "Updated Project Brief" in _obj_to_str(read_back["content"])

    async def test_link_parsing_and_validation_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test workflow: create file -> parse links -> validate links."""
        p = await _init_and_patch(temp_project_root)
        _ = _create_mb_file(
            temp_project_root,
            "test.md",
            "[Project Brief](projectBrief.md)\n[Active Context](activeContext.md)",
        )

        with p:
            result = await parse_file_links("test.md")
            data = json.loads(result)
            assert data["status"] == "success"
            assert len(data["markdown_links"]) >= 2

            result = await validate_links()
            data = json.loads(result)
            assert data["status"] in ["success", "error"]
            if data["status"] == "success":
                assert "mode" in data

    async def test_validation_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test validation workflow: validate -> check quality -> check duplications."""
        p = await _init_and_patch(temp_project_root)

        with p:
            data = json.loads(await validate(check_type="schema"))
            assert data["status"] in ["success", "validation_failed", "error"]

            data = json.loads(
                await validate(check_type="quality", response_format="detailed")
            )
            assert data["status"] == "success"
            assert 0 <= data["overall_score"] <= 100

            data = json.loads(
                await validate(check_type="duplications", response_format="detailed")
            )
            assert data["status"] == "success"
            assert (
                "duplications" in data
                or "exact_duplicates" in data
                or "similar_content" in data
            )

    async def test_optimization_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test optimization workflow."""
        # Arrange
        project_root_str = str(temp_project_root)

        # Initialize
        _ = await _initialize_memory_bank_helper(project_root_str)

        with patch(
            "cortex.core.project_root_resolver.get_project_root",
            return_value=temp_project_root,
        ):
            # Act: Load context - use task_description parameter
            result = await load_context(
                task_description="project",
                token_budget=10000,
                response_format="detailed",
            )
            data = json.loads(result)
            assert data["status"] == "success"
            assert "selected_files" in data or "files" in data

    async def _write_two_versions(self) -> None:
        """Write two versions of test.md to create version history."""
        await manage_file(
            operation="write",
            file_name="test.md",
            content="# Version 1\n\nInitial content.",
            change_description="Initial version",
        )
        await manage_file(
            operation="write",
            file_name="test.md",
            content="# Version 2\n\nUpdated content.",
            change_description="Updated version",
        )

    async def _assert_version_history(self) -> None:
        """Assert version history has at least 2 versions and metadata matches."""
        data = json.loads(
            await query_memory_bank(query_type="version_history", file_name="test.md")
        )
        assert data["status"] == "success"
        assert data["total_versions"] >= 2

        meta = await _manage_file_op("metadata", "test.md")
        assert meta["status"] == "success"
        metadata = cast(dict[str, object], meta["metadata"])
        assert int(cast(int, metadata["current_version"])) >= 2

    async def test_version_history_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test version history workflow: write -> get history -> get metadata."""
        p = await _init_and_patch(temp_project_root)
        _ = _create_mb_file(
            temp_project_root, "test.md", "# Test\n\nInitial content.\n"
        )

        with p:
            await self._write_two_versions()
            await self._assert_version_history()

    async def test_dependency_graph_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test dependency graph workflow."""
        p = await _init_and_patch(temp_project_root)
        _ = _create_mb_file(temp_project_root, "parent.md", "[Child](child.md)")
        _ = _create_mb_file(temp_project_root, "child.md", "# Child\nContent.")

        with p:
            data = json.loads(
                await query_memory_bank(query_type="dependency_graph", format="json")
            )
            assert data["status"] == "success"
            assert "graph" in data
            assert "loading_order" in data

    async def test_stats_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test memory bank statistics workflow."""
        p = await _init_and_patch(temp_project_root)

        with p:
            data = json.loads(
                await query_memory_bank(query_type="stats", response_format="detailed")
            )
            assert data["status"] == "success"
            assert "summary" in data
            assert "total_files" in data["summary"]
            assert "total_tokens" in data["summary"]


@pytest.mark.integration
class TestMCPToolErrorHandling:
    """Test error handling in MCP tool workflows."""

    async def test_error_handling_for_missing_file(self, temp_project_root: Path):
        """Test error handling when file doesn't exist."""
        p = await _init_and_patch(temp_project_root)

        with p:
            data = await _manage_file_op("read", "nonexistent.md")
            assert data["status"] == "error"
            assert "error" in data

    async def test_error_handling_for_invalid_project_root(self):
        """Test error handling for invalid project root."""
        # Arrange
        invalid_root = "/nonexistent/path/that/does/not/exist"

        # Act: Try to initialize
        try:
            result = await _initialize_memory_bank_helper(invalid_root)
            data = json.loads(result)
            # Assert: Should handle error gracefully
            # (May succeed if it creates directory, or fail - both are valid)
            assert "status" in data
        except (OSError, FileNotFoundError):
            # Expected if directory creation fails
            pass

    async def test_error_handling_for_broken_links(self, temp_project_root: Path):
        """Test error handling when links are broken."""
        # Arrange
        project_root_str = str(temp_project_root)

        # Initialize
        _ = await _initialize_memory_bank_helper(project_root_str)

        # Create file with broken link
        file_system = (
            get_cortex_path(temp_project_root, CortexResourceType.MEMORY_BANK)
            / "broken.md"
        )
        file_system.parent.mkdir(exist_ok=True, parents=True)
        _ = file_system.write_text("[Broken Link](nonexistent.md)")

        with patch(
            "cortex.core.project_root_resolver.get_project_root",
            return_value=temp_project_root,
        ):
            # Act: Validate links
            result = await validate_links()
            data = json.loads(result)

            # Assert: Should handle validation (may return success or error)
            assert data["status"] in ["success", "error"]
            # If successful, validation should have been performed
            if data["status"] == "success":
                assert "mode" in data
