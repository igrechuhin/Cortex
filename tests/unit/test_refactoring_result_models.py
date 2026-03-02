"""Unit tests for refactoring result models (default factories and enum coercion)."""

from __future__ import annotations

from cortex.tools.refactoring.result_models import SuggestRefactoringConcisePayload


class TestSuggestRefactoringConcisePayload:
    """Tests for SuggestRefactoringConcisePayload default and validation."""

    def test_default_suggestions_is_empty_list(self) -> None:
        """SuggestRefactoringConcisePayload uses default_factory for suggestions."""
        payload = SuggestRefactoringConcisePayload(type=None)
        assert payload.suggestions == []
        assert payload.status == "success"
        assert payload.type is None

    def test_validate_with_string_type_coerces_to_enum(self) -> None:
        """model_validate with string type coerces to SuggestRefactoringType."""
        data: dict[str, object] = {
            "status": "success",
            "type": "consolidation",
            "suggestions": [],
        }
        payload = SuggestRefactoringConcisePayload.model_validate(data)
        assert payload.type is not None
        assert str(payload.type) == "consolidation"
