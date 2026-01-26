"""
Tests for duplication_detector.py - Duplication detection for Memory Bank content.

Tests cover:
- Detector initialization with custom thresholds
- Scanning files for exact and similar duplicates
- Section comparison with similarity scoring
- Section extraction from markdown content
- Exact duplicate detection using content hashes
- Similar content detection with threshold filtering
- Content normalization for comparison
- Multiple similarity algorithms (SequenceMatcher, Jaccard)
- Refactoring suggestion generation
"""

from typing import cast

import pytest

from cortex.validation.duplication_detector import DuplicationDetector


@pytest.mark.unit
class TestDuplicationDetectorInitialization:
    """Tests for DuplicationDetector initialization."""

    @pytest.mark.asyncio
    async def test_initialization_with_defaults(self):
        """Test detector initializes with default values."""
        detector = DuplicationDetector()

        assert detector.threshold == 0.85
        assert detector.min_length == 50

    @pytest.mark.asyncio
    async def test_initialization_with_custom_values(self):
        """Test detector initializes with custom values."""
        detector = DuplicationDetector(
            similarity_threshold=0.90, min_content_length=100
        )

        assert detector.threshold == 0.90
        assert detector.min_length == 100


@pytest.mark.unit
class TestScanAllFiles:
    """Tests for scan_all_files method."""

    @pytest.mark.asyncio
    async def test_scan_files_with_exact_duplicates(self):
        """Test scanning files finds exact duplicates."""
        detector = DuplicationDetector()

        files = {
            "file1.md": """
## Section A
This is some content that will be duplicated exactly.
It has multiple lines to exceed the minimum length.
""",
            "file2.md": """
## Section B
This is some content that will be duplicated exactly.
It has multiple lines to exceed the minimum length.
""",
        }

        result = await detector.scan_all_files(files)

        duplicates_found = cast(int, result["duplicates_found"])
        assert duplicates_found > 0
        exact_duplicates = cast(list[dict[str, object]], result["exact_duplicates"])
        assert len(exact_duplicates) > 0

        # Check exact duplicate details
        exact = exact_duplicates[0]
        assert cast(float, exact["similarity"]) == 1.0
        assert cast(str, exact["type"]) == "exact"
        exact_str = str(exact)
        assert "file1" in exact_str or "file1.md" in exact_str

    @pytest.mark.asyncio
    async def test_scan_files_with_similar_content(self):
        """Test scanning files finds similar content."""
        detector = DuplicationDetector(similarity_threshold=0.70)

        files = {
            "file1.md": """
## Section A
This is some content about project goals and objectives.
We want to achieve several key milestones in the project.
""",
            "file2.md": """
## Section B
This is some content about project goals and objectives.
We want to reach several important milestones in the project.
""",
        }

        result = await detector.scan_all_files(files)

        duplicates_found = cast(int, result["duplicates_found"])
        assert duplicates_found > 0
        similar_content = cast(list[dict[str, object]], result["similar_content"])
        assert len(similar_content) > 0

        # Check similar content details
        similar = similar_content[0]
        similarity = cast(float, similar["similarity"])
        assert 0.70 <= similarity < 1.0
        assert cast(str, similar["type"]) == "similar"
        assert "suggestion" in similar

    @pytest.mark.asyncio
    async def test_scan_files_with_no_duplicates(self):
        """Test scanning files with completely different content."""
        detector = DuplicationDetector()

        files = {
            "file1.md": """
## Section A
This is completely unique content about architecture patterns.
""",
            "file2.md": """
## Section B
This is totally different content about testing strategies.
""",
        }

        result = await detector.scan_all_files(files)

        assert cast(int, result["duplicates_found"]) == 0
        exact_duplicates = cast(list[object], result["exact_duplicates"])
        similar_content = cast(list[object], result["similar_content"])
        assert len(exact_duplicates) == 0
        assert len(similar_content) == 0

    @pytest.mark.asyncio
    async def test_scan_files_with_short_sections(self):
        """Test scanning files ignores sections below minimum length."""
        detector = DuplicationDetector(min_content_length=100)

        files = {
            "file1.md": """
## Section A
Short content.
""",
            "file2.md": """
## Section B
Short content.
""",
        }

        result = await detector.scan_all_files(files)

        # Short sections should be ignored
        assert result["duplicates_found"] == 0

    @pytest.mark.asyncio
    async def test_scan_files_with_multiple_sections(self):
        """Test scanning files with multiple sections per file."""
        detector = DuplicationDetector(similarity_threshold=0.80)

        files = {
            "file1.md": """
## Section A
This is unique content in section A with enough text to be analyzed.

## Section B
This is duplicated content that appears in both files.
It has multiple lines to exceed the minimum length requirement.

## Section C
This is more unique content in section C with sufficient length.
""",
            "file2.md": """
## Section X
Different content in section X with enough length to analyze.

## Section Y
This is duplicated content that appears in both files.
It has multiple lines to exceed the minimum length requirement.
""",
        }

        result = await detector.scan_all_files(files)

        duplicates_found = result.get("duplicates_found")
        assert isinstance(duplicates_found, (int, float))
        assert duplicates_found > 0
        # Should find the duplicate Section B/Y but not the unique ones


