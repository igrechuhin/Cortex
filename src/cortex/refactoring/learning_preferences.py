"""
Learning Preferences Module

Handles user preference tracking, scoring, and recommendations.
Split from learning_engine.py in Phase 9.1 for improved modularity.
"""

from typing import cast

from cortex.core.models import ModelDict

from .learning_data_manager import FeedbackRecord, LearningDataManager


class PreferenceManager:
    """
    Manage user preferences for suggestion types.

    Tracks approval/rejection patterns and calculates preference scores.
    """

    def __init__(self, data_manager: LearningDataManager):
        """Initialize preference manager.

        Args:
            data_manager: Data manager for persistence
        """
        self.data_manager = data_manager

    def get_or_create_preference(self, pref_key: str) -> ModelDict:
        """Get existing preference or create default.

        Args:
            pref_key: Preference key

        Returns:
            Preference dictionary
        """
        default_pref: ModelDict = {
            "total": 0,
            "approved": 0,
            "rejected": 0,
            "preference_score": 0.5,
        }
        pref_val = self.data_manager.get_preference(pref_key, default_pref)
        if isinstance(pref_val, dict):
            return cast(ModelDict, pref_val)
        return default_pref.copy()

    def update_preference_counts(
        self, pref: ModelDict, feedback: FeedbackRecord
    ) -> None:
        """Update preference counts based on feedback.

        Args:
            pref: Preference dictionary to update
            feedback: Feedback record
        """
        total_val = pref.get("total", 0)
        total = int(total_val) if isinstance(total_val, (int, float)) else 0
        pref["total"] = total + 1

        if feedback.was_approved:
            approved_val = pref.get("approved", 0)
            approved = (
                int(approved_val) if isinstance(approved_val, (int, float)) else 0
            )
            pref["approved"] = approved + 1
        else:
            rejected_val = pref.get("rejected", 0)
            rejected = (
                int(rejected_val) if isinstance(rejected_val, (int, float)) else 0
            )
            pref["rejected"] = rejected + 1

    def calculate_preference_score(self, pref: ModelDict) -> float:
        """Calculate preference score from preference dictionary.

        Args:
            pref: Preference dictionary with approved/total counts

        Returns:
            Preference score (0-1)
        """
        approved_val = pref.get("approved", 0)
        approved_count = (
            int(approved_val) if isinstance(approved_val, (int, float)) else 0
        )
        total_val = pref.get("total", 1)
        total_count = int(total_val) if isinstance(total_val, (int, float)) else 1
        return float(approved_count) / float(total_count) if total_count > 0 else 0.5

    def update_confidence_threshold(self, feedback: FeedbackRecord) -> None:
        """Update global minimum confidence threshold based on feedback.

        Args:
            feedback: Feedback record to process
        """
        if feedback.feedback_type == "not_helpful":
            # User found suggestion not helpful - increase threshold
            current_min_val = self.data_manager.get_preference(
                "min_confidence_threshold", 0.5
            )
            current_min = (
                float(current_min_val)
                if isinstance(current_min_val, (int, float))
                else 0.5
            )
            self.data_manager.update_preference(
                "min_confidence_threshold", min(0.9, current_min + 0.05)
            )

        elif (
            feedback.feedback_type == "helpful" and feedback.suggestion_confidence < 0.6
        ):
            # User found low-confidence suggestion helpful - decrease threshold
            current_min_val = self.data_manager.get_preference(
                "min_confidence_threshold", 0.5
            )
            current_min = (
                float(current_min_val)
                if isinstance(current_min_val, (int, float))
                else 0.5
            )
            self.data_manager.update_preference(
                "min_confidence_threshold", max(0.3, current_min - 0.05)
            )

    def calculate_preference_summary(self) -> ModelDict:
        """Calculate summary of user preferences.

        Returns:
            Dictionary mapping suggestion types to preference summaries
        """
        preference_summary: ModelDict = {}
        for key, pref_val in self.data_manager.get_all_preferences().items():
            if key.startswith("suggestion_type_"):
                pref: ModelDict = (
                    cast(ModelDict, pref_val) if isinstance(pref_val, dict) else {}
                )
                suggestion_type = key.replace("suggestion_type_", "")
                preference_summary[suggestion_type] = {
                    "preference_score": pref.get("preference_score", 0.5),
                    "total_feedback": pref.get("total", 0),
                    "recommendation": self.get_preference_recommendation(pref),
                }
        return preference_summary

    def get_preference_recommendation(self, pref: ModelDict) -> str:
        """Get recommendation based on preference score."""
        score_val = pref.get("preference_score", 0.5)
        score = float(score_val) if isinstance(score_val, (int, float)) else 0.5
        total_val = pref.get("total", 0)
        total = int(total_val) if isinstance(total_val, (int, float)) else 0

        # Early return for insufficient data
        if total < 3:
            return "Not enough data yet"

        # Use early returns to reduce nesting
        if score > 0.7:
            return "Strongly preferred - show more"
        if score > 0.5:
            return "Somewhat preferred"
        if score > 0.3:
            return "Neutral - user is selective"
        return "Not preferred - reduce frequency"

    def get_learning_recommendations(self) -> list[str]:
        """Get recommendations for improving the system."""
        recommendations: list[str] = []

        self._check_feedback_volume(recommendations)
        self._check_confidence_threshold(recommendations)
        self._check_low_success_patterns(recommendations)
        self._check_underutilized_suggestion_types(recommendations)
        self._add_default_recommendation_if_empty(recommendations)

        return recommendations

    def _check_feedback_volume(self, recommendations: list[str]) -> None:
        """Check if enough feedback has been collected."""
        feedback_stats = self.data_manager.get_feedback_stats()
        total_feedback = feedback_stats["total"]

        if total_feedback < 10:
            recommendations.append(
                "Collect more feedback to improve learning (minimum 10 suggestions needed)"
            )

    def _check_confidence_threshold(self, recommendations: list[str]) -> None:
        """Check if confidence threshold is too high."""
        min_threshold_val = self.data_manager.get_preference(
            "min_confidence_threshold", 0.5
        )
        min_threshold = (
            float(min_threshold_val)
            if isinstance(min_threshold_val, (int, float))
            else 0.5
        )
        if min_threshold > 0.8:
            recommendations.append(
                f"Confidence threshold is high ({min_threshold:.2f}). "
                + "Few suggestions will be shown. Consider providing feedback on helpful low-confidence suggestions."
            )

    def _check_low_success_patterns(self, recommendations: list[str]) -> None:
        """Check for patterns with low success rate."""
        low_success_patterns = [
            p
            for p in self.data_manager.get_all_patterns().values()
            if p.success_rate < 0.3 and p.total_occurrences >= 3
        ]

        if low_success_patterns:
            recommendations.append(
                f"Found {len(low_success_patterns)} pattern(s) with low success rate. "
                + "These will be shown less frequently."
            )

    def _check_underutilized_suggestion_types(self, recommendations: list[str]) -> None:
        """Check for underutilized suggestion types."""
        for key, pref_val in self.data_manager.get_all_preferences().items():
            if key.startswith("suggestion_type_"):
                pref: ModelDict = (
                    cast(ModelDict, pref_val) if isinstance(pref_val, dict) else {}
                )
                total_val = pref.get("total", 0)
                total = int(total_val) if isinstance(total_val, (int, float)) else 0
                if total == 0:
                    suggestion_type = key.replace("suggestion_type_", "")
                    recommendations.append(
                        f"No feedback yet for {suggestion_type} suggestions. "
                        + "Try reviewing these when they appear."
                    )

    def _add_default_recommendation_if_empty(self, recommendations: list[str]) -> None:
        """Add default recommendation if no recommendations found."""
        if not recommendations:
            recommendations.append(
                "Learning system is functioning well. Keep providing feedback!"
            )
