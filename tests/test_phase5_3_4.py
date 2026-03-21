"""
Pytest coverage for Phase 5.3–5.4: safe execution, approval management, and learning.

Replaces the previous script-only ``__main__`` harness so CI collects and runs these checks.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from cortex.core.models import ModelDict
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.learning_engine import LearningEngine


@pytest.fixture
def memory_bank_dir(tmp_path: Path) -> Path:
    """Memory bank path aligned with LearningEngine / ApprovalManager layout."""
    mb = tmp_path / ".cortex" / "memory-bank"
    mb.mkdir(parents=True)
    return mb


def test_phase5_3_4_module_imports() -> None:
    """Smoke-import public Phase 5.3–5.4 modules (already loaded above)."""
    assert AdaptationConfig is not None
    assert ApprovalManager is not None
    assert LearningEngine is not None


def test_adaptation_config_defaults_and_validation() -> None:
    adaptation_config = AdaptationConfig()
    assert adaptation_config.is_learning_enabled()
    assert adaptation_config.get_learning_rate() in (
        "aggressive",
        "moderate",
        "conservative",
    )
    assert 0 <= adaptation_config.get_min_confidence_threshold() <= 1
    assert 0 <= adaptation_config.get_max_confidence_threshold() <= 1
    validation = adaptation_config.validate()
    assert validation.valid
    summary = adaptation_config.get_summary()
    assert summary.learning_enabled is not None
    assert summary.learning_rate is not None


def test_learning_engine_initialization(memory_bank_dir: Path) -> None:
    learning_engine = LearningEngine(
        memory_bank_dir=memory_bank_dir,
        config=cast(ModelDict, {"enabled": True}),
    )
    assert learning_engine.config.get("enabled")


def test_approval_manager_initialization(memory_bank_dir: Path) -> None:
    approval_manager = ApprovalManager(memory_bank_dir=memory_bank_dir, config=None)
    assert len(approval_manager.approvals) == 0
    assert len(approval_manager.preferences) == 0


def test_adaptation_config_get_set_and_summary() -> None:
    adaptation_config = AdaptationConfig()
    value = adaptation_config.get("self_evolution.learning.enabled")
    assert isinstance(value, bool)
    adaptation_config.set("self_evolution.learning.learning_rate", "aggressive")
    assert adaptation_config.get_learning_rate() == "aggressive"
    summary = adaptation_config.get_summary()
    assert summary.learning_enabled is not None
    assert summary.learning_rate == "aggressive"


async def test_learning_engine_record_feedback(memory_bank_dir: Path) -> None:
    learning_engine = LearningEngine(
        memory_bank_dir=memory_bank_dir,
        config=cast(ModelDict, {"enabled": True}),
    )
    result = await learning_engine.record_feedback(
        suggestion_id="test-suggestion-1",
        suggestion_type="consolidation",
        feedback_type="helpful",
        comment="This consolidation was very useful",
        suggestion_confidence=0.8,
        was_approved=True,
        was_applied=True,
        suggestion_details={"similarity_threshold": 0.8},
    )
    assert result.status == "recorded"
    assert len(learning_engine.data_manager.feedback_records) == 1
    insights = await learning_engine.get_learning_insights()
    assert insights.total_feedback == 1
    assert insights.approved == 1


async def test_approval_manager_workflow(memory_bank_dir: Path) -> None:
    approval_manager = ApprovalManager(memory_bank_dir=memory_bank_dir, config=None)
    result = await approval_manager.request_approval(
        suggestion_id="test-suggestion-2",
        suggestion_type="split",
        auto_apply=False,
    )
    assert result.status == "success" or result.approval_id is not None
    approve_result = await approval_manager.approve_suggestion(
        suggestion_id="test-suggestion-2",
        user_comment="Looks good!",
        auto_apply=False,
    )
    assert approve_result.status == "approved"
    pending = await approval_manager.get_pending_approvals()
    assert pending.count is not None


async def test_learning_pattern_adjustment(memory_bank_dir: Path) -> None:
    learning_engine = LearningEngine(
        memory_bank_dir=memory_bank_dir,
        config=cast(ModelDict, {"enabled": True}),
    )
    suggestion = cast(
        ModelDict,
        {
            "type": "consolidation",
            "confidence": 0.6,
            "similarity_threshold": 0.8,
        },
    )
    adjusted_confidence, details = await learning_engine.adjust_suggestion_confidence(
        suggestion
    )
    assert isinstance(adjusted_confidence, float)
    assert 0 <= adjusted_confidence <= 1
    assert "original_confidence" in details
    assert "adjusted_confidence" in details
    should_show, reason = await learning_engine.should_show_suggestion(suggestion)
    assert isinstance(should_show, bool)
    assert isinstance(reason, str)


def test_adaptation_config_validation_detects_bad_thresholds() -> None:
    adaptation_config = AdaptationConfig()
    assert adaptation_config.validate().valid
    adaptation_config.set("self_evolution.adaptation.min_confidence_threshold", 0.9)
    adaptation_config.set("self_evolution.adaptation.max_confidence_threshold", 0.2)
    bad = adaptation_config.validate()
    assert not bad.valid
    assert len(bad.issues) > 0
    adaptation_config.reset_to_defaults()
    assert adaptation_config.validate().valid


async def test_learning_insights(memory_bank_dir: Path) -> None:
    learning_engine = LearningEngine(
        memory_bank_dir=memory_bank_dir,
        config=cast(ModelDict, {"enabled": True}),
    )
    insights = await learning_engine.get_learning_insights()
    assert insights.learning_enabled is not None
    assert insights.total_feedback is not None
    assert insights.learned_patterns is not None
    assert insights.recommendations is not None
    assert isinstance(insights.recommendations, list)