@pytest.mark.unit
class TestCompareSections:
    """Tests for compare_sections method."""

    @pytest.mark.asyncio
    async def test_compare_identical_content(self):
        """Test comparing identical content returns 1.0."""
        detector = DuplicationDetector()

        content = "This is some test content with enough length for comparison."

        similarity = detector.compare_sections(content, content)

        assert similarity == 1.0

    @pytest.mark.asyncio
    async def test_compare_similar_content(self):
        """Test comparing similar content returns high score."""
        detector = DuplicationDetector()

        content1 = "This is some test content about project goals and objectives."
        content2 = "This is some test content about project goals and targets."

        similarity = detector.compare_sections(content1, content2)

        assert 0.8 <= similarity < 1.0

    @pytest.mark.asyncio
    async def test_compare_different_content(self):
        """Test comparing different content returns low score."""
        detector = DuplicationDetector()

        content1 = "This is about architecture patterns and system design principles."
        content2 = "Completely unrelated text about user interface testing strategies."

        similarity = detector.compare_sections(content1, content2)

        assert similarity < 0.5

    @pytest.mark.asyncio
    async def test_compare_content_too_short(self):
        """Test comparing content below minimum length returns 0.0."""
        detector = DuplicationDetector(min_content_length=100)

        content1 = "Short text."
        content2 = "Short text."

        similarity = detector.compare_sections(content1, content2)

        assert similarity == 0.0

    @pytest.mark.asyncio
    async def test_compare_case_insensitive(self):
        """Test comparison is case-insensitive."""
        detector = DuplicationDetector()

        content1 = "THIS IS SOME TEST CONTENT WITH ENOUGH LENGTH FOR COMPARISON."
        content2 = "this is some test content with enough length for comparison."

        similarity = detector.compare_sections(content1, content2)

        assert similarity == 1.0


@pytest.mark.unit
class TestExtractSections:
    """Tests for extract_sections method."""

    @pytest.mark.asyncio
    async def test_extract_sections_from_content(self):
        """Test extracting sections from markdown content."""
        detector = DuplicationDetector(
            min_content_length=10
        )  # Lower threshold for this test

        content = """
# Main Title

## Section One
Content for section one with enough length to be included.

## Section Two
Content for section two with enough length to be included.

### Subsection
Subsection content.

## Section Three
Content for section three with enough length to be included.
"""

        sections = detector.extract_sections(content)

        assert len(sections) >= 3
        section_names = [name for name, _ in sections]
        assert "Section One" in section_names
        assert "Section Two" in section_names
        assert "Section Three" in section_names

    @pytest.mark.asyncio
    async def test_extract_sections_filters_short_content(self):
        """Test extracting sections filters out content below minimum."""
        detector = DuplicationDetector(min_content_length=100)

        content = """
## Section A
Short content.

## Section B
This section has much longer content that exceeds the minimum length requirement for duplication detection.
"""

        sections = detector.extract_sections(content)

        assert len(sections) == 1
        assert sections[0][0] == "Section B"

    @pytest.mark.asyncio
    async def test_extract_sections_with_no_sections(self):
        """Test extracting sections from content with no headings."""
        detector = DuplicationDetector()

        content = "Just some plain text without any section headings."

        sections = detector.extract_sections(content)

        assert len(sections) == 0

    @pytest.mark.asyncio
    async def test_extract_sections_preserves_content(self):
        """Test extracting sections preserves section content."""
        detector = DuplicationDetector()

        content = """
## Test Section
Line one of content.
Line two of content.
Line three of content.
"""

        sections = detector.extract_sections(content)

        assert len(sections) == 1
        name, text = sections[0]
        assert name == "Test Section"
        assert "Line one" in text
        assert "Line two" in text
        assert "Line three" in text


