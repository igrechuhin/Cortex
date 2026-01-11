"""
Comprehensive tests for Synapse Tools

This test suite provides comprehensive coverage for:
- sync_synapse()
- update_synapse_rule()
- get_synapse_rules()
- get_synapse_prompts()
- update_synapse_prompt()
- All helper functions and error paths
"""

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.tools.synapse_tools import (
    extract_and_format_rules,
    extract_rules_list,
    format_language_rules_list,
    format_rules_list,
    format_rules_response,
    get_synapse_rules,
    parse_project_files,
    sync_synapse,
    update_synapse_rule,
    validate_rules_manager,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root."""
    return tmp_path


@pytest.fixture
def mock_synapse_manager():
    """Create mock SharedRulesManager."""
    manager = MagicMock()
    manager.sync_synapse = AsyncMock(
        return_value={
            "status": "success",
            "changes": "2 files updated",
            "reindex_triggered": True,
        }
    )
    manager.update_synapse_rule = AsyncMock(
        return_value={"status": "success", "commit_sha": "abc123"}
    )
    return manager


@pytest.fixture
def mock_rules_manager() -> MagicMock:
    """Create mock RulesManager."""
    manager = MagicMock()
    manager.index_rules = AsyncMock(return_value={"indexed": 5})
    manager.get_relevant_rules = AsyncMock(
        return_value={
            "generic_rules": [
                {
                    "file": "coding-standards.md",
                    "tokens": 500,
                    "priority": "high",
                    "relevance_score": 0.8,
                }
            ],
            "language_rules": [
                {
                    "file": "python-style.md",
                    "category": "python",
                    "tokens": 300,
                    "priority": "medium",
                    "relevance_score": 0.9,
                }
            ],
            "local_rules": [
                {
                    "file": "project-rules.md",
                    "tokens": 200,
                    "priority": "high",
                    "relevance_score": 1.0,
                }
            ],
            "context": {
                "languages": ["python"],
                "frameworks": ["django"],
                "task_type": "authentication",
            },
            "total_tokens": 1000,
            "source": "mixed",
        }
    )
    return manager


@pytest.fixture
def mock_managers_with_synapse(
    mock_synapse_manager: MagicMock, mock_rules_manager: MagicMock
) -> dict[str, Any]:
    """Create managers dict with shared rules manager."""
    return {"synapse": mock_synapse_manager, "rules": mock_rules_manager}


@pytest.fixture
def mock_managers_without_synapse(
    mock_rules_manager: MagicMock,
) -> dict[str, MagicMock]:
    """Create managers dict without shared rules manager."""
    return {"rules": mock_rules_manager}


# ============================================================================
# Test sync_synapse()
# ============================================================================


class TestSyncSharedRules:
    """Tests for sync_synapse() tool."""

    async def test_sync_synapse_pull_only(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: dict[str, Any],
    ) -> None:
        """Test successful sync with pull only."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=mock_managers_with_synapse,
            ),
        ):
            # Act
            result_str = await sync_synapse(pull=True, push=False)
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "changes" in result
            synapse = mock_managers_with_synapse.get("synapse")
            if synapse is not None and hasattr(synapse, "sync_synapse"):
                synapse.sync_synapse.assert_called_once_with(pull=True, push=False)

    async def test_sync_synapse_with_reindex(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: dict[str, Any],
    ) -> None:
        """Test sync triggers reindex when changes detected."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=mock_managers_with_synapse,
            ),
        ):
            # Act
            result_str = await sync_synapse(pull=True, push=False)
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            mock_managers_with_synapse["rules"].index_rules.assert_called_once_with(
                force=True
            )

    async def test_sync_synapse_not_initialized(self, mock_project_root: Path) -> None:
        """Test sync fails when shared rules not initialized."""
        # Arrange
        managers = {}  # Empty managers dict
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=managers,
            ),
        ):
            # Act
            result_str = await sync_synapse()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "not initialized" in result["error"]

    async def test_sync_synapse_push_only(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: dict[str, Any],
    ) -> None:
        """Test successful sync with push only."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=mock_managers_with_synapse,
            ),
        ):
            # Act
            result_str = await sync_synapse(pull=False, push=True)
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            mock_managers_with_synapse["synapse"].sync_synapse.assert_called_once_with(
                pull=False, push=True
            )

    async def test_sync_synapse_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in sync_synapse."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                side_effect=RuntimeError("Network error"),
            ),
        ):
            # Act
            result_str = await sync_synapse()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Network error" in result["error"]
            assert result["error_type"] == "RuntimeError"


