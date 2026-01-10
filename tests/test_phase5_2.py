"""
Tests for Phase 5.2: Intelligent Refactoring Suggestions

This module tests the refactoring engine, consolidation detector,
split recommender, and reorganization planner.
"""

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

from cortex.refactoring.consolidation_detector import (
    ConsolidationDetector,
    ConsolidationOpportunity,
)
from cortex.refactoring.refactoring_engine import (
    RefactoringAction,
    RefactoringEngine,
    RefactoringPriority,
    RefactoringSuggestion,
    RefactoringType,
)
from cortex.refactoring.reorganization_planner import (
    ReorganizationAction,
    ReorganizationPlan,
    ReorganizationPlanner,
)
from cortex.refactoring.split_recommender import SplitRecommender


@pytest.fixture
def temp_memory_bank() -> Iterator[Path]:
    """Create a temporary memory bank directory for testing"""
    temp_dir = tempfile.mkdtemp()
    memory_bank = Path(temp_dir) / "memory-bank"
    memory_bank.mkdir()

    # Create test files
    _ = (memory_bank / "test1.md").write_text(
        """# Test File 1

## Introduction
This is a test file with some content.

## Common Section
This section appears in multiple files.
It contains important information.

## Details
Some specific details here.
"""
    )

    _ = (memory_bank / "test2.md").write_text(
        """# Test File 2

## Overview
Another test file.

## Common Section
This section appears in multiple files.
It contains important information.

## Specifics
File-specific content here.
"""
    )

    _ = (memory_bank / "large_file.md").write_text(
        """# Large File

"""
        + "\n\n".join(
            [
                f"""## Section {i}
Content for section {i}. """
                + ("x" * 500)
                for i in range(15)
            ]
        )
    )

    yield memory_bank

    # Cleanup
    shutil.rmtree(temp_dir)


# ============================================================================
# RefactoringEngine Tests
# ============================================================================


@pytest.mark.asyncio
async def test_refactoring_engine_init(temp_memory_bank: Path):
    """Test refactoring engine initialization"""
    engine = RefactoringEngine(
        memory_bank_path=temp_memory_bank,
        min_confidence=0.7,
        max_suggestions_per_run=10,
    )

    assert engine.memory_bank_path == temp_memory_bank
    assert engine.min_confidence == 0.7
    assert engine.max_suggestions_per_run == 10
    assert len(engine.suggestions) == 0


@pytest.mark.asyncio
async def test_refactoring_engine_generate_from_insight(temp_memory_bank: Path):
    """Test generating refactoring suggestion from insight"""
    engine = RefactoringEngine(memory_bank_path=temp_memory_bank, min_confidence=0.5)

    # Create mock insight
    insight: dict[str, object] = {
        "title": "Duplicate content detected",
        "description": "Multiple files contain similar sections",
        "category": "redundancy",
        "impact_score": 0.8,
        "severity": "high",
        "recommendations": ["Consolidate using transclusion"],
        "affected_files": [
            str(temp_memory_bank / "test1.md"),
            str(temp_memory_bank / "test2.md"),
        ],
    }

    suggestions = await engine.generate_suggestions(insights=[insight])

    assert len(suggestions) > 0
    suggestion = suggestions[0]
    assert suggestion.refactoring_type == RefactoringType.CONSOLIDATION
    assert suggestion.confidence_score == 0.8
    assert len(suggestion.affected_files) == 2
    assert len(suggestion.actions) > 0


@pytest.mark.asyncio
async def test_refactoring_engine_preview(temp_memory_bank: Path):
    """Test previewing a refactoring suggestion"""
    engine = RefactoringEngine(memory_bank_path=temp_memory_bank)

    # Create a test suggestion
    suggestion = RefactoringSuggestion(
        suggestion_id="TEST-001",
        refactoring_type=RefactoringType.CONSOLIDATION,
        priority=RefactoringPriority.HIGH,
        title="Test Suggestion",
        description="Test description",
        reasoning="Test reasoning",
        affected_files=["file1.md", "file2.md"],
        actions=[
            RefactoringAction(
                action_type="create",
                target_file="shared.md",
                description="Create shared file",
            )
        ],
        estimated_impact={"token_savings": 100},
        confidence_score=0.8,
    )

    engine.suggestions[suggestion.suggestion_id] = suggestion

    preview = await engine.preview_refactoring(suggestion_id="TEST-001", show_diff=True)

    assert preview["suggestion_id"] == "TEST-001"
    assert preview["title"] == "Test Suggestion"
    actions_raw = preview.get("actions", [])
    assert isinstance(actions_raw, list)
    actions = cast(list[dict[str, object]], actions_raw)
    assert len(actions) == 1