@pytest.mark.unit
class TestFindExactDuplicates:
    """Tests for find_exact_duplicates method."""

    @pytest.mark.asyncio
    async def test_find_exact_duplicates_with_matches(self):
        """Test finding exact duplicates returns matches."""
        detector = DuplicationDetector()

        duplicate_content = (
            "This is duplicate content with enough length for detection."
        )

        all_sections = {
            "file1.md": [("Section A", duplicate_content)],
            "file2.md": [("Section B", duplicate_content)],
        }

        duplicates = detector.find_exact_duplicates(all_sections)

        assert len(duplicates) > 0
        dup = duplicates[0]
        assert dup["similarity"] == 1.0
        assert dup["type"] == "exact"
        assert "file1.md" in [dup["file1"], dup["file2"]]

    @pytest.mark.asyncio
    async def test_find_exact_duplicates_with_no_matches(self):
        """Test finding exact duplicates with no matches."""
        detector = DuplicationDetector()

        all_sections = {
            "file1.md": [("Section A", "Unique content for section A.")],
            "file2.md": [("Section B", "Different content for section B.")],
        }

        duplicates = detector.find_exact_duplicates(all_sections)

        assert len(duplicates) == 0

    @pytest.mark.asyncio
    async def test_find_exact_duplicates_multiple_files(self):
        """Test finding exact duplicates across multiple files."""
        detector = DuplicationDetector()

        duplicate_content = "This is duplicate content appearing in three files."

        all_sections = {
            "file1.md": [("Section A", duplicate_content)],
            "file2.md": [("Section B", duplicate_content)],
            "file3.md": [("Section C", duplicate_content)],
        }

        duplicates = detector.find_exact_duplicates(all_sections)

        # Should find 3 pairs: (1,2), (1,3), (2,3)
        assert len(duplicates) == 3

    @pytest.mark.asyncio
    async def test_find_exact_duplicates_generates_suggestions(self):
        """Test exact duplicates include refactoring suggestions."""
        detector = DuplicationDetector()

        duplicate_content = "This is duplicate content with enough length."

        all_sections = {
            "file1.md": [("Section A", duplicate_content)],
            "file2.md": [("Section B", duplicate_content)],
        }

        duplicates = detector.find_exact_duplicates(all_sections)

        assert len(duplicates) > 0
        first_dup = duplicates[0]
        assert "include:" in first_dup.suggestion


@pytest.mark.unit
class TestFindSimilarContent:
    """Tests for find_similar_content method."""

    @pytest.mark.asyncio
    async def test_find_similar_content_above_threshold(self):
        """Test finding similar content above threshold."""
        detector = DuplicationDetector(similarity_threshold=0.70)

        all_sections = {
            "file1.md": [
                (
                    "Section A",
                    "This is content about project goals and objectives for the team.",
                )
            ],
            "file2.md": [
                (
                    "Section B",
                    "This is content about project goals and targets for the team.",
                )
            ],
        }

        similar = detector.find_similar_content(all_sections)

        assert len(similar) > 0
        assert similar[0]["type"] == "similar"
        similarity_score = cast(float, similar[0]["similarity"])
        assert 0.70 <= similarity_score < 1.0

    @pytest.mark.asyncio
    async def test_find_similar_content_below_threshold(self):
        """Test finding similar content filters below threshold."""
        detector = DuplicationDetector(similarity_threshold=0.90)

        all_sections = {
            "file1.md": [
                (
                    "Section A",
                    "This is content about architecture patterns and design principles.",
                )
            ],
            "file2.md": [
                (
                    "Section B",
                    "This is content about testing strategies and quality assurance.",
                )
            ],
        }

        similar = detector.find_similar_content(all_sections)

        assert len(similar) == 0

    @pytest.mark.asyncio
    async def test_find_similar_content_skips_same_file(self):
        """Test similar content detection skips same-file comparisons."""
        detector = DuplicationDetector()

        all_sections = {
            "file1.md": [
                ("Section A", "Content about architecture patterns and design."),
                ("Section B", "Content about architecture patterns and design."),
            ]
        }

        similar = detector.find_similar_content(all_sections)

        # Should not find duplicates within same file
        assert len(similar) == 0

    @pytest.mark.asyncio
    async def test_find_similar_content_sorts_by_similarity(self):
        """Test similar content is sorted by similarity score."""
        detector = DuplicationDetector(similarity_threshold=0.60)

        all_sections = {
            "file1.md": [
                (
                    "Section A",
                    "Content about architecture and design patterns for systems.",
                )
            ],
            "file2.md": [
                (
                    "Section B",
                    "Content about architecture and design patterns for systems also.",
                )
            ],
            "file3.md": [
                ("Section C", "Content about testing and quality assurance strategies.")
            ],
        }

        similar = detector.find_similar_content(all_sections)

        # Results should be sorted by similarity (highest first)
        if len(similar) > 1:
            for i in range(len(similar) - 1):
                similarity1 = cast(float, similar[i]["similarity"])
                similarity2 = cast(float, similar[i + 1]["similarity"])
                assert similarity1 >= similarity2


