"""
Tests for RefactoringEngine

This module tests the refactoring engine that generates intelligent refactoring
suggestions based on pattern analysis, structure analysis, and quality metrics.
"""

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.refactoring.refactoring_engine import (
    RefactoringAction,
    RefactoringEngine,
    RefactoringPriority,
    RefactoringSuggestion,
    RefactoringType,
)


@pytest.fixture
def refactoring_engine(tmp_path: Path):
    """Create refactoring engine instance"""
    return RefactoringEngine(
        memory_bank_path=tmp_path,
        min_confidence=0.7,
        max_suggestions_per_run=10,
    )


@pytest.fixture
def sample_insight() -> dict[str, str | float | list[str]]:
    """Sample insight data"""
    return {
        "title": "Duplicate Content Found",
        "description": "Files A and B contain similar sections",
        "category": "redundancy",
        "severity": "high",
        "impact_score": 0.85,
        "affected_files": ["memory-bank/file-a.md", "memory-bank/file-b.md"],
        "recommendations": ["Extract common content", "Use transclusion"],
    }


@pytest.fixture
def sample_structure_data() -> dict[str, object]:
    """Sample structure analysis data"""
    return {
        "anti_patterns": {
            "orphaned_files": [
                "memory-bank/orphan1.md",
                "memory-bank/orphan2.md",
                "memory-bank/orphan3.md",
            ],
            "oversized_files": ["memory-bank/large.md"],
        },
        "organization": {
            "total_files": 10,
            "avg_size_kb": 25,
        },
    }


class TestRefactoringEngineInitialization:
    """Test RefactoringEngine initialization"""

    def test_initialization_with_defaults(self, tmp_path: Path):
        """Test engine initialization with default values"""
        engine = RefactoringEngine(tmp_path)

        assert engine.memory_bank_path == tmp_path
        assert engine.min_confidence == 0.7
        assert engine.max_suggestions_per_run == 10
        assert engine.suggestions == {}
        assert engine.suggestion_counter == 0

    def test_initialization_with_custom_values(self, tmp_path: Path):
        """Test engine initialization with custom values"""
        engine = RefactoringEngine(
            memory_bank_path=tmp_path, min_confidence=0.8, max_suggestions_per_run=5
        )

        assert engine.min_confidence == 0.8
        assert engine.max_suggestions_per_run == 5

    def test_path_conversion(self, tmp_path: Path):
        """Test that path is converted to Path object"""
        engine = RefactoringEngine(memory_bank_path=tmp_path)

        assert isinstance(engine.memory_bank_path, Path)
        assert engine.memory_bank_path == tmp_path


class TestSuggestionIDGeneration:
    """Test suggestion ID generation"""

    def test_generate_unique_ids(self, refactoring_engine: RefactoringEngine):
        """Test that generated IDs are unique"""
        id1 = refactoring_engine.generate_suggestion_id(RefactoringType.CONSOLIDATION)
        id2 = refactoring_engine.generate_suggestion_id(RefactoringType.SPLIT)
        id3 = refactoring_engine.generate_suggestion_id(RefactoringType.CONSOLIDATION)

        assert id1 != id2
        assert id1 != id3
        assert id2 != id3

    def test_id_format(self, refactoring_engine: RefactoringEngine):
        """Test that IDs follow expected format"""
        suggestion_id = refactoring_engine.generate_suggestion_id(
            RefactoringType.CONSOLIDATION
        )

        assert suggestion_id.startswith("REF-CON-")
        assert len(suggestion_id.split("-")) == 4  # REF-TYPE-TIMESTAMP-COUNTER

    def test_id_includes_type_prefix(self, refactoring_engine: RefactoringEngine):
        """Test that ID includes type prefix"""
        consolidation_id = refactoring_engine.generate_suggestion_id(
            RefactoringType.CONSOLIDATION
        )
        split_id = refactoring_engine.generate_suggestion_id(RefactoringType.SPLIT)
        reorg_id = refactoring_engine.generate_suggestion_id(
            RefactoringType.REORGANIZATION
        )

        assert "CON" in consolidation_id
        assert "SPL" in split_id
        assert "REO" in reorg_id

    def test_counter_increments(self, refactoring_engine: RefactoringEngine):
        """Test that counter increments with each ID"""
        id1 = refactoring_engine.generate_suggestion_id(RefactoringType.CONSOLIDATION)
        id2 = refactoring_engine.generate_suggestion_id(RefactoringType.CONSOLIDATION)

        # Extract counter from IDs
        counter1 = int(id1.split("-")[-1])
        counter2 = int(id2.split("-")[-1])

        assert counter2 == counter1 + 1


