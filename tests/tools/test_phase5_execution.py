"""
Comprehensive tests for Phase 5.3-5.4: Safe Execution and Learning Tools

This test suite provides comprehensive coverage for:
- apply_refactoring() with approve/apply/rollback actions
- provide_feedback()
- All helper functions and error paths
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.refactoring.refactoring_engine import RefactoringSuggestion
from cortex.tools.phase5_execution import apply_refactoring, provide_feedback

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root."""
    return tmp_path


@pytest.fixture
def mock_refactoring_suggestion():
    """Create mock refactoring suggestion."""
    suggestion = MagicMock()
    suggestion.to_dict.return_value = {
        "suggestion_id": "test-123",
        "refactoring_type": "consolidation",
        "confidence_score": 0.85,
        "files_affected": ["file1.py", "file2.py"],
        "description": "Test refactoring",
    }
    suggestion.refactoring_type.value = "consolidation"
    suggestion.confidence_score = 0.85
    return suggestion


@pytest.fixture
def mock_managers(
    mock_refactoring_suggestion: RefactoringSuggestion,
) -> dict[str, Any]:
    """Create mock managers dictionary."""
    approval_manager = MagicMock()
    approval_manager.approve_suggestion = AsyncMock(
        return_value={
            "status": "success",
            "approval_id": "approval-123",
            "message": "Approved successfully",
        }
    )
    approval_manager.get_approvals_for_suggestion = AsyncMock(
        return_value=[
            {
                "approval_id": "approval-123",
                "status": "approved",
                "timestamp": "2026-01-04T12:00:00",
            }
        ]
    )
    approval_manager.mark_as_applied = AsyncMock(
        return_value={"status": "success", "marked": True}
    )

    refactoring_engine = MagicMock()
    refactoring_engine.get_suggestion = AsyncMock(
        return_value=mock_refactoring_suggestion
    )

    refactoring_executor = MagicMock()
    refactoring_executor.execute_refactoring = AsyncMock(
        return_value={
            "status": "success",
            "execution_id": "exec-123",
            "files_modified": ["file1.py"],
            "changes_applied": 5,
        }
    )

    rollback_manager = MagicMock()
    rollback_manager.rollback_refactoring = AsyncMock(
        return_value={
            "status": "success",
            "execution_id": "exec-123",
            "files_restored": ["file1.py"],
            "snapshot_restored": True,
        }
    )

    learning_engine = MagicMock()
    learning_engine.record_feedback = AsyncMock(
        return_value={
            "status": "success",
            "feedback_recorded": True,
            "confidence_adjusted": 0.87,
        }
    )
    learning_engine.get_learning_insights = AsyncMock(
        return_value={
            "total_feedback": 100,
            "approval_rate": 0.85,
            "min_confidence_threshold": 0.6,
            "total_suggestions": 120,
        }
    )

    return {
        "approval_manager": approval_manager,
        "refactoring_engine": refactoring_engine,
        "refactoring_executor": refactoring_executor,
        "rollback_manager": rollback_manager,
        "learning_engine": learning_engine,
    }


# ============================================================================
# Test apply_refactoring() - Approve Action
# ============================================================================


