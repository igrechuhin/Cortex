"""Unit tests for LearningEngine - Phase 5.4"""

from pathlib import Path
from typing import cast

import pytest

from cortex.refactoring.learning_engine import LearningEngine


class TestLearningEngineInitialization:
    """Test LearningEngine initialization."""

    def test_initialization_creates_data_manager(self, memory_bank_dir: Path):
        """Test engine initialization creates data manager."""
        # Arrange & Act
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Assert
        assert engine.memory_bank_dir == Path(memory_bank_dir)
        assert engine.data_manager is not None

    def test_initialization_with_config(self, memory_bank_dir: Path):
        """Test initialization with custom config."""
        # Arrange
        config: dict[str, object] = {"enabled": True, "min_feedback": 10}

        # Act
        engine = LearningEngine(memory_bank_dir=memory_bank_dir, config=config)

        # Assert
        assert engine.config == config


class TestRecordFeedback:
    """Test feedback recording."""

    @pytest.mark.asyncio
    async def test_record_feedback_stores_record(self, memory_bank_dir: Path):
        """Test recording feedback creates feedback record."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Act
        result = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="helpful",
            was_approved=True,
            was_applied=True,
        )

        # Assert
        assert result["status"] == "recorded"
        assert "feedback_id" in result
        assert len(engine.data_manager.feedback_records) == 1

    @pytest.mark.asyncio
    async def test_record_feedback_updates_patterns(self, memory_bank_dir: Path):
        """Test feedback updates learned patterns."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        suggestion_details: dict[str, object] = {
            "type": "consolidation",
            "similarity_threshold": 0.8,
            "confidence": 0.7,
        }

        # Act
        _ = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="helpful",
            was_approved=True,
            was_applied=True,
            suggestion_details=suggestion_details,
        )

        # Assert
        assert len(engine.data_manager.learned_patterns) > 0

    @pytest.mark.asyncio
    async def test_record_feedback_updates_preferences(self, memory_bank_dir: Path):
        """Test feedback updates user preferences."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Act
        _ = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="split",
            feedback_type="helpful",
            was_approved=True,
            was_applied=False,
        )

        # Assert
        pref_key = "suggestion_type_split"
        assert pref_key in engine.data_manager.user_preferences


class TestAdjustSuggestionConfidence:
    """Test confidence adjustment."""

    @pytest.mark.asyncio
    async def test_adjust_confidence_with_no_patterns(self, memory_bank_dir: Path):
        """Test confidence adjustment with no learned patterns."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        suggestion: dict[str, object] = {"type": "consolidation", "confidence": 0.7}

        # Act
        adjusted, details = await engine.adjust_suggestion_confidence(suggestion)

        # Assert
        assert adjusted == 0.7
        adjustments_val = details.get("adjustments", [])
        adjustments: list[dict[str, object]] = (
            cast(list[dict[str, object]], adjustments_val)
            if isinstance(adjustments_val, list)
            else []
        )
        assert len(adjustments) == 0

    @pytest.mark.asyncio
    async def test_adjust_confidence_with_successful_pattern(
        self, memory_bank_dir: Path
    ):
        """Test confidence boost for successful patterns."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Record successful feedback to create pattern
        for i in range(5):
            _ = await engine.record_feedback(
                suggestion_id=f"sug-{i}",
                suggestion_type="consolidation",
                feedback_type="helpful",
                was_approved=True,
                was_applied=True,
                suggestion_details={
                    "type": "consolidation",
                    "similarity_threshold": 0.8,
                },
            )

        suggestion: dict[str, object] = {
            "type": "consolidation",
            "confidence": 0.7,
            "similarity_threshold": 0.8,
        }

        # Act
        adjusted, _ = await engine.adjust_suggestion_confidence(suggestion)

        # Assert
        assert adjusted > 0.7

    @pytest.mark.asyncio
    async def test_adjust_confidence_with_failed_pattern(self, memory_bank_dir: Path):
        """Test confidence reduction for failed patterns."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Record failed feedback to create pattern
        for i in range(5):
            _ = await engine.record_feedback(
                suggestion_id=f"sug-{i}",
                suggestion_type="consolidation",
                feedback_type="not_helpful",
                was_approved=False,
                was_applied=False,
                suggestion_details={
                    "type": "consolidation",
                    "similarity_threshold": 0.8,
                },
            )

        suggestion: dict[str, object] = {
            "type": "consolidation",
            "confidence": 0.7,
            "similarity_threshold": 0.8,
        }

        # Act
        adjusted, _ = await engine.adjust_suggestion_confidence(suggestion)

        # Assert
        assert adjusted < 0.7


