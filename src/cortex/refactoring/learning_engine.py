"""
Learning Engine - Phase 5.4

Learn from user feedback and adapt suggestions over time.

Refactored in Phase 7.1.2 to use LearningDataManager for improved modularity.
Refactored in Phase 9.1 to split into focused modules (preferences, patterns, adjustments).
"""

from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import ModelDict
from cortex.refactoring.models import (
    FeedbackRecordResult,
    LearningInsights,
    ResetLearningResult,
)

from .learning_adjustments import ConfidenceAdjuster
from .learning_data_manager import FeedbackRecord, LearningDataManager
from .learning_exporter import export_learned_patterns
from .learning_patterns import PatternManager
from .learning_preferences import PreferenceManager


def _check_confidence_threshold(
    adjusted_confidence: float, data_manager: LearningDataManager
) -> tuple[bool, str]:
    """Check if confidence meets minimum threshold."""
    min_threshold_val = data_manager.get_preference("min_confidence_threshold", 0.5)
    min_threshold = (
        float(min_threshold_val) if isinstance(min_threshold_val, (int, float)) else 0.5
    )

    if adjusted_confidence < min_threshold:
        return (
            False,
            f"Confidence {adjusted_confidence:.2f} below threshold {min_threshold:.2f}",
        )
    return True, ""


def _check_suggestion_type_preference(
    suggestion: ModelDict, data_manager: LearningDataManager
) -> tuple[bool, str]:
    """Check if suggestion type preference allows showing."""
    suggestion_type_val = suggestion.get("type")
    suggestion_type = (
        str(suggestion_type_val) if suggestion_type_val is not None else ""
    )
    pref_key = f"suggestion_type_{suggestion_type}"

    pref_val = data_manager.get_preference(pref_key)
    pref: ModelDict | None = (
        cast(ModelDict, pref_val) if isinstance(pref_val, dict) else None
    )
    if pref is not None:
        pref_score_val = pref.get("preference_score", 0.5)
        pref_score = (
            float(pref_score_val) if isinstance(pref_score_val, (int, float)) else 0.5
        )
        total_val = pref.get("total", 0)
        total = int(total_val) if isinstance(total_val, (int, float)) else 0
        if pref_score < 0.2 and total >= 5:
            return False, f"User consistently rejects {suggestion_type} suggestions"

    return True, ""