class TestGenerateSuggestions:
    """Test suggestion generation"""

    @pytest.mark.asyncio
    async def test_generate_empty_when_no_data(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test that no suggestions are generated without data"""
        suggestions = await refactoring_engine.generate_suggestions()

        assert suggestions == []
        assert refactoring_engine.suggestions == {}

    @pytest.mark.asyncio
    async def test_generate_from_insights(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test generating suggestions from insights"""
        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )

        assert len(suggestions) > 0
        assert suggestions[0].refactoring_type == RefactoringType.CONSOLIDATION
        assert suggestions[0].confidence_score >= refactoring_engine.min_confidence

    @pytest.mark.asyncio
    async def test_filters_low_confidence_suggestions(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test that low confidence suggestions are filtered"""
        low_confidence_insight: dict[str, str | float | list[str]] = {
            "title": "Minor Issue",
            "description": "Low impact issue",
            "category": "redundancy",
            "severity": "low",
            "impact_score": 0.5,  # Below min_confidence of 0.7
            "affected_files": ["memory-bank/file.md"],
            "recommendations": ["Consider review"],
        }

        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [low_confidence_insight])
        )

        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_limits_suggestions_count(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test that suggestions are limited to max_suggestions_per_run"""
        refactoring_engine.max_suggestions_per_run = 2

        # Create multiple high-confidence insights
        insights: list[dict[str, str | float | list[str]]] = [
            {
                "title": f"Issue {i}",
                "description": f"Description {i}",
                "category": "redundancy",
                "severity": "high",
                "impact_score": 0.85,
                "affected_files": [f"file{i}.md", f"file{i + 1}.md"],
                "recommendations": ["Fix it"],
            }
            for i in range(5)
        ]

        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], insights)
        )

        assert len(suggestions) == 2  # Limited to max_suggestions_per_run

    @pytest.mark.asyncio
    async def test_sorts_by_priority_and_confidence(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test that suggestions are sorted correctly"""
        insights: list[dict[str, str | float | list[str]]] = [
            {
                "title": "Low Priority",
                "description": "Low priority issue",
                "category": "redundancy",
                "severity": "low",
                "impact_score": 0.75,
                "affected_files": ["file1.md", "file2.md"],
                "recommendations": ["Fix"],
            },
            {
                "title": "High Priority",
                "description": "High priority issue",
                "category": "redundancy",
                "severity": "high",
                "impact_score": 0.85,
                "affected_files": ["file3.md", "file4.md"],
                "recommendations": ["Fix now"],
            },
            {
                "title": "Medium Priority High Confidence",
                "description": "Medium priority",
                "category": "redundancy",
                "severity": "medium",
                "impact_score": 0.95,
                "affected_files": ["file5.md", "file6.md"],
                "recommendations": ["Consider"],
            },
        ]

        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], insights)
        )

        # High priority should come first
        assert suggestions[0].priority == RefactoringPriority.HIGH
        # Medium priority with higher confidence should come before low priority
        assert suggestions[1].priority == RefactoringPriority.MEDIUM

    @pytest.mark.asyncio
    async def test_filters_by_categories(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test filtering by categories"""
        # Only request split suggestions
        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight]),
            categories=["split"],
        )

        # Should not generate consolidation suggestions
        assert all(
            s.refactoring_type != RefactoringType.CONSOLIDATION for s in suggestions
        )

    @pytest.mark.asyncio
    async def test_stores_generated_suggestions(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test that generated suggestions are stored"""
        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )

        assert len(refactoring_engine.suggestions) == len(suggestions)
        for suggestion in suggestions:
            assert suggestion.suggestion_id in refactoring_engine.suggestions

    @pytest.mark.asyncio
    async def test_generates_organization_suggestions_from_structure(
        self,
        refactoring_engine: RefactoringEngine,
        sample_structure_data: dict[str, object],
    ):
        """Test generating organization suggestions from structure data"""
        suggestions = await refactoring_engine.generate_suggestions(
            structure_data=sample_structure_data
        )

        # Should generate suggestion for orphaned files
        assert len(suggestions) > 0
        assert any(
            s.refactoring_type == RefactoringType.REORGANIZATION for s in suggestions
        )


class TestGenerateFromInsight:
    """Test generating individual suggestions from insights"""

    @pytest.mark.asyncio
    async def test_creates_consolidation_suggestion(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test creating consolidation suggestion"""
        suggestion = await refactoring_engine.generate_from_insight(
            cast(dict[str, object], sample_insight), RefactoringType.CONSOLIDATION
        )

        assert suggestion is not None
        assert suggestion.refactoring_type == RefactoringType.CONSOLIDATION
        assert suggestion.title == sample_insight["title"]
        assert len(suggestion.actions) > 0

    @pytest.mark.asyncio
    async def test_creates_split_suggestion(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test creating split suggestion"""
        insight: dict[str, str | float | list[str]] = {
            "title": "Large File",
            "description": "File is too large",
            "category": "organization",
            "severity": "high",
            "impact_score": 0.8,
            "affected_files": ["memory-bank/large-file.md"],
            "recommendations": ["Split into sections"],
        }

        suggestion = await refactoring_engine.generate_from_insight(
            cast(dict[str, object], insight), RefactoringType.SPLIT
        )

        assert suggestion is not None
        assert suggestion.refactoring_type == RefactoringType.SPLIT

    @pytest.mark.asyncio
    async def test_maps_severity_to_priority(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test that severity is mapped to priority correctly"""
        insights: list[dict[str, str | float | list[str]]] = [
            {
                "title": "High Severity",
                "description": "High issue",
                "category": "redundancy",
                "severity": "high",
                "impact_score": 0.8,
                "affected_files": ["file1.md", "file2.md"],
                "recommendations": [],
            },
            {
                "title": "Medium Severity",
                "description": "Medium issue",
                "category": "redundancy",
                "severity": "medium",
                "impact_score": 0.8,
                "affected_files": ["file3.md", "file4.md"],
                "recommendations": [],
            },
            {
                "title": "Low Severity",
                "description": "Low issue",
                "category": "redundancy",
                "severity": "low",
                "impact_score": 0.8,
                "affected_files": ["file5.md", "file6.md"],
                "recommendations": [],
            },
        ]

        high_suggestion = await refactoring_engine.generate_from_insight(
            cast(dict[str, object], insights[0]), RefactoringType.CONSOLIDATION
        )
        medium_suggestion = await refactoring_engine.generate_from_insight(
            cast(dict[str, object], insights[1]), RefactoringType.CONSOLIDATION
        )
        low_suggestion = await refactoring_engine.generate_from_insight(
            cast(dict[str, object], insights[2]), RefactoringType.CONSOLIDATION
        )

        assert high_suggestion is not None
        assert medium_suggestion is not None
        assert low_suggestion is not None
        assert high_suggestion.priority == RefactoringPriority.HIGH
        assert medium_suggestion.priority == RefactoringPriority.MEDIUM
        assert low_suggestion.priority == RefactoringPriority.LOW

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_insight(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test that None is returned for invalid insight"""
        invalid_insights: list[dict[str, object]] = [
            {},  # Empty
            {"title": "No Files"},  # No affected_files
            {"affected_files": ["file.md"]},  # No title
        ]

        for insight in invalid_insights:
            suggestion = await refactoring_engine.generate_from_insight(
                insight, RefactoringType.CONSOLIDATION
            )
            assert suggestion is None

    @pytest.mark.asyncio
    async def test_calculates_estimated_impact(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test that estimated impact is calculated"""
        suggestion = await refactoring_engine.generate_from_insight(
            cast(dict[str, object], sample_insight), RefactoringType.CONSOLIDATION
        )

        assert suggestion is not None
        impact = suggestion.estimated_impact
        assert "token_savings" in impact
        assert "files_affected" in impact
        assert "complexity_reduction" in impact
        assert "maintainability_improvement" in impact
        affected_files = sample_insight["affected_files"]
        assert isinstance(affected_files, list)
        assert impact["files_affected"] == len(affected_files)

    @pytest.mark.asyncio
    async def test_includes_metadata(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test that metadata is included in suggestion"""
        suggestion = await refactoring_engine.generate_from_insight(
            cast(dict[str, object], sample_insight), RefactoringType.CONSOLIDATION
        )

        assert suggestion is not None
        assert "source" in suggestion.metadata
        assert suggestion.metadata["source"] == "insight"
        assert "insight_category" in suggestion.metadata
        assert suggestion.metadata["insight_category"] == sample_insight["category"]


class TestGenerateActions:
    """Test action generation"""

    def test_generates_consolidation_actions(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test generating consolidation actions"""
        affected_files = ["file1.md", "file2.md"]
        actions = refactoring_engine.generate_actions(
            RefactoringType.CONSOLIDATION, affected_files, []
        )

        assert len(actions) > 0
        # Should create a shared file and modify original files
        action_types = [a.action_type for a in actions]
        assert "create" in action_types
        assert "modify" in action_types

    def test_generates_split_actions(self, refactoring_engine: RefactoringEngine):
        """Test generating split actions"""
        affected_files = ["large-file.md"]
        actions = refactoring_engine.generate_actions(
            RefactoringType.SPLIT, affected_files, []
        )

        assert len(actions) > 0
        action_types = [a.action_type for a in actions]
        assert "create" in action_types
        assert "modify" in action_types

    def test_generates_reorganization_actions(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test generating reorganization actions"""
        affected_files = ["file1.md", "file2.md"]
        actions = refactoring_engine.generate_actions(
            RefactoringType.REORGANIZATION, affected_files, []
        )

        assert len(actions) > 0
        assert actions[0].action_type == "move"

    def test_consolidation_requires_multiple_files(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test that consolidation requires multiple files"""
        # Single file should not generate consolidation actions
        actions = refactoring_engine.generate_actions(
            RefactoringType.CONSOLIDATION, ["file1.md"], []
        )

        assert len(actions) == 0


class TestBuildReasoning:
    """Test reasoning building"""

    def test_includes_insight_description(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test that reasoning includes insight description"""
        reasoning = refactoring_engine.build_reasoning(
            cast(dict[str, object], sample_insight), RefactoringType.CONSOLIDATION
        )

        description = sample_insight["description"]
        assert isinstance(description, str)
        assert description in reasoning

    def test_includes_type_specific_reasoning(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test type-specific reasoning"""
        consolidation_reasoning = refactoring_engine.build_reasoning(
            cast(dict[str, object], sample_insight), RefactoringType.CONSOLIDATION
        )
        split_reasoning = refactoring_engine.build_reasoning(
            cast(dict[str, object], sample_insight), RefactoringType.SPLIT
        )
        reorg_reasoning = refactoring_engine.build_reasoning(
            cast(dict[str, object], sample_insight), RefactoringType.REORGANIZATION
        )

        assert "Consolidating" in consolidation_reasoning
        assert "Splitting" in split_reasoning
        assert "Reorganizing" in reorg_reasoning

    def test_includes_high_impact_note(self, refactoring_engine: RefactoringEngine):
        """Test that high impact is noted"""
        high_impact_insight: dict[str, str | float] = {
            "description": "Major issue",
            "impact_score": 0.85,
        }

        reasoning = refactoring_engine.build_reasoning(
            cast(dict[str, object], high_impact_insight), RefactoringType.CONSOLIDATION
        )

        assert "high potential impact" in reasoning


class TestOrganizationSuggestions:
    """Test organization suggestion generation"""

    @pytest.mark.asyncio
    async def test_suggests_orphaned_file_integration(
        self,
        refactoring_engine: RefactoringEngine,
        sample_structure_data: dict[str, object],
    ):
        """Test suggestion for orphaned files"""
        suggestions = await refactoring_engine.generate_organization_suggestions(
            sample_structure_data
        )

        assert len(suggestions) > 0
        orphan_suggestion = suggestions[0]
        assert orphan_suggestion.refactoring_type == RefactoringType.REORGANIZATION
        assert "Orphaned" in orphan_suggestion.title

    @pytest.mark.asyncio
    async def test_requires_multiple_orphaned_files(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test that multiple orphaned files are needed"""
        structure_data: dict[str, dict[str, list[str]]] = {
            "anti_patterns": {
                "orphaned_files": ["file1.md", "file2.md"],  # Only 2 files
            }
        }

        suggestions = await refactoring_engine.generate_organization_suggestions(
            cast(dict[str, object], structure_data)
        )

        # Should not generate suggestion for < 3 orphaned files
        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_limits_actions_for_orphaned_files(
        self,
        refactoring_engine: RefactoringEngine,
        sample_structure_data: dict[str, object],
    ):
        """Test that actions are limited for orphaned files"""
        suggestions = await refactoring_engine.generate_organization_suggestions(
            sample_structure_data
        )

        if suggestions:
            # Should limit to 3 actions even if more orphaned files
            assert len(suggestions[0].actions) <= 3


class TestPriorityToNumber:
    """Test priority to number conversion"""

    def test_converts_all_priorities(self, refactoring_engine: RefactoringEngine):
        """Test that all priorities convert correctly"""
        priorities = [
            (RefactoringPriority.CRITICAL, 0),
            (RefactoringPriority.HIGH, 1),
            (RefactoringPriority.MEDIUM, 2),
            (RefactoringPriority.LOW, 3),
            (RefactoringPriority.OPTIONAL, 4),
        ]

        for priority, expected in priorities:
            assert refactoring_engine.priority_to_number(priority) == expected

    def test_critical_is_highest_priority(self, refactoring_engine: RefactoringEngine):
        """Test that critical has lowest number (highest priority)"""
        critical = refactoring_engine.priority_to_number(RefactoringPriority.CRITICAL)
        high = refactoring_engine.priority_to_number(RefactoringPriority.HIGH)

        assert critical < high


class TestGetSuggestion:
    """Test getting individual suggestions"""

    @pytest.mark.asyncio
    async def test_returns_stored_suggestion(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test retrieving stored suggestion"""
        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )
        suggestion_id = suggestions[0].suggestion_id

        retrieved = await refactoring_engine.get_suggestion(suggestion_id)

        assert retrieved is not None
        assert retrieved.suggestion_id == suggestion_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_id(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test that None is returned for unknown ID"""
        result = await refactoring_engine.get_suggestion("unknown-id")

        assert result is None


class TestPreviewRefactoring:
    """Test refactoring preview"""

    @pytest.mark.asyncio
    async def test_preview_includes_suggestion_details(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test that preview includes suggestion details"""
        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )
        suggestion_id = suggestions[0].suggestion_id

        preview = await refactoring_engine.preview_refactoring(suggestion_id)

        assert "suggestion_id" in preview
        assert preview["suggestion_id"] == suggestion_id
        assert "title" in preview
        assert "refactoring_type" in preview
        assert "affected_files" in preview
        assert "actions" in preview

    @pytest.mark.asyncio
    async def test_preview_includes_actions(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test that preview includes action details"""
        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )
        suggestion_id = suggestions[0].suggestion_id

        preview = await refactoring_engine.preview_refactoring(suggestion_id)

        actions: object | None = preview.get("actions")
        assert actions is not None
        assert isinstance(actions, list)
        actions_list: list[dict[str, object]] = cast(list[dict[str, object]], actions)
        assert len(actions_list) > 0
        assert isinstance(actions_list[0], dict)
        assert "action_type" in actions_list[0]
        assert "target_file" in actions_list[0]
        assert "description" in actions_list[0]

    @pytest.mark.asyncio
    async def test_preview_with_diff(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test preview with diff enabled"""
        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )
        suggestion_id = suggestions[0].suggestion_id

        preview = await refactoring_engine.preview_refactoring(
            suggestion_id, show_diff=True
        )

        # Should include preview for actions
        actions: object | None = preview.get("actions")
        assert actions is not None
        assert isinstance(actions, list)
        actions_list: list[dict[str, object]] = cast(list[dict[str, object]], actions)
        assert len(actions_list) > 0
        assert isinstance(actions[0], dict)
        assert "preview" in actions[0]

    @pytest.mark.asyncio
    async def test_preview_without_diff(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test preview with diff disabled"""
        suggestions = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )
        suggestion_id = suggestions[0].suggestion_id

        preview = await refactoring_engine.preview_refactoring(
            suggestion_id, show_diff=False
        )

        # Should not include preview for actions
        actions: object | None = preview.get("actions")
        assert actions is not None
        assert isinstance(actions, list)
        actions_list: list[dict[str, object]] = cast(list[dict[str, object]], actions)
        assert len(actions_list) > 0
        assert isinstance(actions[0], dict)
        assert "preview" not in actions[0]

    @pytest.mark.asyncio
    async def test_preview_unknown_suggestion(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test preview of unknown suggestion"""
        preview = await refactoring_engine.preview_refactoring("unknown-id")

        assert "error" in preview


class TestGetAllSuggestions:
    """Test getting all suggestions with filters"""

    @pytest.mark.asyncio
    async def test_returns_all_suggestions_without_filters(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test getting all suggestions without filters"""
        insights = [
            {
                "title": f"Issue {i}",
                "description": f"Desc {i}",
                "category": "redundancy",
                "severity": "high",
                "impact_score": 0.8,
                "affected_files": [f"file{i}.md", f"file{i + 1}.md"],
                "recommendations": [],
            }
            for i in range(3)
        ]

        _ = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], insights)
        )
        all_suggestions = await refactoring_engine.get_all_suggestions()

        assert len(all_suggestions) == 3

    @pytest.mark.asyncio
    async def test_filters_by_type(self, refactoring_engine: RefactoringEngine):
        """Test filtering by refactoring type"""
        insights = [
            {
                "title": "Consolidation Issue",
                "description": "Duplicate content",
                "category": "redundancy",
                "severity": "high",
                "impact_score": 0.8,
                "affected_files": ["file1.md", "file2.md"],
                "recommendations": [],
            },
            {
                "title": "Split Issue",
                "description": "Large file",
                "category": "organization",
                "severity": "high",
                "impact_score": 0.8,
                "affected_files": ["large.md"],
                "recommendations": [],
            },
        ]

        _ = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], insights)
        )
        consolidation_suggestions = await refactoring_engine.get_all_suggestions(
            filter_by_type=RefactoringType.CONSOLIDATION
        )

        assert all(
            s.refactoring_type == RefactoringType.CONSOLIDATION
            for s in consolidation_suggestions
        )

    @pytest.mark.asyncio
    async def test_filters_by_priority(self, refactoring_engine: RefactoringEngine):
        """Test filtering by priority"""
        insights = [
            {
                "title": "High Priority",
                "description": "High issue",
                "category": "redundancy",
                "severity": "high",
                "impact_score": 0.8,
                "affected_files": ["file1.md", "file2.md"],
                "recommendations": [],
            },
            {
                "title": "Low Priority",
                "description": "Low issue",
                "category": "redundancy",
                "severity": "low",
                "impact_score": 0.75,
                "affected_files": ["file3.md", "file4.md"],
                "recommendations": [],
            },
        ]

        _ = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], insights)
        )
        high_priority = await refactoring_engine.get_all_suggestions(
            filter_by_priority=RefactoringPriority.HIGH
        )

        assert all(s.priority == RefactoringPriority.HIGH for s in high_priority)

    @pytest.mark.asyncio
    async def test_filters_by_confidence(self, refactoring_engine: RefactoringEngine):
        """Test filtering by minimum confidence"""
        refactoring_engine.min_confidence = 0.0  # Allow all for test

        insights: list[dict[str, str | float | list[str]]] = [
            {
                "title": f"Issue {i}",
                "description": f"Desc {i}",
                "category": "redundancy",
                "severity": "high",
                "impact_score": 0.7 + i * 0.1,
                "affected_files": [f"file{i}.md", f"file{i + 1}.md"],
                "recommendations": [],
            }
            for i in range(3)
        ]

        _ = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], insights)
        )
        high_confidence = await refactoring_engine.get_all_suggestions(
            min_confidence=0.85
        )

        assert all(s.confidence_score >= 0.85 for s in high_confidence)


class TestExportSuggestions:
    """Test exporting suggestions"""

    @pytest.mark.asyncio
    async def test_export_json_format(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test exporting suggestions as JSON"""
        _ = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )
        export = await refactoring_engine.export_suggestions(output_format="json")

        # Should be valid JSON
        data: object = json.loads(export)
        assert isinstance(data, list)
        data_list: list[dict[str, object]] = cast(list[dict[str, object]], data)
        assert len(data_list) > 0
        assert "suggestion_id" in data_list[0]

    @pytest.mark.asyncio
    async def test_export_markdown_format(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test exporting suggestions as Markdown"""
        _ = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )
        export = await refactoring_engine.export_suggestions(output_format="markdown")

        assert "# Refactoring Suggestions" in export
        assert "##" in export  # Suggestion headers
        assert "**ID:**" in export
        assert "**Type:**" in export

    @pytest.mark.asyncio
    async def test_export_text_format(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test exporting suggestions as text"""
        _ = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )
        export = await refactoring_engine.export_suggestions(output_format="text")

        assert "REFACTORING SUGGESTIONS" in export
        assert "===" in export
        assert "ID:" in export

    @pytest.mark.asyncio
    async def test_export_empty_suggestions(
        self, refactoring_engine: RefactoringEngine
    ):
        """Test exporting when no suggestions exist"""
        export_json = await refactoring_engine.export_suggestions(output_format="json")
        export_md = await refactoring_engine.export_suggestions(
            output_format="markdown"
        )
        export_text = await refactoring_engine.export_suggestions(output_format="text")

        assert export_json == "[]"
        assert "# Refactoring Suggestions" in export_md
        assert "REFACTORING SUGGESTIONS" in export_text


class TestClearSuggestions:
    """Test clearing suggestions"""

    @pytest.mark.asyncio
    async def test_clears_all_suggestions(
        self,
        refactoring_engine: RefactoringEngine,
        sample_insight: dict[str, str | float | list[str]],
    ):
        """Test that all suggestions are cleared"""
        _ = await refactoring_engine.generate_suggestions(
            insights=cast(list[dict[str, object]], [sample_insight])
        )
        assert len(refactoring_engine.suggestions) > 0

        await refactoring_engine.clear_suggestions()

        assert len(refactoring_engine.suggestions) == 0
        assert refactoring_engine.suggestion_counter == 0


class TestRefactoringSuggestionDataclass:
    """Test RefactoringSuggestion dataclass"""

    def test_to_dict_conversion(self):
        """Test converting suggestion to dictionary"""
        action = RefactoringAction(
            action_type="create",
            target_file="test.md",
            description="Test action",
            details={"key": "value"},
        )

        suggestion = RefactoringSuggestion(
            suggestion_id="TEST-001",
            refactoring_type=RefactoringType.CONSOLIDATION,
            priority=RefactoringPriority.HIGH,
            title="Test Suggestion",
            description="Test description",
            reasoning="Test reasoning",
            affected_files=["file1.md", "file2.md"],
            actions=[action],
            estimated_impact={"token_savings": 100},
            confidence_score=0.85,
            metadata={"source": "test"},
        )

        result = suggestion.to_dict()

        assert result["suggestion_id"] == "TEST-001"
        assert result["refactoring_type"] == "consolidation"
        assert result["priority"] == "high"
        assert result["title"] == "Test Suggestion"
        actions: object | None = result.get("actions")
        assert actions is not None
        assert isinstance(actions, list)
        actions_list: list[dict[str, object]] = cast(list[dict[str, object]], actions)
        assert len(actions_list) == 1
        assert isinstance(actions_list[0], dict)
        assert actions_list[0]["action_type"] == "create"
        assert result["confidence_score"] == 0.85

    def test_created_at_generated(self):
        """Test that created_at is automatically generated"""
        suggestion = RefactoringSuggestion(
            suggestion_id="TEST-001",
            refactoring_type=RefactoringType.CONSOLIDATION,
            priority=RefactoringPriority.HIGH,
            title="Test",
            description="Test",
            reasoning="Test",
            affected_files=[],
            actions=[],
            estimated_impact={},
            confidence_score=0.8,
        )

        assert suggestion.created_at is not None
        assert "T" in suggestion.created_at  # ISO format


class TestRefactoringAction:
    """Test RefactoringAction dataclass"""

    def test_action_with_defaults(self):
        """Test action with default details"""
        action = RefactoringAction(
            action_type="create", target_file="test.md", description="Test"
        )

        assert action.details == {}

    def test_action_with_details(self):
        """Test action with custom details"""
        details: dict[str, str | int] = {"key1": "value1", "key2": 42}
        action = RefactoringAction(
            action_type="modify",
            target_file="test.md",
            description="Test",
            details=cast(dict[str, object], details),
        )

        assert action.details == details