class TestShouldShowSuggestion:
    """Test suggestion filtering."""

    @pytest.mark.asyncio
    async def test_should_show_with_learning_disabled(self, memory_bank_dir: Path):
        """Test all suggestions shown when learning disabled."""
        # Arrange
        config: dict[str, object] = {"enabled": False}
        engine = LearningEngine(memory_bank_dir=memory_bank_dir, config=config)

        suggestion: dict[str, object] = {"type": "consolidation", "confidence": 0.3}

        # Act
        should_show, reason = await engine.should_show_suggestion(suggestion)

        # Assert
        assert should_show is True
        assert isinstance(reason, str)
        assert "disabled" in reason.lower()

    @pytest.mark.asyncio
    async def test_should_show_with_low_confidence(self, memory_bank_dir: Path):
        """Test suggestion filtered by low confidence."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        engine.data_manager.update_preference("min_confidence_threshold", 0.7)

        suggestion: dict[str, object] = {"type": "consolidation", "confidence": 0.5}

        # Act
        should_show, reason = await engine.should_show_suggestion(suggestion)

        # Assert
        assert should_show is False
        assert isinstance(reason, str)
        assert "below threshold" in reason

    @pytest.mark.asyncio
    async def test_should_show_with_rejected_type(self, memory_bank_dir: Path):
        """Test suggestion filtered by consistently rejected type."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Record multiple rejections
        for i in range(10):
            _ = await engine.record_feedback(
                suggestion_id=f"sug-{i}",
                suggestion_type="consolidation",
                feedback_type="not_helpful",
                was_approved=False,
                was_applied=False,
            )

        suggestion: dict[str, object] = {"type": "consolidation", "confidence": 1.0}

        # Act
        should_show, reason = await engine.should_show_suggestion(suggestion)

        # Assert
        assert should_show is False
        assert isinstance(reason, str)
        assert "consistently rejects" in reason


class TestGetLearningInsights:
    """Test learning insights."""

    @pytest.mark.asyncio
    async def test_get_learning_insights_calculates_statistics(
        self, memory_bank_dir: Path
    ):
        """Test insights include statistics."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        _ = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="helpful",
            was_approved=True,
            was_applied=True,
        )

        _ = await engine.record_feedback(
            suggestion_id="sug-2",
            suggestion_type="split",
            feedback_type="not_helpful",
            was_approved=False,
            was_applied=False,
        )

        # Act
        result = await engine.get_learning_insights()

        # Assert
        assert result["total_feedback"] == 2
        assert result["approved"] == 1
        assert result["rejected"] == 1
        assert result["approval_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_get_learning_insights_includes_recommendations(
        self, memory_bank_dir: Path
    ):
        """Test insights include recommendations."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Act
        result = await engine.get_learning_insights()

        # Assert
        assert "recommendations" in result
        recommendations_val = result.get("recommendations", [])
        recommendations: list[str] = (
            cast(list[str], recommendations_val)
            if isinstance(recommendations_val, list)
            else []
        )
        assert len(recommendations) > 0


class TestResetLearningData:
    """Test resetting learning data."""

    @pytest.mark.asyncio
    async def test_reset_learning_data_clears_all(self, memory_bank_dir: Path):
        """Test reset clears all data."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        _ = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="helpful",
            was_approved=True,
            was_applied=True,
        )

        # Act
        result = await engine.reset_learning_data(
            reset_feedback=True, reset_patterns=True, reset_preferences=True
        )

        # Assert
        assert result["status"] == "success"
        assert len(engine.data_manager.feedback_records) == 0


class TestExportLearnedPatterns:
    """Test exporting learned patterns."""

    @pytest.mark.asyncio
    async def test_export_patterns_as_json(self, memory_bank_dir: Path):
        """Test exporting patterns in JSON format."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        _ = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="helpful",
            was_approved=True,
            was_applied=True,
            suggestion_details={
                "type": "consolidation",
                "similarity_threshold": 0.8,
            },
        )

        # Act
        result = await engine.export_learned_patterns(format="json")

        # Assert
        assert "patterns" in result
        assert "export_date" in result

    @pytest.mark.asyncio
    async def test_export_patterns_as_text(self, memory_bank_dir: Path):
        """Test exporting patterns in text format."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        _ = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="split",
            feedback_type="helpful",
            was_approved=True,
            was_applied=True,
            suggestion_details={"type": "split", "file_tokens": 6000},
        )

        # Act
        result = await engine.export_learned_patterns(format="text")

        # Assert
        assert "content" in result
        content = result.get("content", "")
        assert isinstance(content, str)
        assert "Learned Patterns" in content

    @pytest.mark.asyncio
    async def test_export_patterns_with_invalid_format(self, memory_bank_dir: Path):
        """Test export with invalid format returns error."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Act
        result = await engine.export_learned_patterns(format="invalid")

        # Assert
        assert "error" in result


