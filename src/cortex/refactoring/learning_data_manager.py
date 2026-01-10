"""
Learning Data Manager - Phase 7.1.2

Manages persistence and storage of learning data including feedback records,
learned patterns, and user preferences.

Extracted from learning_engine.py to improve modularity and maintainability.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file


@dataclass
class FeedbackRecord:
    """Record of user feedback on a suggestion."""

    feedback_id: str
    suggestion_id: str
    suggestion_type: str
    feedback_type: str  # "helpful", "not_helpful", "incorrect"
    comment: str | None
    created_at: str
    suggestion_confidence: float
    was_approved: bool
    was_applied: bool

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
        return cast(dict[str, object], asdict(self))


@dataclass
class LearnedPattern:
    """Pattern learned from user feedback."""

    pattern_id: str
    pattern_type: str  # "consolidation", "split", "reorganization"
    conditions: dict[str, object]
    success_rate: float
    total_occurrences: int
    approved_count: int
    rejected_count: int
    last_seen: str
    confidence_adjustment: float  # How much to adjust confidence for this pattern

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
        return cast(dict[str, object], asdict(self))


class LearningDataManager:
    """
    Manages persistence and storage of learning data.

    Responsibilities:
    - Load/save learning data to disk
    - Manage feedback records storage
    - Manage learned patterns storage
    - Manage user preferences storage
    - Handle data corruption and recovery
    """

    learning_file: Path

    def __init__(self, learning_file: Path):
        """
        Initialize learning data manager.

        Args:
            learning_file: Path to the learning data JSON file
        """
        self.learning_file = Path(learning_file)

        # In-memory storage
        self.feedback_records: dict[str, FeedbackRecord] = {}
        self.learned_patterns: dict[str, LearnedPattern] = {}
        self.user_preferences: dict[str, object] = {}

        # Load existing data
        self._load_learning_data()

    def _load_learning_data(self) -> None:
        """
        Load learning data from disk.

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        if not self.learning_file.exists():
            return

        try:
            data = self._read_learning_file()
            if data is None:
                return

            self._load_feedback_records(data)
            self._load_learned_patterns(data)
            self._load_user_preferences(data)

        except Exception as e:
            self._handle_load_error(e)

    def _read_learning_file(self) -> dict[str, object] | None:
        """Read and parse learning data file."""
        with open(self.learning_file) as f:
            data_raw = cast(object, json.load(f))
            if not isinstance(data_raw, dict):
                return None
            return cast(dict[str, object], data_raw)

    def _load_feedback_records(self, data: dict[str, object]) -> None:
        """Load feedback records from data dictionary."""
        feedback_dict: object = data.get("feedback", {})
        if not isinstance(feedback_dict, dict):
            return

        typed_feedback_dict: dict[str, object] = cast(dict[str, object], feedback_dict)
        for key_obj, value_obj in typed_feedback_dict.items():
            feedback_id: str = str(key_obj)
            if isinstance(value_obj, dict):
                feedback = self._deserialize_feedback_record(
                    feedback_id, cast(dict[str, object], value_obj)
                )
                self.feedback_records[feedback_id] = feedback

    def _deserialize_feedback_record(
        self, feedback_id: str, data: dict[str, object]
    ) -> FeedbackRecord:
        """Deserialize a feedback record from dictionary."""
        return FeedbackRecord(
            feedback_id=cast(str, data.get("feedback_id", feedback_id)),
            suggestion_id=cast(str, data.get("suggestion_id", "")),
            suggestion_type=cast(str, data.get("suggestion_type", "")),
            feedback_type=cast(str, data.get("feedback_type", "")),
            comment=cast(str | None, data.get("comment")),
            created_at=cast(str, data.get("created_at", "")),
            suggestion_confidence=cast(float, data.get("suggestion_confidence", 0.0)),
            was_approved=cast(bool, data.get("was_approved", False)),
            was_applied=cast(bool, data.get("was_applied", False)),
        )

    def _load_learned_patterns(self, data: dict[str, object]) -> None:
        """Load learned patterns from data dictionary."""
        patterns_dict: object = data.get("patterns", {})
        if not isinstance(patterns_dict, dict):
            return

        typed_patterns_dict: dict[str, object] = cast(dict[str, object], patterns_dict)
        for pattern_id, pattern_data in typed_patterns_dict.items():
            pattern_id_str: str = str(pattern_id)
            if isinstance(pattern_data, dict):
                pattern = self._deserialize_learned_pattern(
                    pattern_id_str, cast(dict[str, object], pattern_data)
                )
                self.learned_patterns[pattern_id_str] = pattern

    def _deserialize_learned_pattern(
        self, pattern_id: str, data: dict[str, object]
    ) -> LearnedPattern:
        """Deserialize a learned pattern from dictionary."""
        return LearnedPattern(
            pattern_id=cast(str, data.get("pattern_id", pattern_id)),
            pattern_type=cast(str, data.get("pattern_type", "")),
            conditions=cast(dict[str, object], data.get("conditions", {})),
            success_rate=cast(float, data.get("success_rate", 0.0)),
            total_occurrences=cast(int, data.get("total_occurrences", 0)),
            approved_count=cast(int, data.get("approved_count", 0)),
            rejected_count=cast(int, data.get("rejected_count", 0)),
            last_seen=cast(str, data.get("last_seen", "")),
            confidence_adjustment=cast(float, data.get("confidence_adjustment", 0.0)),
        )

    def _load_user_preferences(self, data: dict[str, object]) -> None:
        """Load user preferences from data dictionary."""
        preferences: object = data.get("preferences", {})
        if isinstance(preferences, dict):
            typed_preferences: dict[str, object] = cast(dict[str, object], preferences)
            self.user_preferences = {str(k): v for k, v in typed_preferences.items()}

    def _handle_load_error(self, error: Exception) -> None:
        """Handle error during data loading by resetting to fresh state."""
        print(f"Warning: Failed to load learning data: {error}. Starting fresh.")
        self.feedback_records = {}
        self.learned_patterns = {}
        self.user_preferences = {}

    async def save_learning_data(self) -> None:
        """Save learning data to disk."""
        try:
            data: dict[str, object] = {
                "last_updated": datetime.now().isoformat(),
                "feedback": {
                    feedback_id: feedback.to_dict()
                    for feedback_id, feedback in self.feedback_records.items()
                },
                "patterns": {
                    pattern_id: pattern.to_dict()
                    for pattern_id, pattern in self.learned_patterns.items()
                },
                "preferences": self.user_preferences,
            }

            # Ensure directory exists
            self.learning_file.parent.mkdir(parents=True, exist_ok=True)

            async with open_async_text_file(self.learning_file, "w", "utf-8") as f:
                _ = await f.write(json.dumps(data, indent=2))

        except Exception as e:
            raise Exception(f"Failed to save learning data: {e}") from e

    def add_feedback(self, feedback: FeedbackRecord) -> None:
        """Add a feedback record to storage."""
        self.feedback_records[feedback.feedback_id] = feedback

    def add_pattern(self, pattern: LearnedPattern) -> None:
        """Add or update a learned pattern."""
        self.learned_patterns[pattern.pattern_id] = pattern

    def get_pattern(self, pattern_id: str) -> LearnedPattern | None:
        """Get a learned pattern by ID."""
        return self.learned_patterns.get(pattern_id)

    def update_preference(self, key: str, value: object) -> None:
        """Update a user preference."""
        self.user_preferences[key] = value

    def get_preference(self, key: str, default: object | None = None) -> object | None:
        """Get a user preference value."""
        return self.user_preferences.get(key, default)

    async def reset_data(
        self,
        reset_feedback: bool = True,
        reset_patterns: bool = True,
        reset_preferences: bool = True,
    ) -> dict[str, int]:
        """
        Reset learning data.

        Args:
            reset_feedback: Reset feedback records
            reset_patterns: Reset learned patterns
            reset_preferences: Reset user preferences

        Returns:
            Dictionary with counts of reset items
        """
        counts = {
            "feedback_reset": 0,
            "patterns_reset": 0,
            "preferences_reset": 0,
        }

        if reset_feedback:
            counts["feedback_reset"] = len(self.feedback_records)
            self.feedback_records = {}

        if reset_patterns:
            counts["patterns_reset"] = len(self.learned_patterns)
            self.learned_patterns = {}

        if reset_preferences:
            counts["preferences_reset"] = len(self.user_preferences)
            self.user_preferences = {}

        await self.save_learning_data()

        return counts

    def get_feedback_stats(self) -> dict[str, int]:
        """Get statistics about feedback records."""
        total = len(self.feedback_records)
        approved = len([f for f in self.feedback_records.values() if f.was_approved])
        rejected = len(
            [f for f in self.feedback_records.values() if not f.was_approved]
        )

        return {
            "total": total,
            "approved": approved,
            "rejected": rejected,
        }

    def get_all_patterns(self) -> dict[str, LearnedPattern]:
        """Get all learned patterns."""
        return self.learned_patterns.copy()

    def get_all_preferences(self) -> dict[str, object]:
        """Get all user preferences."""
        return self.user_preferences.copy()
