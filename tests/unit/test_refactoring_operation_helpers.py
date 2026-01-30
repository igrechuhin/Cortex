"""Unit tests for refactoring_operation_helpers."""

import json
from types import SimpleNamespace
from typing import cast

from cortex.refactoring.consolidation_detector import ConsolidationOpportunity
from cortex.refactoring.split_recommender import SplitRecommendation
from cortex.tools.refactoring_operation_helpers import (
    convert_opportunities_to_dict,
    convert_recommendations_to_dict,
    handle_preview_mode,
    parse_refactoring_suggestion_type,
    validate_refactoring_type,
    validate_suggest_refactoring_type,
)


class TestParseRefactoringSuggestionType:
    """Tests for parse_refactoring_suggestion_type."""

    def test_returns_none_for_none(self) -> None:
        """Returns None when value is None."""
        assert parse_refactoring_suggestion_type(None) is None

    def test_returns_enum_for_valid_consolidation(self) -> None:
        """Returns CONSOLIDATION for 'consolidation'."""
        from cortex.refactoring.models import RefactoringSuggestionType

        assert (
            parse_refactoring_suggestion_type("consolidation")
            == RefactoringSuggestionType.CONSOLIDATION
        )

    def test_returns_enum_for_valid_splits(self) -> None:
        """Returns SPLITS for 'splits'."""
        from cortex.refactoring.models import RefactoringSuggestionType

        assert (
            parse_refactoring_suggestion_type("splits")
            == RefactoringSuggestionType.SPLITS
        )

    def test_returns_none_for_invalid_string(self) -> None:
        """Returns None for invalid string."""
        assert parse_refactoring_suggestion_type("invalid") is None


class TestValidateRefactoringType:
    """Tests for validate_refactoring_type."""

    def test_returns_none_for_valid_type(self) -> None:
        """Returns None when type is valid."""
        assert validate_refactoring_type("consolidation") is None
        assert validate_refactoring_type("splits") is None
        assert validate_refactoring_type("reorganization") is None

    def test_returns_error_json_for_invalid_type(self) -> None:
        """Returns JSON error string for invalid type."""
        result = validate_refactoring_type("bad")
        assert result is not None
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "valid_types" in parsed


class TestValidateSuggestRefactoringType:
    """Tests for validate_suggest_refactoring_type."""

    def test_returns_none_for_valid_type(self) -> None:
        """Returns None when type is valid."""
        assert validate_suggest_refactoring_type("reorganization") is None

    def test_returns_error_json_for_invalid_type(self) -> None:
        """Returns JSON error string for invalid type."""
        result = validate_suggest_refactoring_type("unknown")
        assert result is not None
        parsed = json.loads(result)
        assert parsed["status"] == "error"


class TestHandlePreviewMode:
    """Tests for handle_preview_mode."""

    def test_returns_success_json_with_suggestion_id(self) -> None:
        """Returns JSON with preview_mode and suggestion_id."""
        result = handle_preview_mode("suggestion-123")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["preview_mode"] is True
        assert parsed["suggestion_id"] == "suggestion-123"


class TestConvertOpportunitiesToDict:
    """Tests for convert_opportunities_to_dict."""

    def test_uses_to_dict_when_present(self) -> None:
        """Uses to_dict() when opportunity has it."""
        opp = SimpleNamespace()
        opp.to_dict = lambda: {"key": "value"}
        seq = cast(list[ConsolidationOpportunity], [opp])
        assert convert_opportunities_to_dict(seq) == [{"key": "value"}]

    def test_uses_dict_fallback_when_no_to_dict(self) -> None:
        """Uses __dict__ when opportunity has no to_dict."""
        opp = SimpleNamespace(a=1, b=2)
        seq = cast(list[ConsolidationOpportunity], [opp])
        result = convert_opportunities_to_dict(seq)
        assert result == [{"a": 1, "b": 2}]


class TestConvertRecommendationsToDict:
    """Tests for convert_recommendations_to_dict."""

    def test_uses_to_dict_when_present(self) -> None:
        """Uses to_dict() when recommendation has it."""
        rec = SimpleNamespace()
        rec.to_dict = lambda: {"x": 1}
        seq = cast(list[SplitRecommendation], [rec])
        assert convert_recommendations_to_dict(seq) == [{"x": 1}]

    def test_uses_dict_fallback_when_no_to_dict(self) -> None:
        """Uses __dict__ when recommendation has no to_dict."""
        rec = SimpleNamespace(c=3, d=4)
        seq = cast(list[SplitRecommendation], [rec])
        result = convert_recommendations_to_dict(seq)
        assert result == [{"c": 3, "d": 4}]