class TestPatternExtraction:
    """Test pattern key extraction."""

    @pytest.mark.asyncio
    async def test_extract_pattern_key_for_consolidation(self, memory_bank_dir: Path):
        """Test extracting pattern key for consolidation."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        from cortex.refactoring.learning_data_manager import FeedbackRecord

        feedback = FeedbackRecord(
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

        suggestion_details: dict[str, object] = {"similarity_threshold": 0.85}

        # Act
        key = engine.extract_pattern_key(feedback, suggestion_details)

        # Assert
        assert key is not None
        assert isinstance(key, str)
        assert "consolidation" in key

    @pytest.mark.asyncio
    async def test_extract_pattern_key_for_split(self, memory_bank_dir: Path):
        """Test extracting pattern key for split."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        from cortex.refactoring.learning_data_manager import FeedbackRecord

        feedback = FeedbackRecord(
            feedback_id="fb-1",
            suggestion_id="sug-1",
            suggestion_type="split",
            feedback_type="helpful",
            comment=None,
            created_at="2025-01-01T12:00:00",
            suggestion_confidence=0.8,
            was_approved=True,
            was_applied=True,
        )

        suggestion_details: dict[str, object] = {"file_tokens": 12000}

        # Act
        key = engine.extract_pattern_key(feedback, suggestion_details)

        # Assert
        assert key is not None
        assert isinstance(key, str)
        assert "split" in key


class TestPreferenceUpdates:
    """Test preference update logic."""

    @pytest.mark.asyncio
    async def test_preference_increases_min_threshold_on_not_helpful(
        self, memory_bank_dir: Path
    ):
        """Test min threshold increases when suggestions not helpful."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        engine.data_manager.update_preference("min_confidence_threshold", 0.5)

        # Act
        _ = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="not_helpful",
            was_approved=False,
            was_applied=False,
            suggestion_confidence=0.6,
        )

        # Assert
        threshold_val = engine.data_manager.get_preference("min_confidence_threshold")
        threshold = (
            float(threshold_val) if isinstance(threshold_val, (int, float)) else 0.5
        )
        assert threshold > 0.5

    @pytest.mark.asyncio
    async def test_preference_decreases_threshold_on_helpful_low_confidence(
        self, memory_bank_dir: Path
    ):
        """Test threshold decreases for helpful low-confidence suggestions."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        engine.data_manager.update_preference("min_confidence_threshold", 0.6)

        # Act
        _ = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="helpful",
            was_approved=True,
            was_applied=True,
            suggestion_confidence=0.55,
        )

        # Assert
        threshold_val = engine.data_manager.get_preference("min_confidence_threshold")
        threshold = (
            float(threshold_val) if isinstance(threshold_val, (int, float)) else 0.6
        )
        assert threshold < 0.6