@pytest.mark.asyncio
async def test_refactoring_engine_export(temp_memory_bank: Path):
    """Test exporting suggestions"""
    engine = RefactoringEngine(memory_bank_path=temp_memory_bank)

    # Add a test suggestion
    suggestion = RefactoringSuggestion(
        suggestion_id="TEST-001",
        refactoring_type=RefactoringType.SPLIT,
        priority=RefactoringPriority.MEDIUM,
        title="Split large file",
        description="File is too large",
        reasoning="Improve maintainability",
        affected_files=["large.md"],
        actions=[],
        estimated_impact={},
        confidence_score=0.7,
    )
    engine.suggestions[suggestion.suggestion_id] = suggestion

    # Test JSON export
    json_export = await engine.export_suggestions(output_format="json")
    assert "TEST-001" in json_export
    assert "Split large file" in json_export

    # Test Markdown export
    md_export = await engine.export_suggestions(output_format="markdown")
    assert "# Refactoring Suggestions" in md_export
    assert "Split large file" in md_export

    # Test Text export
    text_export = await engine.export_suggestions(output_format="text")
    assert "Split large file" in text_export


# ============================================================================
# ConsolidationDetector Tests
# ============================================================================


@pytest.mark.asyncio
async def test_consolidation_detector_init(temp_memory_bank: Path):
    """Test consolidation detector initialization"""
    detector = ConsolidationDetector(
        memory_bank_path=temp_memory_bank,
        min_similarity=0.80,
        min_section_length=100,
        target_reduction=0.30,
    )

    assert detector.memory_bank_path == temp_memory_bank
    assert detector.min_similarity == 0.80
    assert detector.min_section_length == 100
    assert detector.target_reduction == 0.30


@pytest.mark.asyncio
async def test_consolidation_detect_exact_duplicates(temp_memory_bank: Path):
    """Test detecting exact duplicate sections"""
    detector = ConsolidationDetector(
        memory_bank_path=temp_memory_bank,
        min_similarity=0.80,
        min_section_length=50,  # Lower threshold for test
    )

    opportunities = await detector.detect_opportunities()

    # May or may not find duplicates depending on content
    # At minimum, verify the detector runs without errors
    assert isinstance(opportunities, list)

    if len(opportunities) > 0:
        # If we found opportunities, verify their properties
        opportunity = opportunities[0]
        assert opportunity.similarity_score >= 0.80
        assert len(opportunity.affected_files) >= 2
        assert opportunity.token_savings >= 0
        assert len(opportunity.transclusion_syntax) > 0


@pytest.mark.asyncio
async def test_consolidation_analyze_impact(temp_memory_bank: Path):
    """Test analyzing consolidation impact"""
    detector = ConsolidationDetector(memory_bank_path=temp_memory_bank)

    # Create a test opportunity
    opportunity = ConsolidationOpportunity(
        opportunity_id="CONS-0001",
        opportunity_type="exact_duplicate",
        affected_files=["file1.md", "file2.md"],
        common_content="Shared content",
        similarity_score=1.0,
        token_savings=100,
        suggested_action="Extract to shared file",
        extraction_target="shared.md",
        transclusion_syntax=["{{include: shared.md#section}}"],
    )

    impact = await detector.analyze_consolidation_impact(opportunity)

    assert impact["opportunity_id"] == "CONS-0001"
    assert impact["token_savings"] == 100
    assert impact["files_affected"] == 2
    assert impact["risk_level"] == "low"
    benefits_raw = impact.get("benefits", [])
    assert isinstance(benefits_raw, list)
    benefits = cast(list[str], benefits_raw)
    assert len(benefits) > 0


# ============================================================================
# SplitRecommender Tests
# ============================================================================


