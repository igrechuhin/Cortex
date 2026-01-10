"""
Learning Patterns Module

Handles pattern extraction, creation, and updates based on feedback.
Split from learning_engine.py in Phase 9.1 for improved modularity.
"""

from collections import defaultdict
from datetime import datetime

from .learning_data_manager import FeedbackRecord, LearnedPattern, LearningDataManager


class PatternManager:
    """
    Manage learned patterns from user feedback.

    Extracts patterns from suggestions and tracks their success rates.
    """

    def __init__(self, data_manager: LearningDataManager):
        """Initialize pattern manager.

        Args:
            data_manager: Data manager for persistence
        """
        self.data_manager = data_manager

    def extract_pattern_key(
        self,
        feedback: FeedbackRecord,
        suggestion_details: dict[str, object],
    ) -> str | None:
        """Extract a pattern key from suggestion details."""
        suggestion_type = feedback.suggestion_type

        if suggestion_type == "consolidation":
            # Pattern: consolidation with similarity threshold
            similarity_val = suggestion_details.get("similarity_threshold", 0.8)
            similarity = (
                float(similarity_val)
                if isinstance(similarity_val, (int, float))
                else 0.8
            )
            return f"consolidation-sim-{int(similarity * 10)}"

        elif suggestion_type == "split":
            # Pattern: split based on file size
            file_size_val = suggestion_details.get("file_tokens", 0)
            file_size = (
                int(file_size_val) if isinstance(file_size_val, (int, float)) else 0
            )
            if file_size > 10000:
                return "split-large-file"
            elif file_size > 5000:
                return "split-medium-file"
            else:
                return "split-small-file"

        elif suggestion_type == "reorganization":
            # Pattern: reorganization by goal
            goal_val = suggestion_details.get("optimization_goal", "dependency_depth")
            goal = str(goal_val) if goal_val is not None else "dependency_depth"
            return f"reorganization-{goal}"

        return None

    def extract_conditions(
        self, suggestion_details: dict[str, object]
    ) -> dict[str, object]:
        """Extract conditions from suggestion details."""
        return {
            "min_confidence": suggestion_details.get("confidence", 0.5),
            "thresholds": suggestion_details.get("thresholds", {}),
            "parameters": suggestion_details.get("parameters", {}),
        }

    async def update_patterns(
        self,
        feedback: FeedbackRecord,
        suggestion_details: dict[str, object],
    ) -> None:
        """Update learned patterns based on feedback."""
        pattern_key = self.extract_pattern_key(feedback, suggestion_details)

        if pattern_key:
            pattern = self.data_manager.get_pattern(pattern_key)

            if pattern:
                self._update_existing_pattern(pattern, feedback)
            else:
                pattern = self._create_new_pattern(
                    pattern_key, feedback, suggestion_details
                )

            # Store updated/new pattern
            self.data_manager.add_pattern(pattern)

    def _update_existing_pattern(
        self, pattern: LearnedPattern, feedback: FeedbackRecord
    ) -> None:
        """Update an existing pattern with new feedback."""
        pattern.total_occurrences += 1
        pattern.last_seen = datetime.now().isoformat()

        if feedback.was_approved:
            pattern.approved_count += 1
        else:
            pattern.rejected_count += 1

        # Recalculate success rate
        pattern.success_rate = pattern.approved_count / pattern.total_occurrences

        # Adjust confidence
        if pattern.success_rate > 0.7:
            pattern.confidence_adjustment = 0.1  # Boost confidence
        elif pattern.success_rate < 0.3:
            pattern.confidence_adjustment = -0.2  # Reduce confidence
        else:
            pattern.confidence_adjustment = 0.0  # No adjustment

    def _create_new_pattern(
        self,
        pattern_key: str,
        feedback: FeedbackRecord,
        suggestion_details: dict[str, object],
    ) -> LearnedPattern:
        """Create a new pattern from feedback."""
        return LearnedPattern(
            pattern_id=pattern_key,
            pattern_type=feedback.suggestion_type,
            conditions=self.extract_conditions(suggestion_details),
            success_rate=1.0 if feedback.was_approved else 0.0,
            total_occurrences=1,
            approved_count=1 if feedback.was_approved else 0,
            rejected_count=0 if feedback.was_approved else 1,
            last_seen=datetime.now().isoformat(),
            confidence_adjustment=0.0,
        )

    def calculate_pattern_statistics(self) -> dict[str, dict[str, object]]:
        """Calculate statistics for learned patterns.

        Returns:
            Dictionary mapping pattern types to statistics
        """
        patterns_by_type: defaultdict[str, list[LearnedPattern]] = defaultdict(list)
        for pattern in self.data_manager.get_all_patterns().values():
            patterns_by_type[pattern.pattern_type].append(pattern)

        pattern_stats: dict[str, dict[str, object]] = {}
        for pattern_type, patterns in patterns_by_type.items():
            avg_success_rate = (
                sum(p.success_rate for p in patterns) / len(patterns)
                if patterns
                else 0.0
            )
            best_pattern = (
                max(patterns, key=lambda p: p.success_rate).pattern_id
                if patterns
                else None
            )
            pattern_stats[pattern_type] = {
                "count": len(patterns),
                "avg_success_rate": avg_success_rate,
                "best_pattern": best_pattern,
            }
        return pattern_stats
