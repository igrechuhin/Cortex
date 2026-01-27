"""
Learning Adjustments Module

Handles confidence adjustments for suggestions based on learned patterns
and preferences.
Split from learning_engine.py in Phase 9.1 for improved modularity.
"""

from typing import cast

from cortex.core.models import JsonValue, ModelDict

from .learning_data_manager import FeedbackRecord, LearningDataManager
from .learning_patterns import PatternManager


class ConfidenceAdjuster:
    """
    Adjust suggestion confidence based on learned patterns and preferences.

    Provides methods to apply pattern-based and preference-based adjustments.
    """

    def __init__(
        self, data_manager: LearningDataManager, pattern_extractor: PatternManager
    ):
        """Initialize confidence adjuster.

        Args:
            data_manager: Data manager for persistence
            pattern_extractor: Pattern manager for extracting pattern keys
        """
        self.data_manager = data_manager
        self.pattern_extractor = pattern_extractor

    def extract_original_confidence(self, suggestion: ModelDict) -> float:
        """Extract original confidence from suggestion."""
        confidence_val = suggestion.get("confidence", 0.5)
        return (
            float(confidence_val) if isinstance(confidence_val, (int, float)) else 0.5
        )

    def extract_suggestion_type(self, suggestion: ModelDict) -> str:
        """Extract suggestion type from suggestion."""
        suggestion_type_val = suggestion.get("type")
        return str(suggestion_type_val) if suggestion_type_val is not None else ""

    def apply_pattern_adjustment(
        self,
        suggestion: ModelDict,
        suggestion_type: str,
        adjustments: list[ModelDict],
    ) -> float:
        """Apply pattern-based confidence adjustment."""
        pattern_key = self._extract_pattern_key(suggestion, suggestion_type)
        if not pattern_key:
            return 0.0

        pattern = self.data_manager.get_pattern(pattern_key)
        if not pattern:
            return 0.0

        adjustment = float(pattern.confidence_adjustment)
        adjustments.append(
            {
                "pattern": pattern_key,
                "adjustment": adjustment,
                "reason": f"Pattern has {pattern.success_rate:.1%} success rate",
            }
        )
        return adjustment

    def _extract_pattern_key(
        self, suggestion: ModelDict, suggestion_type: str
    ) -> str | None:
        """Extract pattern key from suggestion."""
        return self.pattern_extractor.extract_pattern_key(
            FeedbackRecord(
                feedback_id="",
                suggestion_id="",
                suggestion_type=suggestion_type,
                feedback_type="",
                comment=None,
                created_at="",
                suggestion_confidence=0.0,
                was_approved=False,
                was_applied=False,
            ),
            suggestion,
        )

    def apply_preference_adjustment(
        self,
        suggestion_type: str,
        adjustments: list[ModelDict],
    ) -> float:
        """Apply preference-based confidence adjustment."""
        pref = self._get_preference_for_type(suggestion_type)
        if pref is None:
            return 0.0

        pref_score = self._extract_preference_score(pref)
        return self._apply_preference_score_adjustment(pref_score, adjustments)

    def _get_preference_for_type(self, suggestion_type: str) -> ModelDict | None:
        """Get preference dict for suggestion type."""
        pref_key = f"suggestion_type_{suggestion_type}"
        pref_val = self.data_manager.get_preference(pref_key)
        return cast(ModelDict, pref_val) if isinstance(pref_val, dict) else None

    def _extract_preference_score(self, pref: ModelDict) -> float:
        """Extract preference score from preference dict."""
        pref_score_val = pref.get("preference_score", 0.5)
        return (
            float(pref_score_val) if isinstance(pref_score_val, (int, float)) else 0.5
        )

    def _apply_preference_score_adjustment(
        self, pref_score: float, adjustments: list[ModelDict]
    ) -> float:
        """Apply adjustment based on preference score."""
        if pref_score > 0.7:
            adjustments.append(
                {"reason": "User prefers this suggestion type", "adjustment": 0.1}
            )
            return 0.1
        elif pref_score < 0.3:
            adjustments.append(
                {"reason": "User dislikes this suggestion type", "adjustment": -0.1}
            )
            return -0.1
        return 0.0

    def apply_all_adjustments(
        self,
        suggestion: ModelDict,
        suggestion_type: str,
        original_confidence: float,
        adjustments: list[ModelDict],
    ) -> float:
        """Apply all confidence adjustments.

        Args:
            suggestion: The suggestion to adjust
            suggestion_type: Type of suggestion
            original_confidence: Original confidence value
            adjustments: List to collect adjustment details

        Returns:
            Adjusted confidence value (clamped to [0, 1])
        """
        adjusted_confidence = original_confidence

        pattern_adjustment = self.apply_pattern_adjustment(
            suggestion, suggestion_type, adjustments
        )
        adjusted_confidence += pattern_adjustment

        preference_adjustment = self.apply_preference_adjustment(
            suggestion_type, adjustments
        )
        adjusted_confidence += preference_adjustment

        return max(0.0, min(1.0, adjusted_confidence))

    def build_adjustment_result(
        self,
        original_confidence: float,
        adjusted_confidence: float,
        adjustments: list[ModelDict],
    ) -> tuple[float, ModelDict]:
        """Build adjustment result dictionary.

        Args:
            original_confidence: Original confidence value
            adjusted_confidence: Adjusted confidence value
            adjustments: List of adjustment details

        Returns:
            Tuple of (adjusted_confidence, adjustment_details_dict)
        """
        adjustments_json: list[JsonValue] = [
            cast(JsonValue, item) for item in adjustments
        ]
        return adjusted_confidence, {
            "original_confidence": original_confidence,
            "adjusted_confidence": adjusted_confidence,
            "adjustments": adjustments_json,
        }

    async def adjust_suggestion_confidence(
        self,
        suggestion: ModelDict,
    ) -> tuple[float, ModelDict]:
        """
        Adjust suggestion confidence based on learned patterns.

        Args:
            suggestion: The suggestion to adjust

        Returns:
            Tuple of (adjusted_confidence, adjustment_details)
        """
        original_confidence = self.extract_original_confidence(suggestion)
        suggestion_type = self.extract_suggestion_type(suggestion)
        adjustments: list[ModelDict] = []

        adjusted_confidence = self.apply_all_adjustments(
            suggestion, suggestion_type, original_confidence, adjustments
        )

        return self.build_adjustment_result(
            original_confidence, adjusted_confidence, adjustments
        )