@pytest.mark.unit
class TestNormalizeContent:
    """Tests for normalize_content method."""

    @pytest.mark.asyncio
    async def test_normalize_content_lowercase(self):
        """Test normalization converts to lowercase."""
        detector = DuplicationDetector()

        result = detector.normalize_content("THIS IS UPPERCASE TEXT")

        assert result == "this is uppercase text"

    @pytest.mark.asyncio
    async def test_normalize_content_whitespace(self):
        """Test normalization removes extra whitespace."""
        detector = DuplicationDetector()

        result = detector.normalize_content("Text  with   extra    spaces")

        assert "  " not in result
        assert result == "text with extra spaces"

    @pytest.mark.asyncio
    async def test_normalize_content_punctuation(self):
        """Test normalization removes punctuation."""
        detector = DuplicationDetector()

        result = detector.normalize_content("Text, with: punctuation! marks?")

        assert "," not in result
        assert ":" not in result
        assert "!" not in result
        assert "?" not in result

    @pytest.mark.asyncio
    async def test_normalize_content_preserves_meaningful_chars(self):
        """Test normalization preserves word characters and hyphens."""
        detector = DuplicationDetector()

        result = detector.normalize_content("test-word and word_here")

        assert "test-word" in result or "testword" in result
        assert "word" in result


@pytest.mark.unit
class TestCalculateSimilarity:
    """Tests for calculate_similarity method."""

    @pytest.mark.asyncio
    async def test_calculate_similarity_identical(self):
        """Test similarity calculation for identical text."""
        detector = DuplicationDetector()

        text = "this is test text for similarity calculation"

        similarity = detector.calculate_similarity(text, text)

        assert similarity == 1.0

    @pytest.mark.asyncio
    async def test_calculate_similarity_different(self):
        """Test similarity calculation for different text."""
        detector = DuplicationDetector()

        text1 = "completely different text about architecture"
        text2 = "totally unrelated content about testing"

        similarity = detector.calculate_similarity(text1, text2)

        assert 0.0 <= similarity < 0.5

    @pytest.mark.asyncio
    async def test_calculate_similarity_uses_multiple_algorithms(self):
        """Test similarity calculation averages multiple algorithms."""
        detector = DuplicationDetector()

        text1 = "test content with some words"
        text2 = "test content with different words"

        similarity = detector.calculate_similarity(text1, text2)

        # Should be between 0 and 1
        assert 0.0 <= similarity <= 1.0


@pytest.mark.unit
class TestJaccardSimilarity:
    """Tests for jaccard_similarity method."""

    @pytest.mark.asyncio
    async def test_jaccard_similarity_identical(self):
        """Test Jaccard similarity for identical text."""
        detector = DuplicationDetector()

        text = "test content for similarity"

        similarity = detector.jaccard_similarity(text, text)

        assert similarity == 1.0

    @pytest.mark.asyncio
    async def test_jaccard_similarity_no_overlap(self):
        """Test Jaccard similarity with no word overlap."""
        detector = DuplicationDetector()

        text1 = "architecture design patterns"
        text2 = "testing quality assurance"

        similarity = detector.jaccard_similarity(text1, text2)

        assert similarity == 0.0

    @pytest.mark.asyncio
    async def test_jaccard_similarity_partial_overlap(self):
        """Test Jaccard similarity with partial overlap."""
        detector = DuplicationDetector()

        text1 = "test content about architecture"
        text2 = "test content about testing"

        similarity = detector.jaccard_similarity(text1, text2)

        assert 0.0 < similarity < 1.0

    @pytest.mark.asyncio
    async def test_jaccard_similarity_empty_text(self):
        """Test Jaccard similarity with empty text."""
        detector = DuplicationDetector()

        # Both empty
        similarity = detector.jaccard_similarity("", "")
        assert similarity == 1.0

        # One empty
        similarity = detector.jaccard_similarity("test", "")
        assert similarity == 0.0