class TestPatternKeyExtractionCoverage:
    """Test additional pattern extraction scenarios."""

    @pytest.mark.asyncio
    async def test_extract_pattern_key_for_reorganization(self, memory_bank_dir: Path):
        """Test extracting pattern key for reorganization."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        from cortex.refactoring.learning_data_manager import FeedbackRecord

        feedback = FeedbackRecord(
            feedback_id="fb-1",
            suggestion_id="sug-1",
            suggestion_type="reorganization",
            feedback_type="helpful",
            comment=None,
            created_at="2025-01-01T12:00:00",
            suggestion_confidence=0.8,
            was_approved=True,
            was_applied=True,
        )

        suggestion_details: dict[str, object] = {"optimization_goal": "category_based"}

        # Act
        key = engine.extract_pattern_key(feedback, suggestion_details)

        # Assert
        assert key == "reorganization-category_based"

    @pytest.mark.asyncio
    async def test_extract_pattern_key_for_split_large_file(
        self, memory_bank_dir: Path
    ):
        """Test pattern key for large file split."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        from cortex.refactoring.learning_data_manager import FeedbackRecord

        feedback = FeedbackRecord(
            feedback_id="fb-1",
            suggestion_id="sug-1",
            suggestion_type="split",
            feedback_type="helpful",
            comment=None,
            created_at="2025-01-01T12:00:00",
            suggestion_confidence=0.8,
            was_approved=True,
            was_applied=True,
        )

        suggestion_details: dict[str, object] = {"file_tokens": 15000}

        # Act
        key = engine.extract_pattern_key(feedback, suggestion_details)

        # Assert
        assert key == "split-large-file"

    @pytest.mark.asyncio
    async def test_extract_pattern_key_for_split_small_file(
        self, memory_bank_dir: Path
    ):
        """Test pattern key for small file split."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        from cortex.refactoring.learning_data_manager import FeedbackRecord

        feedback = FeedbackRecord(
            feedback_id="fb-1",
            suggestion_id="sug-1",
            suggestion_type="split",
            feedback_type="helpful",
            comment=None,
            created_at="2025-01-01T12:00:00",
            suggestion_confidence=0.8,
            was_approved=True,
            was_applied=True,
        )

        suggestion_details: dict[str, object] = {"file_tokens": 3000}

        # Act
        key = engine.extract_pattern_key(feedback, suggestion_details)

        # Assert
        assert key == "split-small-file"

    @pytest.mark.asyncio
    async def test_extract_pattern_key_for_unknown_type(self, memory_bank_dir: Path):
        """Test pattern key extraction for unknown type returns None."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        from cortex.refactoring.learning_data_manager import FeedbackRecord

        feedback = FeedbackRecord(
            feedback_id="fb-1",
            suggestion_id="sug-1",
            suggestion_type="unknown_type",
            feedback_type="helpful",
            comment=None,
            created_at="2025-01-01T12:00:00",
            suggestion_confidence=0.8,
            was_approved=True,
            was_applied=True,
        )

        suggestion_details: dict[str, object] = {}

        # Act
        key = engine.extract_pattern_key(feedback, suggestion_details)

        # Assert
        assert key is None


class TestExtractConditions:
    """Test extracting conditions from suggestion details."""

    def test_extract_conditions_with_all_fields(self, memory_bank_dir: Path):
        """Test extracting all condition fields."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        suggestion_details: dict[str, object] = {
            "confidence": 0.85,
            "thresholds": {"min_similarity": 0.8},
            "parameters": {"max_files": 10},
        }

        # Act
        conditions = engine.extract_conditions(suggestion_details)

        # Assert
        assert conditions["min_confidence"] == 0.85
        assert conditions["thresholds"] == {"min_similarity": 0.8}
        assert conditions["parameters"] == {"max_files": 10}

    def test_extract_conditions_with_defaults(self, memory_bank_dir: Path):
        """Test extracting conditions with default values."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        suggestion_details: dict[str, object] = {}

        # Act
        conditions = engine.extract_conditions(suggestion_details)

        # Assert
        assert conditions["min_confidence"] == 0.5
        assert conditions["thresholds"] == {}
        assert conditions["parameters"] == {}


