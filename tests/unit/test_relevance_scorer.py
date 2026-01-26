"""
Unit tests for relevance_scorer module.

Tests relevance scoring for intelligent context selection.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.metadata_index import MetadataIndex
from cortex.optimization.models import FileMetadataForScoring
from cortex.optimization.relevance_scorer import RelevanceScorer


@pytest.fixture
def sample_dependency_graph() -> DependencyGraph:
    """Create a sample dependency graph."""
    graph = DependencyGraph()
    # DependencyGraph uses static dependencies, so we'll just return it
    # The tests will work with the static structure defined in the class
    return graph


@pytest.fixture
def sample_metadata_index(temp_project_root: Path) -> MetadataIndex:
    """Create a sample metadata index (sync version for simpler tests)."""
    return MetadataIndex(temp_project_root)


class TestRelevanceScorerInitialization:
    """Tests for RelevanceScorer initialization."""

    def test_initialization_with_default_weights(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test RelevanceScorer initializes with default weights."""
        # Arrange & Act
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)

        # Assert
        assert scorer is not None
        assert scorer.keyword_weight == 0.4
        assert scorer.dependency_weight == 0.3
        assert scorer.recency_weight == 0.2
        assert scorer.quality_weight == 0.1

    def test_initialization_with_custom_weights(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test RelevanceScorer initializes with custom weights."""
        # Arrange & Act
        scorer = RelevanceScorer(
            sample_dependency_graph,
            sample_metadata_index,
            keyword_weight=0.5,
            dependency_weight=0.25,
            recency_weight=0.15,
            quality_weight=0.1,
        )

        # Assert
        assert scorer.keyword_weight == 0.5
        assert scorer.dependency_weight == 0.25
        assert scorer.recency_weight == 0.15
        assert scorer.quality_weight == 0.1


class TestKeywordExtraction:
    """Tests for keyword extraction."""

    def test_extract_keywords_from_simple_text(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _extract_keywords extracts words from simple text."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        text = "Build authentication system for API"

        # Act
        keywords = scorer.extract_keywords(text)

        # Assert
        assert "build" in keywords
        assert "authentication" in keywords
        assert "system" in keywords
        assert "api" in keywords
        # Stop words should be filtered
        assert "for" not in keywords

    def test_extract_keywords_filters_stop_words(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _extract_keywords filters common stop words."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        text = "The quick fox and the lazy dog"

        # Act
        keywords = scorer.extract_keywords(text)

        # Assert
        assert "the" not in keywords
        assert "and" not in keywords
        assert "quick" in keywords
        assert "lazy" in keywords

    def test_extract_keywords_filters_short_words(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _extract_keywords filters words shorter than 3 characters."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        text = "Go to DB API"

        # Act
        keywords = scorer.extract_keywords(text)

        # Assert
        assert "go" not in keywords  # Too short
        assert "to" not in keywords  # Stop word
        assert "db" not in keywords  # Too short
        assert "api" in keywords  # 3 chars, kept

    def test_extract_keywords_preserves_order_and_uniqueness(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _extract_keywords maintains order and removes duplicates."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        text = "test system test api test"

        # Act
        keywords = scorer.extract_keywords(text)

        # Assert
        assert keywords == ["test", "system", "api"]  # Order preserved, no duplicates

    def test_extract_keywords_handles_hyphenated_words(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _extract_keywords handles hyphenated words."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        text = "memory-bank self-evolution"

        # Act
        keywords = scorer.extract_keywords(text)

        # Assert
        assert "memory-bank" in keywords
        assert "self-evolution" in keywords


class TestKeywordScoring:
    """Tests for keyword-based scoring."""

    def test_calculate_keyword_score_with_matches(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_keyword_score returns score for matching keywords."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        task_keywords = ["authentication", "system", "api"]
        content = "This file describes the authentication system for the API"

        # Act
        score = scorer.calculate_keyword_score(
            task_keywords,
            content,
        )
        # Assert
        assert 0.0 < score <= 1.0
        assert score > 0.5  # Good match should have high score

    def test_calculate_keyword_score_with_no_matches(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_keyword_score returns low score for no matches."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        task_keywords = ["database", "storage"]
        content = "This file talks about user interface and design patterns"

        # Act
        score = scorer.calculate_keyword_score(
            task_keywords,
            content,
        )
        # Assert
        assert score < 0.2  # No matches should have low score

    def test_calculate_keyword_score_with_empty_keywords(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_keyword_score returns 0 for empty keywords."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        content = "Some content here"

        # Act
        score = scorer.calculate_keyword_score(
            [],
            content,
        )
        # Assert
        assert score == 0.0

    def test_calculate_keyword_score_with_empty_content(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_keyword_score returns 0 for empty content."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        task_keywords = ["test", "keyword"]

        # Act
        score = scorer.calculate_keyword_score(
            task_keywords,
            "",
        )
        # Assert
        assert score == 0.0

    def test_calculate_keyword_score_case_insensitive(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_keyword_score is case-insensitive."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        task_keywords = ["authentication"]
        content_lower = "authentication system"
        content_upper = "AUTHENTICATION SYSTEM"

        # Act
        score_lower = scorer.calculate_keyword_score(
            task_keywords,
            content_lower,
        )
        score_upper = scorer.calculate_keyword_score(
            task_keywords,
            content_upper,
        )
        # Assert
        assert score_lower == score_upper


class TestDependencyScoring:
    """Tests for dependency-based scoring."""

    def test_calculate_dependency_scores_boosts_dependencies(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_dependency_scores boosts files that are dependencies."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        # Use real files from dependency graph: activeContext depends on productContext, systemPatterns, techContext
        keyword_scores = {
            "activeContext.md": 0.9,  # High score, has dependencies
            "productContext.md": 0.1,  # Low score, but dependency of activeContext
            "systemPatterns.md": 0.1,  # Low score, but dependency of activeContext
            "techContext.md": 0.1,  # Low score, but dependency of activeContext
        }

        # Act
        dependency_scores = scorer.calculate_dependency_scores(
            keyword_scores,
        )
        # Assert
        # productContext.md, systemPatterns.md, and techContext.md should be boosted
        # because activeContext.md depends on them (boost = 0.9 * 0.7 = 0.63)
        assert dependency_scores["productContext.md"] > 0.5
        assert dependency_scores["systemPatterns.md"] > 0.5
        assert dependency_scores["techContext.md"] > 0.5

    def test_calculate_dependency_scores_ignores_low_scores(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_dependency_scores ignores files with low scores."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        keyword_scores = {
            "file1.md": 0.2,  # Below 0.3 threshold
            "file2.md": 0.1,
            "file3.md": 0.1,
        }

        # Act
        dependency_scores = scorer.calculate_dependency_scores(
            keyword_scores,
        )
        # Assert
        # No boosting should occur
        assert all(score == 0.0 for score in dependency_scores.values())

    def test_calculate_dependency_scores_handles_empty_scores(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_dependency_scores handles empty scores dict."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)

        # Act
        dependency_scores = scorer.calculate_dependency_scores(
            {},
        )
        # Assert
        assert dependency_scores == {}


class TestRecencyScoring:
    """Tests for recency-based scoring."""

    def test_calculate_recency_score_for_recent_file(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_recency_score gives high score to recent files."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        metadata = FileMetadataForScoring(last_modified=datetime.now().isoformat())

        # Act
        score = scorer.calculate_recency_score(
            metadata,
        )
        # Assert
        assert score > 0.9  # Today's files should have high score

    def test_calculate_recency_score_for_old_file(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_recency_score gives low score to old files."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        old_date = (datetime.now() - timedelta(days=180)).isoformat()
        metadata = FileMetadataForScoring(last_modified=old_date)

        # Act
        score = scorer.calculate_recency_score(
            metadata,
        )
        # Assert
        assert score < 0.3  # Old files should have low score

    def test_calculate_recency_score_defaults_when_no_timestamp(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_recency_score returns 0.5 when no timestamp."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        metadata = FileMetadataForScoring()  # No last_modified

        # Act
        score = scorer.calculate_recency_score(
            metadata,
        )
        # Assert
        assert score == 0.5  # Neutral score

    def test_calculate_recency_score_handles_invalid_timestamp(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _calculate_recency_score handles invalid timestamp gracefully."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        metadata = FileMetadataForScoring(last_modified="invalid-date")

        # Act
        score = scorer.calculate_recency_score(
            metadata,
        )
        # Assert
        assert score == 0.5  # Default to neutral on error


class TestSectionParsing:
    """Tests for markdown section parsing."""

    def test_parse_sections_extracts_headings(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _parse_sections extracts markdown headings."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        content = """# Goals
Project goals here

## Architecture
Architecture details

### Implementation
Implementation notes"""

        # Act
        sections = scorer.parse_sections(
            content,
        )
        # Assert
        assert "Goals" in sections
        assert "Architecture" in sections
        assert "Implementation" in sections

    def test_parse_sections_captures_content(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _parse_sections captures section content."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        content = """# Section One
Content for section one

# Section Two
Content for section two"""

        # Act
        sections = scorer.parse_sections(
            content,
        )
        # Assert
        assert "Content for section one" in sections["Section One"]
        assert "Content for section two" in sections["Section Two"]

    def test_parse_sections_handles_preamble(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test _parse_sections captures content before first heading."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        content = """Preamble content here

# First Section
Section content"""

        # Act
        sections = scorer.parse_sections(
            content,
        )
        # Assert
        assert "preamble" in sections
        assert "Preamble content here" in sections["preamble"]


class TestFileScoring:
    """Tests for complete file scoring."""

    @pytest.mark.asyncio
    async def test_score_files_returns_empty_for_no_files(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test score_files returns empty dict for no files."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)

        # Act
        result = await scorer.score_files("task description", {}, {})

        # Assert
        assert result == {}

    @pytest.mark.asyncio
    async def test_score_files_includes_all_score_components(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test score_files returns all score components."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        files_content = {"test.md": "authentication system for API"}
        files_metadata = {
            "test.md": FileMetadataForScoring(last_modified=datetime.now().isoformat())
        }

        # Act
        result = await scorer.score_files(
            "build authentication system", files_content, files_metadata
        )

        # Assert
        assert "test.md" in result
        assert "total_score" in result["test.md"]
        assert "keyword_score" in result["test.md"]
        assert "dependency_score" in result["test.md"]
        assert "recency_score" in result["test.md"]
        assert "quality_score" in result["test.md"]
        assert "reason" in result["test.md"]

    @pytest.mark.asyncio
    async def test_score_files_combines_scores_with_weights(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test score_files combines scores using configured weights."""
        # Arrange
        scorer = RelevanceScorer(
            sample_dependency_graph,
            sample_metadata_index,
            keyword_weight=1.0,
            dependency_weight=0.0,
            recency_weight=0.0,
            quality_weight=0.0,
        )
        files_content = {"test.md": "test test test"}
        files_metadata = {"test.md": FileMetadataForScoring()}

        # Act
        result = await scorer.score_files("test", files_content, files_metadata)

        # Assert
        # With keyword_weight=1.0 and others=0, total should equal keyword_score
        assert result["test.md"]["total_score"] == result["test.md"]["keyword_score"]

    @pytest.mark.asyncio
    async def test_score_files_normalizes_quality_scores(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test score_files normalizes quality scores above 1.0."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        files_content = {"test.md": "content"}
        files_metadata = {"test.md": FileMetadataForScoring()}
        quality_scores = {"test.md": 150.0}  # Above 1.0, should be normalized

        # Act
        result = await scorer.score_files(
            "task",
            files_content,
            files_metadata,
            quality_scores,
        )

        # Assert
        quality_score = cast(float, result["test.md"]["quality_score"])
        assert 0.0 <= quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_score_files_generates_reason_for_high_scores(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test score_files generates descriptive reason for high scores."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        files_content = {
            "test.md": "authentication authentication authentication system api"
        }
        files_metadata = {
            "test.md": FileMetadataForScoring(last_modified=datetime.now().isoformat())
        }
        quality_scores = {"test.md": 0.9}

        # Act
        result = await scorer.score_files(
            "authentication system", files_content, files_metadata, quality_scores
        )

        # Assert
        reason = result["test.md"]["reason"]
        assert isinstance(reason, str)
        assert len(reason) > 0
        # Should mention high scoring components
        assert (
            "keyword" in reason.lower()
            or "quality" in reason.lower()
            or "recent" in reason.lower()
        )


class TestSectionScoring:
    """Tests for section-level scoring."""

    @pytest.mark.asyncio
    async def test_score_sections_returns_list_of_sections(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test score_sections returns list with section scores."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        content = """# Goals
Build authentication system

# Architecture
System design patterns"""

        # Act
        result = await scorer.score_sections(
            "authentication system", "test.md", content
        )

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert all("section" in item for item in result)
        assert all("score" in item for item in result)
        assert all("reason" in item for item in result)

    @pytest.mark.asyncio
    async def test_score_sections_sorts_by_score_descending(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test score_sections sorts results by score (highest first)."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        content = """# Low Score
Nothing relevant here

# High Score
authentication authentication system system api api"""

        # Act
        result = await scorer.score_sections(
            "authentication system api",
            "test.md",
            content,
        )

        # Assert
        first_score = cast(float, result[0]["score"])
        second_score = cast(float, result[1]["score"])
        assert first_score >= second_score
        assert result[0]["section"] == "High Score"

    @pytest.mark.asyncio
    async def test_score_sections_includes_matching_keywords_in_reason(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test score_sections mentions matching keywords in reason."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        content = """# Test Section
Contains keywords: authentication and api"""

        # Act
        result = await scorer.score_sections("authentication api", "test.md", content)

        # Assert
        reason = cast(str, result[0]["reason"])
        assert (
            "authentication" in reason or "api" in reason or "keyword" in reason.lower()
        )


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_handles_unicode_content(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test handles unicode characters in content."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        files_content = {"test.md": "系统认证 authentication système"}
        files_metadata = {"test.md": FileMetadataForScoring()}

        # Act
        result = await scorer.score_files(
            "authentication", files_content, files_metadata
        )

        # Assert
        assert "test.md" in result
        keyword_score = cast(float, result["test.md"]["keyword_score"])
        assert keyword_score > 0.0

    @pytest.mark.asyncio
    async def test_handles_very_long_content(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test handles very long file content."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        long_content = "word " * 10000 + "authentication"
        files_content = {"test.md": long_content}
        files_metadata = {"test.md": FileMetadataForScoring()}

        # Act
        result = await scorer.score_files(
            "authentication", files_content, files_metadata
        )

        # Assert
        assert "test.md" in result
        total_score = cast(float, result["test.md"]["total_score"])
        assert 0.0 <= total_score <= 1.0

    @pytest.mark.asyncio
    async def test_scores_are_always_between_zero_and_one(
        self,
        sample_dependency_graph: DependencyGraph,
        sample_metadata_index: MetadataIndex,
    ) -> None:
        """Test all scores are normalized to [0, 1] range."""
        # Arrange
        scorer = RelevanceScorer(sample_dependency_graph, sample_metadata_index)
        files_content = {"test.md": "test content here"}
        files_metadata = {
            "test.md": FileMetadataForScoring(last_modified=datetime.now().isoformat())
        }

        # Act
        result = await scorer.score_files("test", files_content, files_metadata)

        # Assert
        scores = result["test.md"]
        total_score = cast(float, scores["total_score"])
        keyword_score = cast(float, scores["keyword_score"])
        dependency_score = cast(float, scores["dependency_score"])
        recency_score = cast(float, scores["recency_score"])
        quality_score = cast(float, scores["quality_score"])

        assert 0.0 <= total_score <= 1.0
        assert 0.0 <= keyword_score <= 1.0
        assert 0.0 <= dependency_score <= 1.0
        assert 0.0 <= recency_score <= 1.0
        assert 0.0 <= quality_score <= 1.0
