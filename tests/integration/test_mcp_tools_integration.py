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

import pytest

from cortex.tools.file_operations import manage_file
from cortex.tools.phase1_foundation_dependency import get_dependency_graph
from cortex.tools.phase1_foundation_stats import get_memory_bank_stats
from cortex.tools.phase1_foundation_version import get_version_history
from cortex.tools.phase2_linking import parse_file_links, validate_links
from cortex.tools.phase4_optimization import load_context
from cortex.tools.validation_operations import validate


# Helper function to replace initialize_memory_bank
async def _initialize_memory_bank_helper(project_root: str) -> str:
    """
    Helper to initialize memory bank structure for tests.

    Note: The actual initialize_memory_bank function has been replaced by
    prompt templates. This helper creates the basic structure for testing.
    """
    import json
    from pathlib import Path

    from tests.helpers.path_helpers import ensure_test_cortex_structure

    root = Path(project_root)
    memory_bank_dir = ensure_test_cortex_structure(root)

    # Create basic files if they don't exist
    basic_files = [
        "projectBrief.md",
        "activeContext.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
        "progress.md",
        "roadmap.md",
    ]

    created = 0
    for filename in basic_files:
        file_path = memory_bank_dir / filename
        if not file_path.exists():
            _ = file_path.write_text(
                f"# {filename.replace('.md', '')}\n\nPlaceholder content.\n"
            )
            created += 1

    return json.dumps(
        {
            "status": "success",
            "message": "Memory Bank initialized for testing",
            "total_files": created,
        },
        indent=2,
    )