# ============================================================================
# Test update_synapse_rule()
# ============================================================================


class TestUpdateSharedRule:
    """Tests for update_synapse_rule() tool."""

    async def test_update_synapse_rule_success(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: dict[str, Any],
    ) -> None:
        """Test successful rule update."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=mock_managers_with_synapse,
            ),
        ):
            # Act
            result_str = await update_synapse_rule(
                category="python",
                file="style-guide.md",
                content="# Updated Style Guide\n\nNew content...",
                commit_message="Update Python style guide",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "commit_sha" in result
            mock_managers_with_synapse[
                "synapse"
            ].update_synapse_rule.assert_called_once()

    async def test_update_synapse_rule_not_initialized(
        self, mock_project_root: Path
    ) -> None:
        """Test update fails when shared rules not initialized."""
        # Arrange
        managers = {}  # Empty managers dict
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=managers,
            ),
        ):
            # Act
            result_str = await update_synapse_rule(
                category="python",
                file="test.md",
                content="test",
                commit_message="test",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "not initialized" in result["error"]

    async def test_update_synapse_rule_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in update_synapse_rule."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                side_effect=ValueError("Invalid category"),
            ),
        ):
            # Act
            result_str = await update_synapse_rule(
                category="invalid",
                file="test.md",
                content="test",
                commit_message="test",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Invalid category" in result["error"]
            assert result["error_type"] == "ValueError"


# ============================================================================
# Test get_synapse_rules()
# ============================================================================


class TestGetRulesWithContext:
    """Tests for get_synapse_rules() tool."""

    async def test_get_synapse_rules_success(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: dict[str, Any],
    ) -> None:
        """Test successful rules retrieval with context."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=mock_managers_with_synapse,
            ),
        ):
            # Act
            result_str = await get_synapse_rules(
                task_description="Implement JWT authentication",
                max_tokens=10000,
                project_files="auth.py,views.py",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "rules_loaded" in result
            assert "generic" in result["rules_loaded"]
            assert "language" in result["rules_loaded"]
            assert "local" in result["rules_loaded"]
            assert result["total_tokens"] == 1000
            assert result["token_budget"] == 10000

    async def test_get_synapse_rules_no_project_files(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: dict[str, Any],
    ) -> None:
        """Test rules retrieval without project files."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=mock_managers_with_synapse,
            ),
        ):
            # Act
            result_str = await get_synapse_rules(
                task_description="Implement authentication"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            mock_managers_with_synapse["rules"].get_relevant_rules.assert_called_once()

    async def test_get_synapse_rules_custom_parameters(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: dict[str, Any],
    ) -> None:
        """Test rules retrieval with custom parameters."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=mock_managers_with_synapse,
            ),
        ):
            # Act
            result_str = await get_synapse_rules(
                task_description="Fix bug",
                max_tokens=5000,
                min_relevance_score=0.5,
                rule_priority="shared_overrides_local",
                context_aware=False,
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["token_budget"] == 5000

    async def test_get_synapse_rules_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in get_synapse_rules."""
        # Arrange
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                side_effect=RuntimeError("Manager initialization failed"),
            ),
        ):
            # Act
            result_str = await get_synapse_rules(task_description="Test")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Manager initialization failed" in result["error"]


# ============================================================================
# Test Helper Functions
# ============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_format_rules_list(self):
        """Test _format_rules_list with valid input."""
        # Arrange
        rules = [
            {
                "file": "test.md",
                "tokens": 100,
                "priority": "high",
                "relevance_score": 0.9,
            }
        ]

        # Act
        result = format_rules_list(cast(list[object], rules))

        # Assert
        assert len(result) == 1
        assert result[0]["file"] == "test.md"
        assert result[0]["tokens"] == 100

    def test_format_rules_list_empty(self):
        """Test _format_rules_list with empty input."""
        # Arrange
        rules: list[object] = []

        # Act
        result = format_rules_list(rules)

        # Assert
        assert result == []

    def test_format_language_rules_list(self):
        """Test _format_language_rules_list with valid input."""
        # Arrange
        rules: list[object] = [
            {
                "file": "python.md",
                "category": "python",
                "tokens": 200,
                "priority": "medium",
                "relevance_score": 0.8,
            }
        ]

        # Act
        result = format_language_rules_list(rules)

        # Assert
        assert len(result) == 1
        assert result[0]["category"] == "python"
        assert result[0]["file"] == "python.md"

    def test_validate_rules_manager_with_manager(self):
        """Test _validate_rules_manager when manager exists."""
        # Arrange
        managers: dict[str, object] = {"rules": MagicMock()}

        # Act
        result = validate_rules_manager(managers)

        # Assert
        assert result is None

    def test_validate_rules_manager_without_manager(self):
        """Test _validate_rules_manager when manager missing."""
        # Arrange
        managers: dict[str, object] = {}

        # Act
        result = validate_rules_manager(managers)

        # Assert
        assert result is not None
        assert result["status"] == "error"
        assert "not initialized" in str(result.get("error", ""))

    def test_parse_project_files_with_files(self):
        """Test _parse_project_files with comma-separated files."""
        # Arrange
        project_files = "file1.py, file2.py, file3.py"

        # Act
        result = parse_project_files(project_files)

        # Assert
        assert result is not None
        assert len(result) == 3
        assert all(isinstance(p, Path) for p in result)

    def test_parse_project_files_empty_string(self):
        """Test _parse_project_files with empty string."""
        # Arrange
        project_files = ""

        # Act
        result = parse_project_files(project_files)

        # Assert
        assert result is None

    def test_parse_project_files_none(self):
        """Test _parse_project_files with None."""
        # Arrange
        project_files = None

        # Act
        result = parse_project_files(project_files)

        # Assert
        assert result is None

    def test_extract_rules_list(self):
        """Test _extract_rules_list with valid result."""
        # Arrange
        result: dict[str, object] = {"rules": [{"file": "test.md"}]}

        # Act
        rules = extract_rules_list(result, "rules")

        # Assert
        assert len(rules) == 1

    def test_extract_rules_list_missing_key(self):
        """Test _extract_rules_list with missing key."""
        # Arrange
        result: dict[str, object] = {}

        # Act
        rules = extract_rules_list(result, "missing")

        # Assert
        assert rules == []

    def test_extract_and_format_rules(self):
        """Test _extract_and_format_rules integration."""
        # Arrange
        result: dict[str, object] = {
            "generic_rules": [
                {
                    "file": "standards.md",
                    "tokens": 500,
                    "priority": "high",
                    "relevance_score": 0.9,
                }
            ]
        }

        # Act
        rules = extract_and_format_rules(result, "generic_rules")

        # Assert
        assert len(rules) == 1
        assert rules[0]["file"] == "standards.md"

    def test_format_rules_response(self):
        """Test _format_rules_response integration."""
        # Arrange
        result: dict[str, object] = {
            "generic_rules": [{"file": "test.md", "tokens": 100, "priority": "high"}],
            "language_rules": [],
            "local_rules": [],
            "context": {"languages": ["python"]},
            "total_tokens": 100,
            "source": "local_only",
        }

        # Act
        response = format_rules_response(result, "Test task", 5000)

        # Assert
        assert response["status"] == "success"
        assert response["task_description"] == "Test task"
        assert response["token_budget"] == 5000
        assert response["total_tokens"] == 100


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for full workflows."""

    async def test_full_rules_workflow(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: dict[str, Any],
    ) -> None:
        """Test complete workflow: sync -> get rules -> update."""
        with (
            patch(
                "cortex.tools.synapse_tools.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools.get_managers",
                return_value=mock_managers_with_synapse,
            ),
        ):
            # Act 1: Sync
            sync_result = await sync_synapse()
            sync_data = json.loads(sync_result)

            # Assert 1
            assert sync_data["status"] == "success"

            # Act 2: Get rules
            rules_result = await get_synapse_rules(task_description="Test task")
            rules_data = json.loads(rules_result)

            # Assert 2
            assert rules_data["status"] == "success"

            # Act 3: Update
            update_result = await update_synapse_rule(
                category="python",
                file="test.md",
                content="test",
                commit_message="test",
            )
            update_data = json.loads(update_result)

            # Assert 3
            assert update_data["status"] == "success"