class LearningEngine:
    """
    Learn from user feedback and improve suggestions.

    Features:
    - Track suggestion outcomes (approved/rejected)
    - Identify successful pattern types
    - Learn user preferences
    - Adjust suggestion thresholds
    - Build pattern library
    - Provide learning insights

    Delegates to specialized managers for preferences, patterns, and adjustments.
    """

    def __init__(
        self,
        memory_bank_dir: Path,
        config: ModelDict | None = None,
    ):
        self.memory_bank_dir: Path = Path(memory_bank_dir)
        self.config: ModelDict = config or {}

        # Learning data file
        learning_file = self.memory_bank_dir.parent / "learning.json"

        # Initialize data manager for persistence
        self.data_manager = LearningDataManager(learning_file)

        # Initialize specialized managers
        self.preference_manager = PreferenceManager(self.data_manager)
        self.pattern_manager = PatternManager(self.data_manager)
        self.confidence_adjuster = ConfidenceAdjuster(
            self.data_manager, self.pattern_manager
        )

    async def record_feedback(
        self,
        suggestion_id: str,
        suggestion_type: str,
        feedback_type: str,
        comment: str | None = None,
        suggestion_confidence: float = 0.5,
        was_approved: bool = False,
        was_applied: bool = False,
        suggestion_details: ModelDict | None = None,
    ) -> FeedbackRecordResult:
        """
        Record user feedback on a suggestion.

        Args:
            suggestion_id: ID of the suggestion
            suggestion_type: Type of suggestion
            feedback_type: Type of feedback ("helpful", "not_helpful", "incorrect")
            comment: Optional user comment
            suggestion_confidence: Original confidence score
            was_approved: Whether suggestion was approved
            was_applied: Whether suggestion was applied
            suggestion_details: Additional details about the suggestion

        Returns:
            Recorded feedback
        """
        feedback_id = self._generate_feedback_id(suggestion_id)
        feedback = self._create_feedback_record(
            feedback_id,
            suggestion_id,
            suggestion_type,
            feedback_type,
            comment,
            suggestion_confidence,
            was_approved,
            was_applied,
        )

        self.data_manager.add_feedback(feedback)

        if suggestion_details:
            await self.pattern_manager.update_patterns(feedback, suggestion_details)

        await self._update_preferences(feedback)
        await self.data_manager.save_learning_data()

        return self._build_feedback_response(feedback_id)

    def _generate_feedback_id(self, suggestion_id: str) -> str:
        """Generate unique feedback ID with timestamp."""
        return f"feedback-{suggestion_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _create_feedback_record(
        self,
        feedback_id: str,
        suggestion_id: str,
        suggestion_type: str,
        feedback_type: str,
        comment: str | None,
        suggestion_confidence: float,
        was_approved: bool,
        was_applied: bool,
    ) -> FeedbackRecord:
        """Create feedback record object."""
        return FeedbackRecord(
            feedback_id=feedback_id,
            suggestion_id=suggestion_id,
            suggestion_type=suggestion_type,
            feedback_type=feedback_type,
            comment=comment,
            created_at=datetime.now().isoformat(),
            suggestion_confidence=suggestion_confidence,
            was_approved=was_approved,
            was_applied=was_applied,
        )

    def _build_feedback_response(self, feedback_id: str) -> FeedbackRecordResult:
        """Build feedback response dictionary."""
        from cortex.refactoring.models import FeedbackRecordResult

        return FeedbackRecordResult(
            status="recorded",
            feedback_id=feedback_id,
            learning_enabled=bool(self.config.get("enabled", True)),
            message="Feedback recorded and learning updated",
        )

    async def _update_preferences(self, feedback: FeedbackRecord) -> None:
        """Update user preferences based on feedback."""
        pref_key = f"suggestion_type_{feedback.suggestion_type}"
        pref = self.preference_manager.get_or_create_preference(pref_key)

        self.preference_manager.update_preference_counts(pref, feedback)
        pref["preference_score"] = self.preference_manager.calculate_preference_score(
            pref
        )

        self.data_manager.update_preference(pref_key, pref)
        self.preference_manager.update_confidence_threshold(feedback)

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
        return await self.confidence_adjuster.adjust_suggestion_confidence(suggestion)

    async def should_show_suggestion(
        self,
        suggestion: ModelDict,
    ) -> tuple[bool, str]:
        """
        Determine if a suggestion should be shown to the user.

        Args:
            suggestion: The suggestion to evaluate

        Returns:
            Tuple of (should_show, reason)
        """
        if not bool(self.config.get("enabled", True)):
            return True, "Learning disabled"

        adjusted_confidence, _ = await self.adjust_suggestion_confidence(suggestion)

        threshold_check = _check_confidence_threshold(
            adjusted_confidence, self.data_manager
        )
        if not threshold_check[0]:
            return threshold_check

        type_check = _check_suggestion_type_preference(suggestion, self.data_manager)
        if not type_check[0]:
            return type_check

        return True, "Suggestion meets confidence and preference criteria"

    async def get_learning_insights(self) -> LearningInsights:
        """
        Get insights about learning and adaptation.

        Returns:
            Learning insights with statistics
        """
        feedback_stats = self.data_manager.get_feedback_stats()
        pattern_stats = self.pattern_manager.calculate_pattern_statistics()
        preference_summary = self.preference_manager.calculate_preference_summary()
        min_threshold_val = self.data_manager.get_preference(
            "min_confidence_threshold", 0.5
        )
        min_threshold = (
            float(min_threshold_val)
            if isinstance(min_threshold_val, (int, float))
            else 0.5
        )

        total_feedback = feedback_stats["total"]
        approved = feedback_stats["approved"]
        rejected = feedback_stats["rejected"]

        return LearningInsights(
            learning_enabled=bool(self.config.get("enabled", True)),
            total_feedback=total_feedback,
            approved=approved,
            rejected=rejected,
            approval_rate=(
                float(approved) / float(total_feedback) if total_feedback > 0 else 0.0
            ),
            learned_patterns=len(self.data_manager.get_all_patterns()),
            pattern_statistics=pattern_stats,
            user_preferences=preference_summary,
            min_confidence_threshold=min_threshold,
            recommendations=self.preference_manager.get_learning_recommendations(),
        )

    async def reset_learning_data(
        self,
        reset_feedback: bool = True,
        reset_patterns: bool = True,
        reset_preferences: bool = True,
    ) -> ResetLearningResult:
        """
        Reset learning data.

        Args:
            reset_feedback: Reset feedback records
            reset_patterns: Reset learned patterns
            reset_preferences: Reset user preferences

        Returns:
            Reset results
        """
        counts = await self.data_manager.reset_data(
            reset_feedback=reset_feedback,
            reset_patterns=reset_patterns,
            reset_preferences=reset_preferences,
        )

        return ResetLearningResult(
            status="success",
            message="Learning data reset",
            feedback_reset=counts.get("feedback_reset", 0),
            patterns_reset=counts.get("patterns_reset", 0),
            preferences_reset=counts.get("preferences_reset", 0),
        )

    async def export_learned_patterns(self, format: str = "json") -> ModelDict:
        """
        Export learned patterns.

        Args:
            format: Export format ("json", "text")

        Returns:
            Exported patterns
        """
        patterns = self.data_manager.get_all_patterns()
        return export_learned_patterns(patterns, format)

    # Backward compatibility methods for tests
    def extract_pattern_key(
        self, feedback: FeedbackRecord, suggestion_details: ModelDict
    ) -> str | None:
        """Extract pattern key (delegates to pattern manager)."""
        return self.pattern_manager.extract_pattern_key(feedback, suggestion_details)

    def extract_conditions(self, suggestion_details: ModelDict) -> ModelDict:
        """Extract conditions (delegates to pattern manager)."""
        return self.pattern_manager.extract_conditions(suggestion_details)

    async def update_patterns(
        self, feedback: FeedbackRecord, suggestion_details: ModelDict
    ) -> None:
        """Update patterns (delegates to pattern manager)."""
        await self.pattern_manager.update_patterns(feedback, suggestion_details)

    def get_preference_recommendation(self, pref: ModelDict) -> str:
        """Get preference recommendation (delegates to preference manager)."""
        return self.preference_manager.get_preference_recommendation(pref)

    def get_learning_recommendations(self) -> list[str]:
        """Get learning recommendations (delegates to preference manager)."""
        return self.preference_manager.get_learning_recommendations()