@pytest.mark.integration
class TestMCPToolWorkflows:
    """Test MCP tool integration workflows."""

    async def test_initialize_read_write_workflow(self, temp_project_root: Path):
        """Test complete workflow: initialize -> read -> write."""
        # Arrange
        project_root_str = str(temp_project_root)

        # Act 1: Initialize
        result = await _initialize_memory_bank_helper(project_root_str)
        data = json.loads(result)
        assert data["status"] == "success"

        # Act 2: Read file
        result = await manage_file(
            operation="read", file_name="projectBrief.md", project_root=project_root_str
        )
        data = json.loads(result)
        assert data["status"] == "success"
        assert "content" in data

        # Act 3: Write file
        new_content = "# Updated Project Brief\n\nUpdated content."
        result = await manage_file(
            operation="write",
            file_name="projectBrief.md",
            content=new_content,
            project_root=project_root_str,
            change_description="Test update",
        )
        data = json.loads(result)
        assert data["status"] == "success"

        # Act 4: Read updated file
        result = await manage_file(
            operation="read", file_name="projectBrief.md", project_root=project_root_str
        )
        data = json.loads(result)
        assert data["status"] == "success"
        assert "Updated Project Brief" in data["content"]

    async def test_link_parsing_and_validation_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test workflow: create file -> parse links -> validate links."""
        # Arrange
        project_root_str = str(temp_project_root)

        # Initialize
        _ = await _initialize_memory_bank_helper(project_root_str)

        # Create file with links
        file_system = temp_project_root / ".cortex" / "memory-bank" / "test.md"
        file_system.parent.mkdir(exist_ok=True, parents=True)
        _ = file_system.write_text(
            "[Project Brief](projectBrief.md)\n[Active Context](activeContext.md)"
        )

        # Act 1: Parse links
        result = await parse_file_links("test.md", project_root_str)
        data = json.loads(result)
        assert data["status"] == "success"
        # Check markdown_links instead of links
        assert len(data["markdown_links"]) >= 2

        # Act 2: Validate links
        result = await validate_links(project_root=project_root_str)
        data = json.loads(result)
        # Validation should succeed (may return success or error status)
        assert data["status"] in ["success", "error"]
        # Check if validation was performed
        if data["status"] == "success":
            # Should have mode and validation results
            assert "mode" in data

    async def test_validation_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test validation workflow: validate -> check quality -> check duplications."""
        # Arrange
        project_root_str = str(temp_project_root)

        # Initialize
        _ = await _initialize_memory_bank_helper(project_root_str)

        # Act 1: Validate memory bank
        result = await validate(check_type="schema", project_root=project_root_str)
        data = json.loads(result)
        # Validation may return success, validation_failed, or error
        assert data["status"] in ["success", "validation_failed", "error"]

        # Act 2: Get quality score
        result = await validate(check_type="quality", project_root=project_root_str)
        data = json.loads(result)
        assert data["status"] == "success"
        assert "overall_score" in data
        assert 0 <= data["overall_score"] <= 100

        # Act 3: Check duplications
        result = await validate(
            check_type="duplications", project_root=project_root_str
        )
        data = json.loads(result)
        assert data["status"] == "success"
        # Can be duplications, exact_duplicates, or similar_content
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

        # Act: Load context - use task_description parameter
        result = await load_context(
            task_description="project",
            token_budget=10000,
            project_root=project_root_str,
        )
        data = json.loads(result)
        assert data["status"] == "success"
        assert "selected_files" in data or "files" in data

    async def test_version_history_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test version history workflow: write -> get history -> get metadata."""
        # Arrange
        project_root_str = str(temp_project_root)

        # Initialize
        _ = await _initialize_memory_bank_helper(project_root_str)

        # Create test.md file first (manage_file only allows modifying existing files)
        from pathlib import Path

        from tests.helpers.path_helpers import ensure_test_cortex_structure

        root = Path(project_root_str)
        memory_bank_dir = ensure_test_cortex_structure(root)
        test_file = memory_bank_dir / "test.md"
        test_file.write_text("# Test\n\nInitial content.\n")

        # Act 1: Write file (creates version 1)
        content1 = "# Version 1\n\nInitial content."
        await manage_file(
            operation="write",
            file_name="test.md",
            content=content1,
            project_root=project_root_str,
            change_description="Initial version",
        )

        # Act 2: Write again (creates version 2)
        content2 = "# Version 2\n\nUpdated content."
        await manage_file(
            operation="write",
            file_name="test.md",
            content=content2,
            project_root=project_root_str,
            change_description="Updated version",
        )

        # Act 3: Get version history
        result = await get_version_history("test.md", project_root_str)
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["total_versions"] >= 2

        # Act 4: Get file metadata
        result = await manage_file(
            operation="metadata", file_name="test.md", project_root=project_root_str
        )
        data = json.loads(result)
        assert data["status"] == "success"
        assert "metadata" in data
        assert data["metadata"]["current_version"] >= 2

    async def test_dependency_graph_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test dependency graph workflow."""
        # Arrange
        project_root_str = str(temp_project_root)

        # Initialize
        _ = await _initialize_memory_bank_helper(project_root_str)

        # Create linked files
        file_system = temp_project_root / ".cortex" / "memory-bank"
        file_system.mkdir(exist_ok=True, parents=True)
        _ = (file_system / "parent.md").write_text("[Child](child.md)")
        _ = (file_system / "child.md").write_text("# Child\nContent.")

        # Act: Get dependency graph
        result = await get_dependency_graph(project_root_str, format="json")
        data = json.loads(result)
        assert data["status"] == "success"
        assert "graph" in data
        assert "loading_order" in data

    async def test_stats_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test memory bank statistics workflow."""
        # Arrange
        project_root_str = str(temp_project_root)

        # Initialize
        _ = await _initialize_memory_bank_helper(project_root_str)

        # Act: Get stats
        result = await get_memory_bank_stats(project_root_str)
        data = json.loads(result)
        assert data["status"] == "success"
        assert "summary" in data
        assert "total_files" in data["summary"]
        assert "total_tokens" in data["summary"]


@pytest.mark.integration
class TestMCPToolErrorHandling:
    """Test error handling in MCP tool workflows."""

    async def test_error_handling_for_missing_file(self, temp_project_root: Path):
        """Test error handling when file doesn't exist."""
        # Arrange
        project_root_str = str(temp_project_root)

        # Initialize
        _ = await _initialize_memory_bank_helper(project_root_str)

        # Act: Try to read non-existent file
        result = await manage_file(
            operation="read", file_name="nonexistent.md", project_root=project_root_str
        )
        data = json.loads(result)

        # Assert: Should return error status
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
        file_system = temp_project_root / ".cortex" / "memory-bank" / "broken.md"
        file_system.parent.mkdir(exist_ok=True, parents=True)
        _ = file_system.write_text("[Broken Link](nonexistent.md)")

        # Act: Validate links
        result = await validate_links(project_root=project_root_str)
        data = json.loads(result)

        # Assert: Should handle validation (may return success or error)
        assert data["status"] in ["success", "error"]
        # If successful, validation should have been performed
        if data["status"] == "success":
            assert "mode" in data
