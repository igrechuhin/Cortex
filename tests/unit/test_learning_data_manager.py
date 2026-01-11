"""Unit tests for LearningDataManager - Phase 5.4"""

import json
from pathlib import Path

import pytest

from cortex.refactoring.learning_data_manager import (
    FeedbackRecord,
    LearnedPattern,
    LearningDataManager,
)


class TestFeedbackRecord:
    """Test FeedbackRecord dataclass."""

    def test_feedback_record_to_dict(self):
        """Test converting feedback record to dictionary."""
        # Arrange
        record = FeedbackRecord(
            feedback_id="fb-1",
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="helpful",
            comment="Great suggestion",
            created_at="2025-01-01T12:00:00",
            suggestion_confidence=0.8,
            was_approved=True,
            was_applied=True,
        )

        # Act
        result = record.to_dict()

        # Assert
        assert result["feedback_id"] == "fb-1"
        assert result["suggestion_type"] == "consolidation"
        assert result["was_approved"] is True


class TestLearnedPattern:
    """Test LearnedPattern dataclass."""

    def test_learned_pattern_to_dict(self):
        """Test converting learned pattern to dictionary."""
        # Arrange
        pattern = LearnedPattern(
            pattern_id="pat-1",
            pattern_type="consolidation",
            conditions={"min_confidence": 0.7},
            success_rate=0.85,
            total_occurrences=10,
            approved_count=8,
            rejected_count=2,
            last_seen="2025-01-01T12:00:00",
            confidence_adjustment=0.1,
        )

        # Act
        result = pattern.to_dict()

        # Assert
        assert result["pattern_id"] == "pat-1"
        assert result["success_rate"] == 0.85
        assert result["total_occurrences"] == 10


