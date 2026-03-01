"""Unit tests for execution_planning module."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.refactoring.models import RefactoringAction
from cortex.tools.execution_planning import (
    execute_validated_refactoring,
    execute_with_error_handling,
    get_suggestion_for_feedback,
    provide_feedback_impl,
)


class TestExecuteValidatedRefactoring:
    """Tests for execute_validated_refactoring."""

    @pytest.mark.asyncio
    async def test_returns_validation_error_when_approve_missing_suggestion_id(
        self,
    ) -> None:
        """Returns error JSON when approve action has no suggestion_id."""
        result = await execute_validated_refactoring(
            action=RefactoringAction.APPROVE,
            project_root="/tmp",
            suggestion_id=None,
            approval_id=None,
            execution_id=None,
            user_comment=None,
            auto_apply=False,
            dry_run=False,
            validate_first=True,
            restore_snapshot=True,
            preserve_manual_changes=True,
        )
        data = json.loads(result)
        assert data["status"] == "error"
        assert "suggestion_id" in data.get("suggestion", "")

    @pytest.mark.asyncio
    async def test_returns_validation_error_when_rollback_missing_execution_id(
        self,
    ) -> None:
        """Returns error JSON when rollback action has no execution_id."""
        result = await execute_validated_refactoring(
            action=RefactoringAction.ROLLBACK,
            project_root="/tmp",
            suggestion_id=None,
            approval_id=None,
            execution_id=None,
            user_comment=None,
            auto_apply=False,
            dry_run=False,
            validate_first=True,
            restore_snapshot=True,
            preserve_manual_changes=True,
        )
        data = json.loads(result)
        assert data["status"] == "error"
        assert "execution_id" in data.get("suggestion", "")


class TestExecuteWithErrorHandling:
    """Tests for execute_with_error_handling."""

    @pytest.mark.asyncio
    async def test_returns_error_response_when_inner_raises(self) -> None:
        """Returns error JSON when execute_validated_refactoring raises."""
        with patch(
            "cortex.tools.execution_planning.execute_validated_refactoring",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Simulated failure"),
        ):
            result = await execute_with_error_handling(
                action=RefactoringAction.APPROVE,
                project_root="/tmp",
                suggestion_id="suggestion-123",
                approval_id=None,
                execution_id=None,
                user_comment=None,
                auto_apply=False,
                dry_run=False,
                validate_first=True,
                restore_snapshot=True,
                preserve_manual_changes=True,
                ctx=None,
            )
        data = json.loads(result)
        assert data["status"] == "error"
        assert "Simulated failure" in data["error"]


class TestGetSuggestionForFeedback:
    """Tests for get_suggestion_for_feedback."""

    @pytest.mark.asyncio
    async def test_returns_error_json_when_suggestion_not_found(self) -> None:
        """Returns error JSON string when suggestion not found."""
        engine = MagicMock()
        engine.get_suggestion = AsyncMock(return_value=None)
        result = await get_suggestion_for_feedback(engine, "nonexistent")
        assert isinstance(result, str)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "not found" in data["error"]

    @pytest.mark.asyncio
    async def test_returns_suggestion_when_found(self) -> None:
        """Returns suggestion model when found."""
        from cortex.refactoring.models import (
            RefactoringImpactMetrics,
            RefactoringPriority,
            RefactoringSuggestionModel,
            RefactoringType,
        )

        suggestion = RefactoringSuggestionModel(
            suggestion_id="test-123",
            refactoring_type=RefactoringType.CONSOLIDATION,
            priority=RefactoringPriority.HIGH,
            title="Test",
            description="Test",
            reasoning="Test",
            affected_files=[],
            actions=[],
            estimated_impact=RefactoringImpactMetrics(
                token_savings=0, files_affected=0
            ),
            confidence_score=0.9,
        )
        engine = MagicMock()
        engine.get_suggestion = AsyncMock(return_value=suggestion)
        result = await get_suggestion_for_feedback(engine, "test-123")
        assert result == suggestion


class TestProvideFeedbackImpl:
    """Tests for provide_feedback_impl."""

    @pytest.mark.asyncio
    async def test_returns_error_json_when_suggestion_not_found(self) -> None:
        """Returns error JSON when get_suggestion returns None."""
        mgrs = MagicMock()
        refactoring_engine = MagicMock()
        refactoring_engine.get_suggestion = AsyncMock(return_value=None)
        learning_engine = MagicMock()
        approval_manager = MagicMock()
        approval_manager.get_approvals_for_suggestion = AsyncMock(return_value=[])

        with (
            patch(
                "cortex.tools.execution_planning.get_project_root",
                return_value="/tmp",
            ),
            patch(
                "cortex.tools.execution_planning.get_managers",
                new_callable=AsyncMock,
                return_value=mgrs,
            ),
            patch(
                "cortex.tools.execution_planning.extract_feedback_managers",
                new_callable=AsyncMock,
                return_value=(learning_engine, refactoring_engine, approval_manager),
            ),
        ):
            result = await provide_feedback_impl(
                suggestion_id="nonexistent",
                feedback_type="helpful",
                comment=None,
                adjust_preferences=True,
                project_root="/tmp",
                ctx=None,
            )
        data = json.loads(result)
        assert data["status"] == "error"
        assert "not found" in data["error"]