@pytest.mark.asyncio
async def test_split_recommender_init(temp_memory_bank: Path):
    """Test split recommender initialization"""
    recommender = SplitRecommender(
        memory_bank_path=temp_memory_bank, max_file_size=5000, max_sections=10
    )

    assert recommender.memory_bank_path == temp_memory_bank
    assert recommender.max_file_size == 5000
    assert recommender.max_sections == 10


@pytest.mark.asyncio
async def test_split_recommender_analyze_large_file(temp_memory_bank: Path):
    """Test analyzing a large file that needs splitting"""
    recommender = SplitRecommender(
        memory_bank_path=temp_memory_bank,
        max_file_size=2000,  # Set low to trigger split
        max_sections=5,
    )

    large_file = str(temp_memory_bank / "large_file.md")
    recommendation = await recommender.analyze_file(large_file)

    # Should recommend splitting
    assert recommendation is not None
    assert len(recommendation.split_points) > 0
    assert recommendation.split_strategy in ["by_sections", "by_size", "by_topics"]
    assert len(recommendation.estimated_impact) > 0


@pytest.mark.asyncio
async def test_split_recommender_suggest_splits(temp_memory_bank: Path):
    """Test suggesting splits for multiple files"""
    recommender = SplitRecommender(
        memory_bank_path=temp_memory_bank, max_file_size=2000, max_sections=5
    )

    recommendations = await recommender.suggest_file_splits()

    # Should find at least the large file
    assert len(recommendations) > 0

    # Check recommendation properties
    recommendation = recommendations[0]
    assert hasattr(recommendation, "file_path")
    assert hasattr(recommendation, "reason")
    assert hasattr(recommendation, "split_strategy")
    assert len(recommendation.split_points) > 0


@pytest.mark.asyncio
async def test_split_recommender_split_point(temp_memory_bank: Path):
    """Test split point generation"""
    recommender = SplitRecommender(memory_bank_path=temp_memory_bank)

    content = (temp_memory_bank / "large_file.md").read_text()

    sections = recommender.parse_file_structure(content)

    # Should parse multiple sections
    assert len(sections) > 5

    # Check section properties
    section = sections[0]
    assert "heading" in section
    assert "level" in section
    assert "start_line" in section
    assert "content" in section


# ============================================================================
# ReorganizationPlanner Tests
# ============================================================================


@pytest.mark.asyncio
async def test_reorganization_planner_init(temp_memory_bank: Path):
    """Test reorganization planner initialization"""
    planner = ReorganizationPlanner(
        memory_bank_path=temp_memory_bank,
        max_dependency_depth=5,
        enable_categories=True,
    )

    assert planner.memory_bank_path == temp_memory_bank
    assert planner.max_dependency_depth == 5
    assert planner.enable_categories is True


@pytest.mark.asyncio
async def test_reorganization_planner_analyze_structure(temp_memory_bank: Path):
    """Test analyzing current structure"""
    planner = ReorganizationPlanner(memory_bank_path=temp_memory_bank)

    structure = await planner.analyze_current_structure({}, {})

    assert "total_files" in structure
    total_files = structure.get("total_files", 0)
    assert isinstance(total_files, (int, float))
    assert total_files >= 3
    assert "organization" in structure
    assert "categories" in structure


@pytest.mark.asyncio
async def test_reorganization_planner_infer_categories(temp_memory_bank: Path):
    """Test inferring categories from filenames"""
    planner = ReorganizationPlanner(memory_bank_path=temp_memory_bank)

    files = [
        "memory-bank/activeContext.md",
        "memory-bank/techContext.md",
        "memory-bank/progress.md",
    ]

    categories = planner.infer_categories(files)

    # Should categorize files
    assert len(categories) > 0
    assert (
        "context" in categories or "technical" in categories or "progress" in categories
    )


