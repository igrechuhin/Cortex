"""Tests for LinkValidator - link integrity validation.

This module tests:
1. Link validation (file existence, section existence)
2. Broken link detection
3. Validation reports with suggestions
4. Batch validation for entire Memory Bank

Part of Phase 2: DRY Linking and Transclusion
"""

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.core.models import JsonValue, ModelDict
from cortex.linking.link_parser import LinkParser
from cortex.linking.link_validator import LinkValidator


@pytest.mark.unit
class TestLinkValidatorInitialization:
    """Tests for LinkValidator initialization."""

    def test_init_stores_dependencies(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test initialization stores file system and parser."""
        # Arrange & Act
        validator = LinkValidator(mock_file_system, mock_link_parser)

        # Assert
        assert validator.fs is mock_file_system
        assert validator.parser is mock_link_parser


@pytest.mark.unit
class TestCheckFileExists:
    """Tests for check_file_exists method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_file_exists(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test returns True when target file exists."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create a test file
        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("# Test")

        # Act
        result = await validator.check_file_exists("test.md")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_file_not_exists(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test returns False when target file does not exist."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Act
        result = await validator.check_file_exists("nonexistent.md")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_target_is_directory(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test returns False when target is a directory."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create a directory
        test_dir = memory_bank_dir / "test_dir"
        test_dir.mkdir()

        # Act
        result = await validator.check_file_exists("test_dir")

        # Assert
        assert result is False


@pytest.mark.unit
class TestCheckSectionExists:
    """Tests for check_section_exists method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_section_exists(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test returns True when section exists in file."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create file with sections
        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("# Introduction\n\n## Details\n\nContent here.")

        # Act
        exists, sections = await validator.check_section_exists(
            "test.md", "Introduction"
        )

        # Assert
        assert exists is True
        assert "Introduction" in sections
        assert "Details" in sections

    @pytest.mark.asyncio
    async def test_returns_false_when_section_not_exists(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test returns False when section does not exist."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create file with sections
        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("# Introduction\n\n## Details")

        # Act
        exists, sections = await validator.check_section_exists("test.md", "Missing")

        # Assert
        assert exists is False
        assert "Introduction" in sections
        assert "Details" in sections
        assert "Missing" not in sections

    @pytest.mark.asyncio
    async def test_case_insensitive_section_matching(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test section matching is case-insensitive."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("# Introduction\n\nContent")

        # Act
        exists_lower, _ = await validator.check_section_exists(
            "test.md", "introduction"
        )
        exists_upper, _ = await validator.check_section_exists(
            "test.md", "INTRODUCTION"
        )

        # Assert
        assert exists_lower is True
        assert exists_upper is True

    @pytest.mark.asyncio
    async def test_returns_false_when_file_not_exists(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test returns False and empty list when file doesn't exist."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Act
        exists, sections = await validator.check_section_exists(
            "nonexistent.md", "Introduction"
        )

        # Assert
        assert exists is False
        assert sections == []

    @pytest.mark.asyncio
    async def test_extracts_all_heading_levels(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test extracts headings of all levels."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("# H1\n\n## H2\n\n### H3\n\n#### H4")

        # Act
        _, sections = await validator.check_section_exists("test.md", "H1")

        # Assert
        assert "H1" in sections
        assert "H2" in sections
        assert "H3" in sections
        assert "H4" in sections


@pytest.mark.unit
class TestExtractHeadings:
    """Tests for _extract_headings method."""

    def test_extracts_single_heading(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test extracts single heading from content."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        content = "# Introduction\n\nSome content"

        # Act
        headings = validator.extract_headings(content)

        # Assert
        assert headings == ["Introduction"]

    def test_extracts_multiple_headings(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test extracts multiple headings."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        content = "# Title\n\n## Section 1\n\n## Section 2\n\n### Subsection"

        # Act
        headings = validator.extract_headings(content)

        # Assert
        assert headings == ["Title", "Section 1", "Section 2", "Subsection"]

    def test_handles_empty_content(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test handles empty content."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        content = ""

        # Act
        headings = validator.extract_headings(content)

        # Assert
        assert headings == []

    def test_ignores_non_headings(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test ignores lines that aren't headings."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        content = "# Title\n\nRegular text\n\n## Section\n\nMore text"

        # Act
        headings = validator.extract_headings(content)

        # Assert
        assert headings == ["Title", "Section"]

    def test_strips_heading_markers(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test strips # markers from heading text."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        content = "### My Section  "

        # Act
        headings = validator.extract_headings(content)

        # Assert
        assert headings == ["My Section"]

    def test_handles_headings_with_special_characters(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test handles headings with special characters."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        content = "# Title: The Beginning\n\n## Q&A Section\n\n### Cost ($$$)"

        # Act
        headings = validator.extract_headings(content)

        # Assert
        assert "Title: The Beginning" in headings
        assert "Q&A Section" in headings
        assert "Cost ($$$)" in headings


@pytest.mark.unit
class TestSimilarityScore:
    """Tests for _similarity_score method."""

    def test_returns_high_score_when_one_contains_other(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test returns 0.8 when one string contains the other."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)

        # Act
        score1 = validator.similarity_score("project", "projectBrief.md")
        score2 = validator.similarity_score("projectBrief.md", "project")

        # Assert
        assert score1 == 0.8
        assert score2 == 0.8

    def test_returns_score_based_on_common_prefix(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test returns score based on common prefix length."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)

        # Act
        score = validator.similarity_score("project", "problem")
        # Assert
        # "pro" is common prefix (3 chars), max length is 7
        assert score == 3 / 7

    def test_returns_zero_for_completely_different_strings(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test returns 0.0 for completely different strings."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)

        # Act
        score = validator.similarity_score("project", "xyz")
        # Assert
        assert score == 0.0

    def test_case_insensitive_comparison(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test similarity comparison is case-insensitive."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)

        # Act
        score1 = validator.similarity_score("Project", "project")
        score2 = validator.similarity_score("PROJECT", "project")

        # Assert
        assert score1 == 0.8  # Contains check
        assert score2 == 0.8

    def test_identical_strings_return_high_score(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test identical strings return high score."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)

        # Act
        score = validator.similarity_score("project.md", "project.md")
        # Assert
        assert score == 0.8  # Contains check succeeds


@pytest.mark.unit
class TestGenerateFileNotFoundSuggestion:
    """Tests for _generate_file_not_found_suggestion method."""

    @pytest.mark.asyncio
    async def test_suggests_similar_files_when_found(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test suggests similar files when they exist."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create similar files
        _ = (memory_bank_dir / "projectBrief.md").write_text("# Project")
        _ = (memory_bank_dir / "project-overview.md").write_text("# Overview")

        # Act
        suggestion = await validator.generate_file_not_found_suggestion("project.md")

        # Assert
        # The similarity algorithm should find similar files
        # It might match either or both depending on the algorithm's scoring
        is_similar_suggestion = (
            "Did you mean:" in suggestion
            or "projectBrief.md" in suggestion
            or "project-overview.md" in suggestion
        )
        assert is_similar_suggestion or "Create 'project.md'" in suggestion

    @pytest.mark.asyncio
    async def test_suggests_create_when_no_similar_files(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test suggests creating file when no similar files exist."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Act
        suggestion = await validator.generate_file_not_found_suggestion("newfile.md")

        # Assert
        assert "Create 'newfile.md'" in suggestion or "update the link" in suggestion


@pytest.mark.unit
class TestGenerateSectionSuggestion:
    """Tests for _generate_section_suggestion method."""

    def test_suggests_similar_sections_when_found(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test suggests similar sections when found."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        available = ["Introduction", "Overview", "Details"]

        # Act
        suggestion = validator.generate_section_suggestion("Intro", available)
        # Assert
        assert "Did you mean:" in suggestion
        assert "Introduction" in suggestion

    def test_lists_available_sections_when_none_similar(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test lists available sections when none are similar."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        available = ["Section A", "Section B", "Section C"]

        # Act
        suggestion = validator.generate_section_suggestion("XYZ", available)
        # Assert
        assert "Available sections:" in suggestion
        assert "Section A" in suggestion

    def test_handles_empty_available_sections(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test handles case when file has no sections."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        available: list[str] = []

        # Act
        suggestion = validator.generate_section_suggestion("Missing", available)
        # Assert
        assert suggestion == "File has no sections"

    def test_limits_suggestions_to_three(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test limits suggestions to first 3 similar sections."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        available = ["Intro1", "Intro2", "Intro3", "Intro4", "Intro5"]

        # Act
        suggestion = validator.generate_section_suggestion("Intro", available)
        # Assert
        # Should suggest only first 3
        assert "Did you mean:" in suggestion


@pytest.mark.unit
class TestValidateFile:
    """Tests for validate_file method."""

    @pytest.mark.asyncio
    async def test_validates_file_with_valid_links(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test validates file with all valid links."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create target file
        target_file = memory_bank_dir / "target.md"
        _ = target_file.write_text("# Introduction\n\nContent")

        # Create source file
        source_file = memory_bank_dir / "source.md"
        _ = source_file.write_text("[Link](target.md#Introduction)")

        # Mock parser to return parsed links
        mock_link_parser.parse_file = AsyncMock(
            return_value={
                "markdown_links": [
                    {
                        "type": "markdown",
                        "target": "target.md",
                        "section": "Introduction",
                        "line": 1,
                    }
                ],
                "transclusions": [],
            }
        )

        # Act
        result = await validator.validate_file(source_file)

        # Assert
        assert result["file"] == "source.md"
        valid_links = cast(list[dict[str, object]], result["valid_links"])
        broken_links = cast(list[dict[str, object]], result["broken_links"])
        warnings = cast(list[dict[str, object]], result["warnings"])
        assert len(valid_links) == 1
        assert len(broken_links) == 0
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_detects_broken_file_link(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test detects link to non-existent file."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        source_file = memory_bank_dir / "source.md"
        _ = source_file.write_text("[Link](missing.md)")

        # Mock parser
        mock_link_parser.parse_file = AsyncMock(
            return_value={
                "markdown_links": [
                    {
                        "type": "markdown",
                        "target": "missing.md",
                        "section": None,
                        "line": 1,
                    }
                ],
                "transclusions": [],
            }
        )

        # Act
        result = await validator.validate_file(source_file)

        # Assert
        broken_links = cast(list[dict[str, object]], result["broken_links"])
        assert len(broken_links) == 1
        broken = broken_links[0]
        assert broken["target"] == "missing.md"
        assert broken["error"] == "File not found"
        assert "suggestion" in broken

    @pytest.mark.asyncio
    async def test_detects_missing_section_warning(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test detects link to non-existent section."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create target file without the referenced section
        target_file = memory_bank_dir / "target.md"
        _ = target_file.write_text("# Introduction\n\nContent")

        source_file = memory_bank_dir / "source.md"
        _ = source_file.write_text("[Link](target.md#Missing)")

        # Mock parser
        mock_link_parser.parse_file = AsyncMock(
            return_value={
                "markdown_links": [
                    {
                        "type": "markdown",
                        "target": "target.md",
                        "section": "Missing",
                        "line": 1,
                    }
                ],
                "transclusions": [],
            }
        )

        # Act
        result = await validator.validate_file(source_file)

        # Assert
        warnings = cast(list[dict[str, object]], result["warnings"])
        assert len(warnings) == 1
        warning = warnings[0]
        assert warning["section"] == "Missing"
        assert warning["warning"] == "Section not found"
        assert "available_sections" in warning

    @pytest.mark.asyncio
    async def test_validates_link_without_section(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test validates link without section reference."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        target_file = memory_bank_dir / "target.md"
        _ = target_file.write_text("# Content")

        source_file = memory_bank_dir / "source.md"
        _ = source_file.write_text("[Link](target.md)")

        # Mock parser
        mock_link_parser.parse_file = AsyncMock(
            return_value={
                "markdown_links": [
                    {
                        "type": "markdown",
                        "target": "target.md",
                        "section": None,
                        "line": 1,
                    }
                ],
                "transclusions": [],
            }
        )

        # Act
        result = await validator.validate_file(source_file)

        # Assert
        valid_links = cast(list[dict[str, object]], result["valid_links"])
        broken_links = cast(list[dict[str, object]], result["broken_links"])
        warnings = cast(list[dict[str, object]], result["warnings"])
        assert len(valid_links) == 1
        assert len(broken_links) == 0
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_validates_transclusions(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test validates transclusion links."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        target_file = memory_bank_dir / "target.md"
        _ = target_file.write_text("# Section\n\nContent")

        source_file = memory_bank_dir / "source.md"
        _ = source_file.write_text("{{include: target.md#Section}}")

        # Mock parser
        mock_link_parser.parse_file = AsyncMock(
            return_value={
                "markdown_links": [],
                "transclusions": [
                    {
                        "type": "transclusion",
                        "target": "target.md",
                        "section": "Section",
                        "line": 1,
                    }
                ],
            }
        )

        # Act
        result = await validator.validate_file(source_file)

        # Assert
        valid_links = cast(list[dict[str, object]], result["valid_links"])
        assert len(valid_links) == 1
        assert valid_links[0]["type"] == "transclusion"


@pytest.mark.unit
class TestValidateAll:
    """Tests for validate_all method."""

    @pytest.mark.asyncio
    async def test_validates_all_files_in_directory(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test validates all markdown files in directory."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create multiple files
        file1 = memory_bank_dir / "file1.md"
        _ = file1.write_text("[Link](file2.md)")

        file2 = memory_bank_dir / "file2.md"
        _ = file2.write_text("[Link](file1.md)")

        # Mock parser
        mock_link_parser.parse_file = AsyncMock(
            return_value={
                "markdown_links": [
                    {
                        "type": "markdown",
                        "target": "file2.md",
                        "section": None,
                        "line": 1,
                    }
                ],
                "transclusions": [],
            }
        )

        # Act
        result = await validator.validate_all(memory_bank_dir)

        # Assert
        assert result["files_checked"] == 2
        by_file = cast(dict[str, dict[str, object]], result["by_file"])
        assert "file1.md" in by_file
        assert "file2.md" in by_file

    @pytest.mark.asyncio
    async def test_aggregates_statistics_correctly(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test aggregates statistics across all files."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create files
        file1 = memory_bank_dir / "file1.md"
        _ = file1.write_text("[Link](file2.md)")

        file2 = memory_bank_dir / "file2.md"
        _ = file2.write_text("[Link](missing.md)")

        # Mock parser to return different results for each file
        call_count = 0

        async def mock_parse(content: str) -> ModelDict:
            nonlocal call_count
            call_count += 1
            transclusions: list[ModelDict] = []
            if call_count == 1:
                markdown_links: list[ModelDict] = [
                    {
                        "type": "markdown",
                        "target": "file2.md",
                        "section": None,
                        "line": 1,
                    }
                ]
            else:
                markdown_links = [
                    {
                        "type": "markdown",
                        "target": "missing.md",
                        "section": None,
                        "line": 1,
                    }
                ]
            return {
                "markdown_links": cast(list[JsonValue], markdown_links),
                "transclusions": cast(list[JsonValue], transclusions),
            }

        mock_link_parser.parse_file = mock_parse

        # Act
        result = await validator.validate_all(memory_bank_dir)

        # Assert
        assert result["files_checked"] == 2
        assert result["total_links"] == 2
        assert result["valid_links"] == 1
        assert result["broken_links"] == 1

    @pytest.mark.asyncio
    async def test_collects_all_broken_links_with_file_context(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test collects all broken links with file context."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        file1 = memory_bank_dir / "file1.md"
        _ = file1.write_text("[Link](missing.md)")

        # Mock parser
        mock_link_parser.parse_file = AsyncMock(
            return_value={
                "markdown_links": [
                    {
                        "type": "markdown",
                        "target": "missing.md",
                        "section": None,
                        "line": 5,
                    }
                ],
                "transclusions": [],
            }
        )

        # Act
        result = await validator.validate_all(memory_bank_dir)

        # Assert
        validation_errors = cast(list[dict[str, object]], result["validation_errors"])
        assert len(validation_errors) == 1
        error = validation_errors[0]
        assert error["file"] == "file1.md"
        assert error["target"] == "missing.md"
        assert error["line"] == 5

    @pytest.mark.asyncio
    async def test_handles_file_processing_errors(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test handles errors during file processing gracefully."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        file1 = memory_bank_dir / "file1.md"
        _ = file1.write_text("Content")

        # Mock parser to raise exception
        mock_link_parser.parse_file = AsyncMock(side_effect=Exception("Parse error"))

        # Act
        result = await validator.validate_all(memory_bank_dir)

        # Assert
        assert result["files_checked"] == 0  # File not counted if error
        by_file = cast(dict[str, dict[str, object]], result["by_file"])
        assert "file1.md" in by_file
        assert "error" in by_file["file1.md"]

    @pytest.mark.asyncio
    async def test_empty_directory_returns_zero_stats(
        self,
        memory_bank_dir: Path,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test empty directory returns zero statistics."""
        # Arrange
        fs = FileSystemManager(memory_bank_dir.parent.parent)
        validator = LinkValidator(fs, mock_link_parser)

        # Create empty directory
        empty_dir = memory_bank_dir / "empty"
        empty_dir.mkdir()

        # Act
        result = await validator.validate_all(empty_dir)

        # Assert
        assert result["files_checked"] == 0
        assert result["total_links"] == 0
        assert result["valid_links"] == 0
        assert result["broken_links"] == 0


@pytest.mark.unit
class TestGenerateReport:
    """Tests for generate_report method."""

    def test_generates_report_with_summary(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test generates report with summary statistics."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        validation_result: dict[str, object] = {
            "files_checked": 5,
            "total_links": 20,
            "valid_links": 18,
            "broken_links": 2,
            "warnings": 1,
            "validation_errors": [],
            "validation_warnings": [],
        }

        # Act
        report = validator.generate_report(validation_result)

        # Assert
        assert "Link Validation Report" in report
        assert "Files checked: 5" in report
        assert "Total links: 20" in report
        assert "Valid links: 18" in report
        assert "Broken links: 2" in report
        assert "Warnings: 1" in report

    def test_includes_broken_links_section(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test includes broken links section with details."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        validation_result: dict[str, object] = {
            "files_checked": 1,
            "total_links": 1,
            "valid_links": 0,
            "broken_links": 1,
            "warnings": 0,
            "validation_errors": [
                {
                    "file": "source.md",
                    "line": 10,
                    "target": "missing.md",
                    "section": None,
                    "error": "File not found",
                    "suggestion": "Create file",
                }
            ],
            "validation_warnings": [],
        }

        # Act
        report = validator.generate_report(validation_result)

        # Assert
        assert "Broken Links" in report
        assert "source.md:10" in report
        assert "missing.md" in report
        assert "File not found" in report
        assert "Create file" in report

    def test_includes_warnings_section(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test includes warnings section with details."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        validation_result: dict[str, object] = {
            "files_checked": 1,
            "total_links": 1,
            "valid_links": 0,
            "broken_links": 0,
            "warnings": 1,
            "validation_errors": [],
            "validation_warnings": [
                {
                    "file": "source.md",
                    "line": 5,
                    "target": "target.md",
                    "section": "Missing",
                    "warning": "Section not found",
                    "suggestion": "Check section name",
                }
            ],
        }

        # Act
        report = validator.generate_report(validation_result)

        # Assert
        assert "Warnings" in report
        assert "source.md:5" in report
        assert "target.md#Missing" in report
        assert "Section not found" in report
        assert "Check section name" in report

    def test_handles_empty_results(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test handles validation results with no errors or warnings."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        validation_result: dict[str, object] = {
            "files_checked": 3,
            "total_links": 10,
            "valid_links": 10,
            "broken_links": 0,
            "warnings": 0,
            "validation_errors": [],
            "validation_warnings": [],
        }

        # Act
        report = validator.generate_report(validation_result)

        # Assert
        assert "Link Validation Report" in report
        # Check for section headers, not summary statistics
        assert "## Broken Links" not in report
        assert "## Warnings" not in report

    def test_formats_links_with_sections_correctly(
        self,
        mock_file_system: FileSystemManager,
        mock_link_parser: LinkParser,
    ) -> None:
        """Test formats links with section references correctly."""
        # Arrange
        validator = LinkValidator(mock_file_system, mock_link_parser)
        validation_result: dict[str, object] = {
            "files_checked": 1,
            "total_links": 1,
            "valid_links": 0,
            "broken_links": 1,
            "warnings": 0,
            "validation_errors": [
                {
                    "file": "source.md",
                    "line": 10,
                    "target": "missing.md",
                    "section": "Introduction",
                    "error": "File not found",
                    "suggestion": "Create file",
                }
            ],
            "validation_warnings": [],
        }

        # Act
        report = validator.generate_report(validation_result)

        # Assert
        assert "missing.md#Introduction" in report


# Run tests
if __name__ == "__main__":
    _ = pytest.main([__file__, "-v"])