class TestLearningDataManagerInitialization:
    """Test LearningDataManager initialization."""

    def test_initialization_with_no_file(self, temp_project_root: Path):
        """Test manager initialization with no existing file."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"

        # Act
        manager = LearningDataManager(learning_file=learning_file)

        # Assert
        assert manager.learning_file == learning_file
        assert len(manager.feedback_records) == 0
        assert len(manager.learned_patterns) == 0
        assert len(manager.user_preferences) == 0

    def test_initialization_loads_existing_data(self, temp_project_root: Path):
        """Test manager loads existing learning data."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        learning_data: dict[str, object] = {
            "feedback": {
                "fb-1": {
                    "feedback_id": "fb-1",
                    "suggestion_id": "sug-1",
                    "suggestion_type": "consolidation",
                    "feedback_type": "helpful",
                    "comment": None,
                    "created_at": "2025-01-01T12:00:00",
                    "suggestion_confidence": 0.8,
                    "was_approved": True,
                    "was_applied": False,
                }
            },
            "patterns": {
                "pat-1": {
                    "pattern_id": "pat-1",
                    "pattern_type": "consolidation",
                    "conditions": {},
                    "success_rate": 0.9,
                    "total_occurrences": 5,
                    "approved_count": 4,
                    "rejected_count": 1,
                    "last_seen": "2025-01-01T12:00:00",
                    "confidence_adjustment": 0.1,
                }
            },
            "preferences": {"min_confidence_threshold": 0.6},
        }
        _ = learning_file.write_text(json.dumps(learning_data))

        # Act
        manager = LearningDataManager(learning_file=learning_file)

        # Assert
        assert len(manager.feedback_records) == 1
        assert len(manager.learned_patterns) == 1
        assert len(manager.user_preferences) == 1

    def test_initialization_handles_corrupted_file(self, temp_project_root: Path):
        """Test manager handles corrupted learning file."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        _ = learning_file.write_text("invalid json{")

        # Act
        manager = LearningDataManager(learning_file=learning_file)

        # Assert
        assert len(manager.feedback_records) == 0
        assert len(manager.learned_patterns) == 0


class TestSaveLearningData:
    """Test saving learning data."""

    @pytest.mark.asyncio
    async def test_save_creates_file_with_data(self, temp_project_root: Path):
        """Test save creates file with learning data."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        feedback = FeedbackRecord(
            feedback_id="fb-1",
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="helpful",
            comment=None,
            created_at="2025-01-01T12:00:00",
            suggestion_confidence=0.8,
            was_approved=True,
            was_applied=False,
        )
        manager.add_feedback(feedback)

        # Act
        await manager.save_learning_data()

        # Assert
        assert learning_file.exists()
        data = json.loads(learning_file.read_text())
        assert "feedback" in data
        assert "fb-1" in data["feedback"]

    @pytest.mark.asyncio
    async def test_save_preserves_all_data_types(self, temp_project_root: Path):
        """Test save preserves feedback, patterns, and preferences."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        manager.add_feedback(
            FeedbackRecord(
                feedback_id="fb-1",
                suggestion_id="sug-1",
                suggestion_type="consolidation",
                feedback_type="helpful",
                comment=None,
                created_at="2025-01-01T12:00:00",
                suggestion_confidence=0.8,
                was_approved=True,
                was_applied=False,
            )
        )

        manager.add_pattern(
            LearnedPattern(
                pattern_id="pat-1",
                pattern_type="consolidation",
                conditions={},
                success_rate=0.9,
                total_occurrences=5,
                approved_count=4,
                rejected_count=1,
                last_seen="2025-01-01T12:00:00",
                confidence_adjustment=0.1,
            )
        )

        manager.update_preference("min_confidence", 0.6)

        # Act
        await manager.save_learning_data()

        # Assert
        data = json.loads(learning_file.read_text())
        assert len(data["feedback"]) == 1
        assert len(data["patterns"]) == 1
        assert "min_confidence" in data["preferences"]


class TestFeedbackManagement:
    """Test feedback record management."""

    def test_add_feedback_stores_record(self, temp_project_root: Path):
        """Test adding feedback record."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        feedback = FeedbackRecord(
            feedback_id="fb-1",
            suggestion_id="sug-1",
            suggestion_type="split",
            feedback_type="not_helpful",
            comment="Too complex",
            created_at="2025-01-01T12:00:00",
            suggestion_confidence=0.5,
            was_approved=False,
            was_applied=False,
        )

        # Act
        manager.add_feedback(feedback)

        # Assert
        assert "fb-1" in manager.feedback_records
        assert manager.feedback_records["fb-1"].comment == "Too complex"

    def test_get_feedback_stats_calculates_correctly(self, temp_project_root: Path):
        """Test feedback statistics calculation."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        manager.add_feedback(
            FeedbackRecord(
                feedback_id="fb-1",
                suggestion_id="sug-1",
                suggestion_type="consolidation",
                feedback_type="helpful",
                comment=None,
                created_at="2025-01-01T12:00:00",
                suggestion_confidence=0.8,
                was_approved=True,
                was_applied=True,
            )
        )

        manager.add_feedback(
            FeedbackRecord(
                feedback_id="fb-2",
                suggestion_id="sug-2",
                suggestion_type="split",
                feedback_type="not_helpful",
                comment=None,
                created_at="2025-01-01T13:00:00",
                suggestion_confidence=0.6,
                was_approved=False,
                was_applied=False,
            )
        )

        # Act
        stats = manager.get_feedback_stats()

        # Assert
        assert stats["total"] == 2
        assert stats["approved"] == 1
        assert stats["rejected"] == 1


class TestPatternManagement:
    """Test learned pattern management."""

    def test_add_pattern_stores_pattern(self, temp_project_root: Path):
        """Test adding learned pattern."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        pattern = LearnedPattern(
            pattern_id="pat-1",
            pattern_type="reorganization",
            conditions={"optimization_goal": "dependency_depth"},
            success_rate=0.75,
            total_occurrences=8,
            approved_count=6,
            rejected_count=2,
            last_seen="2025-01-01T12:00:00",
            confidence_adjustment=0.05,
        )

        # Act
        manager.add_pattern(pattern)

        # Assert
        assert "pat-1" in manager.learned_patterns
        assert manager.learned_patterns["pat-1"].pattern_type == "reorganization"

    def test_get_pattern_retrieves_by_id(self, temp_project_root: Path):
        """Test retrieving pattern by ID."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        pattern = LearnedPattern(
            pattern_id="pat-1",
            pattern_type="split",
            conditions={},
            success_rate=0.8,
            total_occurrences=10,
            approved_count=8,
            rejected_count=2,
            last_seen="2025-01-01T12:00:00",
            confidence_adjustment=0.1,
        )
        manager.add_pattern(pattern)

        # Act
        result = manager.get_pattern("pat-1")

        # Assert
        assert result is not None
        assert result.pattern_id == "pat-1"

    def test_get_pattern_returns_none_for_nonexistent(self, temp_project_root: Path):
        """Test getting nonexistent pattern returns None."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        # Act
        result = manager.get_pattern("nonexistent")

        # Assert
        assert result is None

    def test_get_all_patterns_returns_copy(self, temp_project_root: Path):
        """Test getting all patterns returns copy."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        pattern = LearnedPattern(
            pattern_id="pat-1",
            pattern_type="consolidation",
            conditions={},
            success_rate=0.9,
            total_occurrences=5,
            approved_count=4,
            rejected_count=1,
            last_seen="2025-01-01T12:00:00",
            confidence_adjustment=0.1,
        )
        manager.add_pattern(pattern)

        # Act
        patterns = manager.get_all_patterns()

        # Assert
        assert "pat-1" in patterns
        assert patterns is not manager.learned_patterns


class TestPreferenceManagement:
    """Test user preference management."""

    def test_update_preference_stores_value(self, temp_project_root: Path):
        """Test updating user preference."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        # Act
        manager.update_preference("min_confidence_threshold", 0.7)

        # Assert
        assert manager.user_preferences["min_confidence_threshold"] == 0.7

    def test_get_preference_returns_value(self, temp_project_root: Path):
        """Test getting preference value."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)
        manager.update_preference("test_key", "test_value")

        # Act
        result = manager.get_preference("test_key")

        # Assert
        assert result == "test_value"

    def test_get_preference_returns_default_for_missing(self, temp_project_root: Path):
        """Test getting missing preference returns default."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        # Act
        result = manager.get_preference("missing_key", default="default_value")

        # Assert
        assert result == "default_value"

    def test_get_all_preferences_returns_copy(self, temp_project_root: Path):
        """Test getting all preferences returns copy."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)
        manager.update_preference("key1", "value1")

        # Act
        prefs = manager.get_all_preferences()

        # Assert
        assert "key1" in prefs
        assert prefs is not manager.user_preferences


class TestResetData:
    """Test resetting learning data."""

    @pytest.mark.asyncio
    async def test_reset_feedback_only(self, temp_project_root: Path):
        """Test resetting only feedback records."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        manager.add_feedback(
            FeedbackRecord(
                feedback_id="fb-1",
                suggestion_id="sug-1",
                suggestion_type="consolidation",
                feedback_type="helpful",
                comment=None,
                created_at="2025-01-01T12:00:00",
                suggestion_confidence=0.8,
                was_approved=True,
                was_applied=False,
            )
        )
        manager.update_preference("key", "value")

        # Act
        counts = await manager.reset_data(
            reset_feedback=True, reset_patterns=False, reset_preferences=False
        )

        # Assert
        assert counts["feedback_reset"] == 1
        assert len(manager.feedback_records) == 0
        assert len(manager.user_preferences) == 1

    @pytest.mark.asyncio
    async def test_reset_patterns_only(self, temp_project_root: Path):
        """Test resetting only learned patterns."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        manager.add_pattern(
            LearnedPattern(
                pattern_id="pat-1",
                pattern_type="consolidation",
                conditions={},
                success_rate=0.9,
                total_occurrences=5,
                approved_count=4,
                rejected_count=1,
                last_seen="2025-01-01T12:00:00",
                confidence_adjustment=0.1,
            )
        )

        # Act
        counts = await manager.reset_data(
            reset_feedback=False, reset_patterns=True, reset_preferences=False
        )

        # Assert
        assert counts["patterns_reset"] == 1
        assert len(manager.learned_patterns) == 0

    @pytest.mark.asyncio
    async def test_reset_all_data(self, temp_project_root: Path):
        """Test resetting all learning data."""
        # Arrange
        learning_file = temp_project_root / ".cortex/learning.json"
        manager = LearningDataManager(learning_file=learning_file)

        manager.add_feedback(
            FeedbackRecord(
                feedback_id="fb-1",
                suggestion_id="sug-1",
                suggestion_type="consolidation",
                feedback_type="helpful",
                comment=None,
                created_at="2025-01-01T12:00:00",
                suggestion_confidence=0.8,
                was_approved=True,
                was_applied=False,
            )
        )
        manager.add_pattern(
            LearnedPattern(
                pattern_id="pat-1",
                pattern_type="consolidation",
                conditions={},
                success_rate=0.9,
                total_occurrences=5,
                approved_count=4,
                rejected_count=1,
                last_seen="2025-01-01T12:00:00",
                confidence_adjustment=0.1,
            )
        )
        manager.update_preference("key", "value")

        # Act
        counts = await manager.reset_data(
            reset_feedback=True, reset_patterns=True, reset_preferences=True
        )

        # Assert
        assert counts["feedback_reset"] == 1
        assert counts["patterns_reset"] == 1
        assert counts["preferences_reset"] == 1
        assert len(manager.feedback_records) == 0
        assert len(manager.learned_patterns) == 0
        assert len(manager.user_preferences) == 0