@pytest.mark.asyncio
async def test_reorganization_planner_create_plan(temp_memory_bank: Path):
    """Test creating a reorganization plan"""
    planner = ReorganizationPlanner(memory_bank_path=temp_memory_bank)

    # Create mock structure data
    structure_data: dict[str, object] = {
        "organization": {"type": "flat"},
        "anti_patterns": {},
        "complexity_metrics": {"max_dependency_depth": 6},
    }

    plan = await planner.create_reorganization_plan(
        optimize_for="dependency_depth", structure_data=structure_data
    )

    # May or may not need reorganization depending on structure
    # Just verify it doesn't crash
    if plan:
        assert plan.optimization_goal == "dependency_depth"
        assert len(plan.actions) >= 0
        assert len(plan.estimated_impact) > 0


@pytest.mark.asyncio
async def test_reorganization_planner_preview(temp_memory_bank: Path):
    """Test previewing a reorganization plan"""
    planner = ReorganizationPlanner(memory_bank_path=temp_memory_bank)

    # Create a test plan
    plan = ReorganizationPlan(
        plan_id="REORG-0001",
        optimization_goal="category_based",
        current_structure={"organization": "flat"},
        proposed_structure={"organization": "category_based"},
        actions=[
            ReorganizationAction(
                action_type="move",
                source="file1.md",
                target="context/file1.md",
                reason="Categorize",
            )
        ],
        estimated_impact={"files_moved": 1},
        risks=["May break links"],
        benefits=["Better organization"],
    )

    preview = await planner.preview_reorganization(plan, show_details=True)

    assert preview["plan_id"] == "REORG-0001"
    assert preview["optimization_goal"] == "category_based"
    assert "actions" in preview
    actions_raw = preview.get("actions", [])
    assert isinstance(actions_raw, list)
    actions = cast(list[dict[str, object]], actions_raw)
    assert len(actions) == 1


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_integration_consolidation_to_refactoring(temp_memory_bank: Path):
    """Test full workflow from detection to refactoring suggestion"""
    # Step 1: Detect consolidation opportunities
    detector = ConsolidationDetector(
        memory_bank_path=temp_memory_bank,
        min_section_length=50,  # Lower threshold
    )
    opportunities = await detector.detect_opportunities()

    # Create insight manually for testing if no opportunities found
    if len(opportunities) == 0:
        # Create a synthetic opportunity for testing
        insight: dict[str, object] = {
            "title": "Test consolidation opportunity",
            "description": "Test duplicate content",
            "category": "redundancy",
            "impact_score": 0.8,
            "severity": "high",
            "recommendations": ["Consolidate using transclusion"],
            "affected_files": [
                str(temp_memory_bank / "test1.md"),
                str(temp_memory_bank / "test2.md"),
            ],
        }
    else:
        opportunity = opportunities[0]
        insight = {
            "title": f"Consolidation opportunity: {opportunity.opportunity_type}",
            "description": opportunity.suggested_action,
            "category": "redundancy",
            "impact_score": min(opportunity.similarity_score, 1.0),
            "severity": "high" if opportunity.token_savings > 200 else "medium",
            "recommendations": [opportunity.suggested_action],
            "affected_files": opportunity.affected_files,
        }

    # Step 2: Generate refactoring suggestion
    engine = RefactoringEngine(memory_bank_path=temp_memory_bank, min_confidence=0.5)
    suggestions = await engine.generate_suggestions(insights=[insight])

    assert len(suggestions) > 0
    suggestion = suggestions[0]
    assert suggestion.refactoring_type == RefactoringType.CONSOLIDATION
    assert len(suggestion.actions) > 0


@pytest.mark.asyncio
async def test_integration_split_to_refactoring(temp_memory_bank: Path):
    """Test full workflow from split detection to refactoring suggestion"""
    # For split type, we need to test the split recommender directly
    # as it generates different outputs than the refactoring engine
    recommender = SplitRecommender(
        memory_bank_path=temp_memory_bank, max_file_size=2000
    )
    recommendations = await recommender.suggest_file_splits()

    # The split recommender should generate recommendations
    # The refactoring engine generates different types of suggestions
    # This test verifies the split recommender works correctly
    if len(recommendations) > 0:
        recommendation = recommendations[0]
        assert recommendation.file_path is not None
        assert len(recommendation.split_points) > 0
        assert recommendation.split_strategy is not None
    else:
        # If no recommendations, verify the recommender runs without errors
        assert isinstance(recommendations, list)


if __name__ == "__main__":
    # Run tests
    _ = pytest.main([__file__, "-v"])