class TestApplyRefactoringApprove:
    """Tests for apply_refactoring() with approve action."""

    async def test_approve_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test successful approval."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="approve", suggestion_id="test-123"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["approval_id"] == "approval-123"
            mock_managers["approval_manager"].approve_suggestion.assert_called_once()

    async def test_approve_with_auto_apply(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test approval with auto-apply enabled."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="approve", suggestion_id="test-123", auto_apply=True
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            mock_managers[
                "approval_manager"
            ].approve_suggestion.assert_called_once_with(
                suggestion_id="test-123", user_comment=None, auto_apply=True
            )

    async def test_approve_with_user_comment(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test approval with user comment."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="approve",
                suggestion_id="test-123",
                user_comment="Looks good!",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_approve_missing_suggestion_id(self, mock_project_root: Path) -> None:
        """Test approval without suggestion_id."""
        # Arrange
        with patch(
            "cortex.tools.phase5_execution.get_project_root",
            return_value=mock_project_root,
        ):
            # Act
            result_str = await apply_refactoring(action="approve")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "suggestion_id is required" in result["error"]


# ============================================================================
# Test apply_refactoring() - Apply Action
# ============================================================================


class TestApplyRefactoringApply:
    """Tests for apply_refactoring() with apply action."""

    async def test_apply_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test successful application of approved refactoring."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="apply", suggestion_id="test-123"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["execution_id"] == "exec-123"
            mock_managers[
                "refactoring_executor"
            ].execute_refactoring.assert_called_once()

    async def test_apply_with_approval_id(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test application with explicit approval_id."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="apply", suggestion_id="test-123", approval_id="approval-123"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_apply_dry_run(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test application in dry-run mode."""
        # Arrange
        mock_managers["refactoring_executor"].execute_refactoring = AsyncMock(
            return_value={
                "status": "success",
                "execution_id": "exec-dry-123",
                "dry_run": True,
                "would_modify": ["file1.py"],
            }
        )

        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="apply", suggestion_id="test-123", dry_run=True
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            mock_managers[
                "approval_manager"
            ].mark_as_applied.assert_not_called()  # No marking in dry-run

    async def test_apply_suggestion_not_found(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test application when suggestion not found."""
        # Arrange
        mock_managers["refactoring_engine"].get_suggestion = AsyncMock(
            return_value=None
        )

        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="apply", suggestion_id="nonexistent"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "not found" in result["error"]

    async def test_apply_no_approval(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test application when no approval exists."""
        # Arrange
        mock_managers["approval_manager"].get_approvals_for_suggestion = AsyncMock(
            return_value=[]
        )

        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="apply", suggestion_id="test-123"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "No approval found" in result["error"]

    async def test_apply_missing_suggestion_id(self, mock_project_root: Path) -> None:
        """Test application without suggestion_id."""
        # Arrange
        with patch(
            "cortex.tools.phase5_execution.get_project_root",
            return_value=mock_project_root,
        ):
            # Act
            result_str = await apply_refactoring(action="apply")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "suggestion_id is required" in result["error"]


# ============================================================================
# Test apply_refactoring() - Rollback Action
# ============================================================================


class TestApplyRefactoringRollback:
    """Tests for apply_refactoring() with rollback action."""

    async def test_rollback_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test successful rollback."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="rollback", execution_id="exec-123"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["execution_id"] == "exec-123"
            mock_managers["rollback_manager"].rollback_refactoring.assert_called_once()

    async def test_rollback_with_options(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test rollback with restore and preserve options."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="rollback",
                execution_id="exec-123",
                restore_snapshot=True,
                preserve_manual_changes=False,
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            mock_managers[
                "rollback_manager"
            ].rollback_refactoring.assert_called_once_with(
                execution_id="exec-123",
                restore_snapshot=True,
                preserve_manual_changes=False,
                dry_run=False,
            )

    async def test_rollback_dry_run(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test rollback in dry-run mode."""
        # Arrange
        mock_managers["rollback_manager"].rollback_refactoring = AsyncMock(
            return_value={
                "status": "success",
                "dry_run": True,
                "would_restore": ["file1.py"],
            }
        )

        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="rollback", execution_id="exec-123", dry_run=True
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["dry_run"] is True

    async def test_rollback_missing_execution_id(self, mock_project_root: Path) -> None:
        """Test rollback without execution_id."""
        # Arrange
        with patch(
            "cortex.tools.phase5_execution.get_project_root",
            return_value=mock_project_root,
        ):
            # Act
            result_str = await apply_refactoring(action="rollback")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "execution_id is required" in result["error"]


# ============================================================================
# Test apply_refactoring() - Edge Cases
# ============================================================================


class TestApplyRefactoringEdgeCases:
    """Tests for apply_refactoring() edge cases."""

    async def test_invalid_action(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test with invalid action."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="invalid_action", suggestion_id="test-123"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Invalid action" in result["error"]

    async def test_exception_handling(self, mock_project_root: Path) -> None:
        """Test exception handling in apply_refactoring."""
        # Arrange
        with patch(
            "cortex.tools.phase5_execution.get_project_root",
            side_effect=RuntimeError("Test error"),
        ):
            # Act
            result_str = await apply_refactoring(
                action="approve", suggestion_id="test-123"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Test error" in result["error"]
            assert result["error_type"] == "RuntimeError"


# ============================================================================
# Test provide_feedback()
# ============================================================================


class TestProvideFeedback:
    """Tests for provide_feedback() tool."""

    async def test_provide_feedback_helpful(
        self,
        mock_project_root: Path,
        mock_managers: dict[str, Any],
        mock_refactoring_suggestion: RefactoringSuggestion,
    ) -> None:
        """Test providing helpful feedback."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await provide_feedback(
                suggestion_id="test-123",
                feedback_type="helpful",
                comment="This was very useful",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["feedback_recorded"] is True
            assert "learning_summary" in result
            learning_engine = mock_managers.get("learning_engine")
            if learning_engine is not None and hasattr(
                learning_engine, "record_feedback"
            ):
                learning_engine.record_feedback.assert_called_once()

    async def test_provide_feedback_not_helpful(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test providing not_helpful feedback."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await provide_feedback(
                suggestion_id="test-123",
                feedback_type="not_helpful",
                comment="Not relevant to my needs",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_provide_feedback_incorrect(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test providing incorrect feedback."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await provide_feedback(
                suggestion_id="test-123",
                feedback_type="incorrect",
                comment="This would break the code",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_provide_feedback_without_comment(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test providing feedback without comment."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await provide_feedback(
                suggestion_id="test-123", feedback_type="helpful"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_provide_feedback_suggestion_not_found(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test feedback for non-existent suggestion."""
        # Arrange
        refactoring_engine = mock_managers.get("refactoring_engine")
        if refactoring_engine is not None and hasattr(
            refactoring_engine, "get_suggestion"
        ):
            refactoring_engine.get_suggestion = AsyncMock(return_value=None)

        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await provide_feedback(
                suggestion_id="nonexistent", feedback_type="helpful"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "not found" in result["error"]

    async def test_provide_feedback_with_applied_status(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test feedback for already applied suggestion."""
        # Arrange
        approval_manager = mock_managers.get("approval_manager")
        if approval_manager is not None and hasattr(
            approval_manager, "get_approvals_for_suggestion"
        ):
            approval_manager.get_approvals_for_suggestion = AsyncMock(
                return_value=[
                    {
                        "approval_id": "approval-123",
                        "status": "applied",
                        "timestamp": "2026-01-04T12:00:00",
                    }
                ]
            )

        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await provide_feedback(
                suggestion_id="test-123", feedback_type="helpful"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "learning_summary" in result

    async def test_provide_feedback_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in provide_feedback."""
        # Arrange
        with patch(
            "cortex.tools.phase5_execution.get_project_root",
            side_effect=ValueError("Invalid feedback"),
        ):
            # Act
            result_str = await provide_feedback(
                suggestion_id="test-123", feedback_type="helpful"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Invalid feedback" in result["error"]
            assert result["error_type"] == "ValueError"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for Phase 5 execution workflows."""

    async def test_full_refactoring_workflow(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test complete workflow: approve -> apply -> provide feedback."""
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act 1: Approve suggestion
            approve_result = await apply_refactoring(
                action="approve", suggestion_id="test-123"
            )
            approve_data = json.loads(approve_result)

            # Assert 1
            assert approve_data["status"] == "success"

            # Act 2: Apply refactoring
            apply_result = await apply_refactoring(
                action="apply", suggestion_id="test-123"
            )
            apply_data = json.loads(apply_result)

            # Assert 2
            assert apply_data["status"] == "success"

            # Act 3: Provide feedback
            feedback_result = await provide_feedback(
                suggestion_id="test-123", feedback_type="helpful"
            )
            feedback_data = json.loads(feedback_result)

            # Assert 3
            assert feedback_data["status"] == "success"

    async def test_rollback_workflow(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test rollback workflow."""
        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act 1: Apply refactoring
            apply_result = await apply_refactoring(
                action="apply", suggestion_id="test-123"
            )
            apply_data = json.loads(apply_result)

            # Assert 1
            assert apply_data["status"] == "success"
            execution_id = apply_data["execution_id"]

            # Act 2: Rollback
            rollback_result = await apply_refactoring(
                action="rollback", execution_id=execution_id
            )
            rollback_data = json.loads(rollback_result)

            # Assert 2
            assert rollback_data["status"] == "success"
            assert rollback_data["execution_id"] == execution_id


# ============================================================================
# Test Helper Functions - Edge Cases
# ============================================================================


class TestHelperFunctions:
    """Tests for helper functions and edge cases."""

    async def test_apply_invalid_approval_id_type(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test application when approval_id has invalid type."""
        # Arrange - approval has non-string approval_id
        mock_managers["approval_manager"].get_approvals_for_suggestion = AsyncMock(
            return_value=[
                {
                    "approval_id": 12345,  # Invalid type - should be string
                    "status": "approved",
                    "timestamp": "2026-01-04T12:00:00",
                }
            ]
        )

        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="apply", suggestion_id="test-123"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Invalid approval_id type" in result["error"]

    async def test_apply_execution_id_not_string(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test application when execution_id is not a string (edge case)."""
        # Arrange - execution result has non-string execution_id
        mock_managers["refactoring_executor"].execute_refactoring = AsyncMock(
            return_value={
                "status": "success",
                "execution_id": None,  # Not a string - should skip mark_as_applied
                "files_modified": ["file1.py"],
                "changes_applied": 5,
            }
        )

        with (
            patch(
                "cortex.tools.phase5_execution.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase5_execution.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await apply_refactoring(
                action="apply", suggestion_id="test-123"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            # Mark as applied should NOT have been called (execution_id is not string)
            mock_managers["approval_manager"].mark_as_applied.assert_not_called()