class TestGetPreferenceRecommendation:
    """Test preference recommendation logic."""

    def test_preference_recommendation_not_enough_data(self, memory_bank_dir: Path):
        """Test recommendation when not enough data."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        pref: dict[str, object] = {"preference_score": 0.8, "total": 2}

        # Act
        recommendation = engine.get_preference_recommendation(pref)

        # Assert
        assert recommendation == "Not enough data yet"

    def test_preference_recommendation_strongly_preferred(self, memory_bank_dir: Path):
        """Test recommendation for strongly preferred type."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        pref: dict[str, object] = {"preference_score": 0.9, "total": 10}

        # Act
        recommendation = engine.get_preference_recommendation(pref)

        # Assert
        assert "Strongly preferred" in recommendation

    def test_preference_recommendation_somewhat_preferred(self, memory_bank_dir: Path):
        """Test recommendation for somewhat preferred type."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        pref: dict[str, object] = {"preference_score": 0.65, "total": 10}

        # Act
        recommendation = engine.get_preference_recommendation(pref)

        # Assert
        assert "Somewhat preferred" in recommendation

    def test_preference_recommendation_neutral(self, memory_bank_dir: Path):
        """Test recommendation for neutral preference."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        pref: dict[str, object] = {"preference_score": 0.45, "total": 10}

        # Act
        recommendation = engine.get_preference_recommendation(pref)

        # Assert
        assert "Neutral" in recommendation

    def test_preference_recommendation_not_preferred(self, memory_bank_dir: Path):
        """Test recommendation for not preferred type."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        pref: dict[str, object] = {"preference_score": 0.2, "total": 10}

        # Act
        recommendation = engine.get_preference_recommendation(pref)

        # Assert
        assert "Not preferred" in recommendation


class TestGetLearningRecommendations:
    """Test learning recommendation generation."""

    def test_recommendations_with_low_feedback(self, memory_bank_dir: Path):
        """Test recommendations when feedback count is low."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Act
        recommendations = engine.get_learning_recommendations()

        # Assert
        assert any("more feedback" in r.lower() for r in recommendations)

    @pytest.mark.asyncio
    async def test_recommendations_with_high_threshold(self, memory_bank_dir: Path):
        """Test recommendations when threshold is too high."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)
        engine.data_manager.update_preference("min_confidence_threshold", 0.85)

        # Act
        recommendations = engine.get_learning_recommendations()

        # Assert
        assert any("threshold is high" in r.lower() for r in recommendations)

    @pytest.mark.asyncio
    async def test_recommendations_with_low_success_patterns(
        self, memory_bank_dir: Path
    ):
        """Test recommendations when patterns have low success rate."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Create pattern with low success rate
        for i in range(5):
            _ = await engine.record_feedback(
                suggestion_id=f"sug-{i}",
                suggestion_type="consolidation",
                feedback_type="not_helpful",
                was_approved=False,
                was_applied=False,
                suggestion_details={
                    "type": "consolidation",
                    "similarity_threshold": 0.8,
                },
            )

        # Act
        recommendations = engine.get_learning_recommendations()

        # Assert
        assert any("low success rate" in r.lower() for r in recommendations)


class TestAdjustSuggestionConfidenceEdgeCases:
    """Test edge cases for confidence adjustment."""

    @pytest.mark.asyncio
    async def test_adjust_confidence_with_user_preference_boost(
        self, memory_bank_dir: Path
    ):
        """Test confidence boost based on user preference."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Record feedback to build preference
        for i in range(10):
            _ = await engine.record_feedback(
                suggestion_id=f"sug-{i}",
                suggestion_type="consolidation",
                feedback_type="helpful",
                was_approved=True,
                was_applied=True,
            )

        suggestion: dict[str, object] = {"type": "consolidation", "confidence": 0.6}

        # Act
        adjusted, details = await engine.adjust_suggestion_confidence(suggestion)

        # Assert
        assert adjusted > 0.6
        adjustments_val = details.get("adjustments", [])
        adjustments: list[dict[str, object]] = (
            cast(list[dict[str, object]], adjustments_val)
            if isinstance(adjustments_val, list)
            else []
        )
        assert any(
            "prefer" in str(adj.get("reason", "")).lower() for adj in adjustments
        )

    @pytest.mark.asyncio
    async def test_adjust_confidence_with_user_preference_reduction(
        self, memory_bank_dir: Path
    ):
        """Test confidence reduction based on user preference."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Record negative feedback to build preference
        for i in range(10):
            _ = await engine.record_feedback(
                suggestion_id=f"sug-{i}",
                suggestion_type="consolidation",
                feedback_type="not_helpful",
                was_approved=False,
                was_applied=False,
            )

        suggestion: dict[str, object] = {"type": "consolidation", "confidence": 0.6}

        # Act
        adjusted, details = await engine.adjust_suggestion_confidence(suggestion)

        # Assert
        assert adjusted < 0.6
        adjustments_val = details.get("adjustments", [])
        adjustments: list[dict[str, object]] = (
            cast(list[dict[str, object]], adjustments_val)
            if isinstance(adjustments_val, list)
            else []
        )
        assert any(
            "dislike" in str(adj.get("reason", "")).lower() for adj in adjustments
        )

    @pytest.mark.asyncio
    async def test_adjust_confidence_clamps_to_zero(self, memory_bank_dir: Path):
        """Test confidence is clamped to minimum 0."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Create very negative adjustments
        for i in range(10):
            _ = await engine.record_feedback(
                suggestion_id=f"sug-{i}",
                suggestion_type="consolidation",
                feedback_type="not_helpful",
                was_approved=False,
                was_applied=False,
                suggestion_details={
                    "type": "consolidation",
                    "similarity_threshold": 0.8,
                },
            )

        suggestion: dict[str, object] = {
            "type": "consolidation",
            "confidence": 0.1,
            "similarity_threshold": 0.8,
        }

        # Act
        adjusted, _ = await engine.adjust_suggestion_confidence(suggestion)

        # Assert
        assert adjusted >= 0.0

    @pytest.mark.asyncio
    async def test_adjust_confidence_clamps_to_one(self, memory_bank_dir: Path):
        """Test confidence is clamped to maximum 1."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Create very positive adjustments
        for i in range(10):
            _ = await engine.record_feedback(
                suggestion_id=f"sug-{i}",
                suggestion_type="consolidation",
                feedback_type="helpful",
                was_approved=True,
                was_applied=True,
                suggestion_details={
                    "type": "consolidation",
                    "similarity_threshold": 0.8,
                },
            )

        suggestion: dict[str, object] = {
            "type": "consolidation",
            "confidence": 0.95,
            "similarity_threshold": 0.8,
        }

        # Act
        adjusted, _ = await engine.adjust_suggestion_confidence(suggestion)

        # Assert
        assert adjusted <= 1.0


