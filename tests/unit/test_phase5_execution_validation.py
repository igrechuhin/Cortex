"""Unit tests for execution_validation module."""

import json

from cortex.refactoring.models import RefactoringAction
from cortex.tools.execution_validation import validate_apply_refactoring_params


class TestValidateApplyRefactoringParams:
    """Tests for validate_apply_refactoring_params."""

    def test_approve_without_suggestion_id_returns_error_json(self) -> None:
        """Approve action requires suggestion_id."""
        result = validate_apply_refactoring_params(
            RefactoringAction.APPROVE, suggestion_id=None, execution_id=None
        )
        assert result is not None
        data = json.loads(result)
        assert data["status"] == "error"
        assert "suggestion_id" in data.get("suggestion", "")

    def test_apply_without_suggestion_id_returns_error_json(self) -> None:
        """Apply action requires suggestion_id."""
        result = validate_apply_refactoring_params(
            RefactoringAction.APPLY, suggestion_id=None, execution_id=None
        )
        assert result is not None
        data = json.loads(result)
        assert data["status"] == "error"
        assert "suggestion_id" in data.get("suggestion", "")

    def test_rollback_without_execution_id_returns_error_json(self) -> None:
        """Rollback action requires execution_id."""
        result = validate_apply_refactoring_params(
            RefactoringAction.ROLLBACK,
            suggestion_id="suggestion-123",
            execution_id=None,
        )
        assert result is not None
        data = json.loads(result)
        assert data["status"] == "error"
        assert "execution_id" in data.get("suggestion", "")

    def test_approve_with_suggestion_id_returns_none(self) -> None:
        """Approve with suggestion_id passes validation."""
        result = validate_apply_refactoring_params(
            RefactoringAction.APPROVE, suggestion_id="suggestion-123", execution_id=None
        )
        assert result is None

    def test_apply_with_suggestion_id_returns_none(self) -> None:
        """Apply with suggestion_id passes validation."""
        result = validate_apply_refactoring_params(
            RefactoringAction.APPLY, suggestion_id="suggestion-123", execution_id=None
        )
        assert result is None

    def test_rollback_with_execution_id_returns_none(self) -> None:
        """Rollback with execution_id passes validation."""
        result = validate_apply_refactoring_params(
            RefactoringAction.ROLLBACK,
            suggestion_id=None,
            execution_id="exec-123",
        )
        assert result is None