@pytest.mark.unit
class TestGenerateRefactoringSuggestion:
    """Tests for generate_refactoring_suggestion method."""

    @pytest.mark.asyncio
    async def test_generate_suggestion_format(self):
        """Test refactoring suggestion has correct format."""
        detector = DuplicationDetector()

        suggestion = detector.generate_refactoring_suggestion(
            "file1.md", "Section A", "file2.md", "Section B"
        )

        assert "include:" in suggestion
        assert "Section" in suggestion
        assert ".md" in suggestion

    @pytest.mark.asyncio
    async def test_generate_suggestion_hierarchy_order(self):
        """Test suggestion respects file hierarchy."""
        detector = DuplicationDetector()

        # projectBrief comes before activeContext in hierarchy
        suggestion = detector.generate_refactoring_suggestion(
            "activeContext.md", "Section A", "projectBrief.md", "Section B"
        )

        # Should suggest including from projectBrief (earlier in hierarchy)
        assert "projectBrief.md" in suggestion

    @pytest.mark.asyncio
    async def test_generate_suggestion_unknown_files(self):
        """Test suggestion for files not in standard hierarchy."""
        detector = DuplicationDetector()

        suggestion = detector.generate_refactoring_suggestion(
            "custom1.md", "Section A", "custom2.md", "Section B"
        )

        # Should still generate a valid suggestion
        assert "include:" in suggestion
        assert "custom" in suggestion.lower()


@pytest.mark.unit
class TestDuplicationDetectorIntegration:
    """Integration tests for DuplicationDetector."""

    @pytest.mark.asyncio
    async def test_complete_duplication_scan_workflow(self):
        """Test complete duplication detection workflow."""
        detector = DuplicationDetector(similarity_threshold=0.75)

        files = {
            "projectBrief.md": """
# Project Brief

## Project Overview
This project aims to build a comprehensive memory management system
for AI assistants to maintain context across conversations.

## Goals
- Maintain conversation history efficiently
- Enable quick context retrieval
- Support multiple file formats
""",
            "activeContext.md": """
# Active Context

## Current Focus
This project aims to build a comprehensive memory management system
for AI assistants to maintain context across conversations.

## Recent Changes
Updated the context loading mechanism to improve performance.
""",
            "techContext.md": """
# Technical Context

## Technology Stack
Built using Python with async/await patterns for file I/O.

## Dependencies
Core dependencies include tiktoken for token counting.
""",
        }

        result = await detector.scan_all_files(files)

        # Should find duplicates between projectBrief and activeContext
        duplicates_found = result.get("duplicates_found")
        assert isinstance(duplicates_found, (int, float))
        assert duplicates_found > 0

        # Verify result structure
        assert "exact_duplicates" in result
        assert "similar_content" in result

        # Check that suggestions are generated
        exact_dups = cast(list[dict[str, object]], result["exact_duplicates"])
        similar_dups = cast(list[dict[str, object]], result["similar_content"])
        all_duplicates = exact_dups + similar_dups
        for dup in all_duplicates:
            assert "suggestion" in dup
            assert "file1" in dup
            assert "file2" in dup
            assert "similarity" in dup

    @pytest.mark.asyncio
    async def test_threshold_affects_results(self):
        """Test that threshold affects number of duplicates found."""
        content1 = (
            "Content about project goals and objectives for the development team."
        )
        content2 = "Content about project goals and targets for the development team."

        files = {
            "file1.md": f"## Section\n{content1}",
            "file2.md": f"## Section\n{content2}",
        }

        # High threshold - fewer matches
        strict_detector = DuplicationDetector(similarity_threshold=0.95)
        strict_result = await strict_detector.scan_all_files(files)

        # Low threshold - more matches
        lenient_detector = DuplicationDetector(similarity_threshold=0.70)
        lenient_result = await lenient_detector.scan_all_files(files)

        # Lenient detector should find more or equal duplicates
        lenient_count = cast(int, lenient_result["duplicates_found"])
        strict_count = cast(int, strict_result["duplicates_found"])
        assert lenient_count >= strict_count