class TestShouldShowSuggestionEdgeCases:
    """Test edge cases for should show suggestion."""

    @pytest.mark.asyncio
    async def test_should_show_with_high_confidence(self, memory_bank_dir: Path):
        """Test suggestion with high confidence is shown."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        suggestion: dict[str, object] = {"type": "consolidation", "confidence": 0.95}

        # Act
        should_show, reason = await engine.should_show_suggestion(suggestion)

        # Assert
        assert should_show is True
        assert isinstance(reason, str)
        assert "meets" in reason.lower()

    @pytest.mark.asyncio
    async def test_should_show_with_neutral_preference(self, memory_bank_dir: Path):
        """Test suggestion with neutral preference is shown."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Record mixed feedback
        for i in range(5):
            _ = await engine.record_feedback(
                suggestion_id=f"sug-{i}",
                suggestion_type="consolidation",
                feedback_type="helpful" if i % 2 == 0 else "not_helpful",
                was_approved=i % 2 == 0,
                was_applied=i % 2 == 0,
            )

        suggestion: dict[str, object] = {"type": "consolidation", "confidence": 0.8}

        # Act
        should_show, _ = await engine.should_show_suggestion(suggestion)

        # Assert
        assert should_show is True


class TestUpdatePatternsCoverage:
    """Test pattern update logic coverage."""

    @pytest.mark.asyncio
    async def test_update_patterns_creates_new_pattern(self, memory_bank_dir: Path):
        """Test creating a new pattern from feedback."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        from cortex.refactoring.learning_data_manager import FeedbackRecord

        feedback = FeedbackRecord(
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

        suggestion_details: dict[str, object] = {"similarity_threshold": 0.9}

        # Act
        await engine.update_patterns(feedback, suggestion_details)

        # Assert
        patterns = engine.data_manager.get_all_patterns()
        assert len(patterns) > 0
        pattern = list(patterns.values())[0]
        assert pattern.total_occurrences == 1
        assert pattern.approved_count == 1

    @pytest.mark.asyncio
    async def test_update_patterns_updates_existing_rejected(
        self, memory_bank_dir: Path
    ):
        """Test updating pattern with rejection."""
        # Arrange
        engine = LearningEngine(memory_bank_dir=memory_bank_dir)

        # Create initial pattern
        _ = await engine.record_feedback(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            feedback_type="helpful",
            was_approved=True,
            was_applied=True,
            suggestion_details={"similarity_threshold": 0.8},
        )

        from cortex.refactoring.learning_data_manager import FeedbackRecord

        # Create rejection feedback
        feedback = FeedbackRecord(
            feedback_id="fb-2",
            suggestion_id="sug-2",
            suggestion_type="consolidation",
            feedback_type="not_helpful",
            comment=None,
            created_at="2025-01-01T12:00:00",
            suggestion_confidence=0.8,
            was_approved=False,
            was_applied=False,
        )

        suggestion_details: dict[str, object] = {"similarity_threshold": 0.8}

        # Act
        await engine.update_patterns(feedback, suggestion_details)

        # Assert
        pattern_key = engine.extract_pattern_key(feedback, suggestion_details)
        assert pattern_key is not None
        pattern = engine.data_manager.get_pattern(pattern_key)
        assert pattern is not None
        assert pattern.rejected_count > 0
