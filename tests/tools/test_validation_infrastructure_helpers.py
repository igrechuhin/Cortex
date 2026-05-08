"""Split from test_validation_operations.py to keep file size under limits."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.validation.helpers import (
    create_invalid_check_type_error,
    create_validation_error_response,
)
from cortex.tools.validation.infrastructure import (
    handle_infrastructure_validation,
)
from tests.tools.validation_operations_support import (
    setup_infrastructure_success_workspace,
)


class TestErrorHelpers:
    """Test error response helper functions."""

    def test_create_invalid_check_type_error(self) -> None:
        """Test creation of invalid check type error response."""
        # Act
        result = create_invalid_check_type_error("invalid_type")

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "invalid_type" in result_data["error"]
        assert "available_options" in result_data
        assert "schema" in result_data["available_options"]
        assert "duplications" in result_data["available_options"]
        assert "quality" in result_data["available_options"]
        assert "suggestion" in result_data
        assert "example" in result_data

    def test_create_validation_error_response(self) -> None:
        """Test creation of validation error response."""
        # Arrange
        error = ValueError("Test error message")

        # Act
        result = create_validation_error_response(error)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert result_data["error"] == "Test error message"
        assert result_data["error_type"] == "ValueError"

    def test_create_invalid_check_type_error_includes_infrastructure(self) -> None:
        """Test that invalid check type error includes infrastructure."""
        # Act
        result = create_invalid_check_type_error("invalid_type")

        # Assert
        result_data = json.loads(result)
        assert "infrastructure" in result_data["available_options"]


class TestHandleInfrastructureValidation:
    """Test infrastructure validation handler."""

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_success(
        self, tmp_path: Path
    ) -> None:
        """Test successful infrastructure validation."""
        setup_infrastructure_success_workspace(tmp_path)

        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=True,
            check_code_quality_consistency=True,
            check_documentation_consistency=True,
            check_config_consistency=True,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["check_type"] == "infrastructure"
        assert "checks_performed" in result_data
        assert "issues_found" in result_data
        assert "recommendations" in result_data

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_ci_file(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with missing CI workflow file."""
        # Arrange
        synapse_dir = get_cortex_path(tmp_path, CortexResourceType.SYNAPSE) / "prompts"
        synapse_dir.mkdir(parents=True)
        commit_file = synapse_dir / "commit.md"
        _ = commit_file.write_text("# Commit\n\n1. **Test step**\n   Description")

        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=True,
            check_code_quality_consistency=False,
            check_documentation_consistency=False,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_file" for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_commit_file(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with missing commit prompt file."""
        # Arrange
        github_dir = tmp_path / ".github" / "workflows"
        github_dir.mkdir(parents=True)
        workflow_file = github_dir / "quality.yml"
        _ = workflow_file.write_text(
            "name: Test\njobs:\n  test:\n    steps:\n      - name: Test step"
        )

        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=True,
            check_code_quality_consistency=False,
            check_documentation_consistency=False,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_file" for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_code_quality_check(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with code quality consistency check."""
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=True,
            check_documentation_consistency=False,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "code_quality_consistency" in result_data["checks_performed"]

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_documentation_check(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with documentation consistency check."""
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=False,
            check_documentation_consistency=True,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "documentation_consistency" in result_data["checks_performed"]

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_config_check(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation with configuration consistency check."""
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=False,
            check_documentation_consistency=False,
            check_config_consistency=True,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "config_consistency" in result_data["checks_performed"]

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_scripts(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation detects missing code quality scripts."""
        # Arrange - no scripts directory
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=True,
            check_documentation_consistency=False,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_script" for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_readme(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation detects missing README."""
        # Arrange - no README.md
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=False,
            check_documentation_consistency=True,
            check_config_consistency=False,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_documentation"
            for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_missing_configs(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation detects missing config files."""
        # Arrange - no .cortex directory
        # Act
        result = await handle_infrastructure_validation(
            tmp_path,
            check_commit_ci_alignment=False,
            check_code_quality_consistency=False,
            check_documentation_consistency=False,
            check_config_consistency=True,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert len(result_data["issues_found"]) > 0
        assert any(
            issue["type"] == "missing_config" for issue in result_data["issues_found"]
        )

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_yaml_none(
        self, tmp_path: Path
    ) -> None:
        """Test infrastructure validation when yaml module is not available."""
        # Arrange
        github_dir = tmp_path / ".github" / "workflows"
        github_dir.mkdir(parents=True)
        workflow_file = github_dir / "quality.yml"
        _ = workflow_file.write_text("name: Test")

        synapse_dir = get_cortex_path(tmp_path, CortexResourceType.SYNAPSE) / "prompts"
        synapse_dir.mkdir(parents=True)
        commit_file = synapse_dir / "commit.md"
        _ = commit_file.write_text("# Commit")

        # Mock yaml as None
        with patch("cortex.validation.infrastructure_validator.yaml", None):
            # Act
            result = await handle_infrastructure_validation(
                tmp_path,
                check_commit_ci_alignment=True,
                check_code_quality_consistency=False,
                check_documentation_consistency=False,
                check_config_consistency=False,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            # Should still complete without errors even if yaml is None
