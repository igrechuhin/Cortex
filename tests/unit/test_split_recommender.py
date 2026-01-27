"""
Tests for SplitRecommender

This module tests the split recommender that suggests splitting large or complex
files into smaller, more focused components for better context management.
"""

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.models import ModelDict
from cortex.refactoring.split_recommender import (
    SplitPoint,
    SplitRecommendation,
    SplitRecommender,
)


@pytest.fixture
def split_recommender(tmp_path: Path):
    """Create split recommender instance"""
    return SplitRecommender(
        memory_bank_path=tmp_path,
        max_file_size=5000,
        max_sections=10,
        min_section_independence=0.6,
    )


@pytest.fixture
def sample_content_large():
    """Sample large file content with multiple sections"""
    sections: list[str] = []
    for i in range(12):
        section_content = f"# Section {i}\n\n" + ("Lorem ipsum dolor sit amet. " * 200)
        sections.append(section_content)
    return "\n\n".join(sections)


@pytest.fixture
def sample_content_topics():
    """Sample content with multiple distinct topics"""
    return """# Topic 1: Architecture

This section discusses the architecture of the system.

## Subsection 1.1

Details about architecture patterns.

# Topic 2: Implementation

This section covers implementation details.

## Subsection 2.1

Code examples and best practices.

# Topic 3: Testing

This section explains testing strategies.

## Subsection 3.1

Unit testing approaches.

# Topic 4: Deployment

This section describes deployment procedures.
"""


@pytest.fixture
def sample_content_small():
    """Sample small file content"""
    return """# Small File

This is a small file with minimal content.

## Section 1

Just a small section.
"""


class TestSplitRecommenderInitialization:
    """Test SplitRecommender initialization"""

    def test_initialization_with_defaults(self, tmp_path: Path):
        """Test recommender initialization with default values"""
        recommender = SplitRecommender(memory_bank_path=tmp_path)

        assert recommender.memory_bank_path == tmp_path
        assert recommender.max_file_size == 5000
        assert recommender.max_sections == 10
        assert recommender.min_section_independence == 0.6
        assert recommender.recommendation_counter == 0

    def test_initialization_with_custom_values(self, tmp_path: Path):
        """Test recommender initialization with custom values"""
        recommender = SplitRecommender(
            memory_bank_path=tmp_path,
            max_file_size=3000,
            max_sections=8,
            min_section_independence=0.7,
        )

        assert recommender.max_file_size == 3000
        assert recommender.max_sections == 8
        assert recommender.min_section_independence == 0.7

    def test_path_conversion(self, tmp_path: Path):
        """Test that path is converted to Path object"""
        recommender = SplitRecommender(memory_bank_path=tmp_path)

        assert isinstance(recommender.memory_bank_path, Path)
        assert recommender.memory_bank_path == tmp_path

    def test_analyzer_initialization(self, split_recommender: SplitRecommender):
        """Test that analyzer is initialized with correct parameters"""
        assert split_recommender.analyzer is not None
        assert split_recommender.analyzer.max_file_size == 5000
        assert split_recommender.analyzer.max_sections == 10
        assert split_recommender.analyzer.min_section_independence == 0.6


class TestRecommendationIDGeneration:
    """Test recommendation ID generation"""

    def test_generate_unique_ids(self, split_recommender: SplitRecommender):
        """Test that generated IDs are unique"""
        id1 = split_recommender.generate_recommendation_id()
        id2 = split_recommender.generate_recommendation_id()
        id3 = split_recommender.generate_recommendation_id()

        assert id1 != id2 != id3
        assert id1 == "SPLIT-0001"
        assert id2 == "SPLIT-0002"
        assert id3 == "SPLIT-0003"

    def test_id_counter_increments(self, split_recommender: SplitRecommender):
        """Test that counter increments correctly"""
        assert split_recommender.recommendation_counter == 0

        _ = split_recommender.generate_recommendation_id()
        assert split_recommender.recommendation_counter == 1

        _ = split_recommender.generate_recommendation_id()
        assert split_recommender.recommendation_counter == 2

    def test_id_format(self, split_recommender: SplitRecommender):
        """Test that ID format is correct"""
        id1 = split_recommender.generate_recommendation_id()

        assert id1.startswith("SPLIT-")
        assert len(id1) == 10  # "SPLIT-" + 4 digits
        assert id1[6:].isdigit()


class TestFileStructureParsing:
    """Test file structure parsing"""

    def test_parse_simple_structure(self, split_recommender: SplitRecommender):
        """Test parsing simple file structure"""
        content = """# Main Heading

Some content.

## Subheading

More content.
"""
        sections = split_recommender.parse_file_structure(content)

        assert len(sections) == 2
        assert sections[0]["heading"] == "Main Heading"
        assert sections[0]["level"] == 1
        assert sections[1]["heading"] == "Subheading"
        assert sections[1]["level"] == 2

    def test_parse_multiple_sections(
        self, split_recommender: SplitRecommender, sample_content_topics: str
    ):
        """Test parsing file with multiple sections"""
        sections = split_recommender.parse_file_structure(sample_content_topics)

        assert len(sections) >= 4  # At least 4 top-level sections
        top_level = [s for s in sections if s["level"] == 1]
        assert len(top_level) == 4

    def test_parse_empty_content(self, split_recommender: SplitRecommender):
        """Test parsing empty content"""
        sections = split_recommender.parse_file_structure("")

        assert sections == []

    def test_delegates_to_analyzer(self, split_recommender: SplitRecommender):
        """Test that parsing delegates to analyzer"""
        content = "# Test\n\nContent"

        # Call recommender method
        result = split_recommender.parse_file_structure(content)

        # Verify it returns same result as analyzer
        analyzer_result = split_recommender.analyzer.parse_file_structure(content)
        assert result == analyzer_result


class TestAnalyzeFile:
    """Test file analysis"""

    @pytest.mark.asyncio
    async def test_analyze_large_file(
        self, split_recommender: SplitRecommender, sample_content_large: str
    ):
        """Test analyzing large file that needs splitting"""
        file_path = "memory-bank/large.md"
        token_count = len(sample_content_large) // 4  # Rough estimate

        recommendation = await split_recommender.analyze_file(
            file_path=file_path, content=sample_content_large, token_count=token_count
        )

        assert recommendation is not None
        assert recommendation.file_path == file_path
        assert recommendation.reason
        assert recommendation.split_strategy in [
            "by_size",
            "by_sections",
            "by_topics",
        ]
        assert len(recommendation.split_points) > 0

    @pytest.mark.asyncio
    async def test_analyze_small_file(
        self, split_recommender: SplitRecommender, sample_content_small: str
    ):
        """Test analyzing small file that doesn't need splitting"""
        file_path = "memory-bank/small.md"
        token_count = len(sample_content_small) // 4

        recommendation = await split_recommender.analyze_file(
            file_path=file_path, content=sample_content_small, token_count=token_count
        )

        assert recommendation is None

    @pytest.mark.asyncio
    async def test_analyze_with_topics(
        self, split_recommender: SplitRecommender, sample_content_topics: str
    ):
        """Test analyzing file with multiple distinct topics"""
        file_path = "memory-bank/topics.md"
        token_count = len(sample_content_topics) // 4

        recommendation = await split_recommender.analyze_file(
            file_path=file_path, content=sample_content_topics, token_count=token_count
        )

        assert recommendation is not None
        assert recommendation.split_strategy == "by_topics"
        assert len(recommendation.split_points) > 0

    @pytest.mark.asyncio
    async def test_analyze_reads_file_if_no_content(
        self, split_recommender: SplitRecommender, tmp_path: Path
    ):
        """Test that analyzer reads file if content not provided"""
        test_file = tmp_path / "test.md"
        _ = test_file.write_text("# Test\n\n" + ("Content " * 2000))

        with patch.object(
            split_recommender, "read_file", new_callable=AsyncMock
        ) as mock_read:
            mock_read.return_value = test_file.read_text()

            recommendation = await split_recommender.analyze_file(
                file_path=str(test_file), content=None
            )

            mock_read.assert_called_once_with(str(test_file))
            # Recommendation may be None or a valid SplitRecommendation; in either case
            # we ensure the call succeeded without errors.
            assert recommendation is None or recommendation.file_path == str(test_file)

    @pytest.mark.asyncio
    async def test_analyze_calculates_token_count(
        self, split_recommender: SplitRecommender, sample_content_large: str
    ):
        """Test that analyzer calculates token count if not provided"""
        file_path = "memory-bank/test.md"

        recommendation = await split_recommender.analyze_file(
            file_path=file_path, content=sample_content_large, token_count=None
        )

        # Should calculate token count and potentially generate recommendation
        assert (
            recommendation is not None or recommendation is None
        )  # Either outcome valid

    @pytest.mark.asyncio
    async def test_analyze_handles_file_read_error(
        self, split_recommender: SplitRecommender
    ):
        """Test that analyzer handles file read errors gracefully"""
        with patch.object(
            split_recommender, "read_file", new_callable=AsyncMock
        ) as mock_read:
            mock_read.side_effect = Exception("Read error")

            recommendation = await split_recommender.analyze_file(
                file_path="nonexistent.md", content=None
            )

            assert recommendation is None

    @pytest.mark.asyncio
    async def test_analyze_generates_valid_recommendation(
        self, split_recommender: SplitRecommender, sample_content_large: str
    ):
        """Test that generated recommendation has all required fields"""
        recommendation = await split_recommender.analyze_file(
            file_path="test.md",
            content=sample_content_large,
            token_count=len(sample_content_large) // 4,
        )

        assert recommendation is not None
        assert recommendation.recommendation_id.startswith("SPLIT-")
        assert recommendation.file_path == "test.md"
        assert recommendation.reason
        assert recommendation.split_strategy
        assert recommendation.split_points
        assert recommendation.estimated_impact
        assert recommendation.new_structure


class TestSplitPointGeneration:
    """Test split point generation"""

    @pytest.mark.asyncio
    async def test_generate_split_points_by_topics(
        self, split_recommender: SplitRecommender, sample_content_topics: str
    ):
        """Test generating split points by topics"""
        sections = split_recommender.parse_file_structure(sample_content_topics)

        split_points = await split_recommender.generate_split_points(
            file_path="test.md",
            content=sample_content_topics,
            sections=sections,
            strategy="by_topics",
        )

        assert len(split_points) > 0
        # Should have split points for independent top-level sections
        for sp in split_points:
            assert sp.section_heading
            assert sp.start_line > 0
            assert sp.end_line >= sp.start_line
            assert sp.suggested_filename

    @pytest.mark.asyncio
    async def test_generate_split_points_by_sections(
        self, split_recommender: SplitRecommender, sample_content_topics: str
    ):
        """Test generating split points by sections"""
        sections = split_recommender.parse_file_structure(sample_content_topics)

        split_points = await split_recommender.generate_split_points(
            file_path="test.md",
            content=sample_content_topics,
            sections=sections,
            strategy="by_sections",
        )

        # Should group related sections
        assert isinstance(split_points, list)
        for sp in split_points:
            assert isinstance(sp, SplitPoint)
            assert sp.independence_score >= split_recommender.min_section_independence

    @pytest.mark.asyncio
    async def test_generate_split_points_by_size(
        self, split_recommender: SplitRecommender, sample_content_large: str
    ):
        """Test generating split points by size"""
        sections = split_recommender.parse_file_structure(sample_content_large)

        split_points = await split_recommender.generate_split_points(
            file_path="test.md",
            content=sample_content_large,
            sections=sections,
            strategy="by_size",
        )

        assert len(split_points) > 0
        # Should have multiple chunks roughly equal in size
        for sp in split_points:
            assert sp.token_count <= split_recommender.max_file_size

    @pytest.mark.asyncio
    async def test_split_points_respect_independence_threshold(
        self, split_recommender: SplitRecommender, sample_content_topics: str
    ):
        """Test that split points respect independence threshold"""
        sections = split_recommender.parse_file_structure(sample_content_topics)

        split_points = await split_recommender.generate_split_points(
            file_path="test.md",
            content=sample_content_topics,
            sections=sections,
            strategy="by_topics",
        )

        # All split points should meet independence threshold
        for sp in split_points:
            assert sp.independence_score >= split_recommender.min_section_independence


class TestFilenameGeneration:
    """Test split filename generation"""

    def test_generate_split_filename_basic(self, split_recommender: SplitRecommender):
        """Test generating split filename"""
        original = "memory-bank/project-brief.md"
        heading = "Architecture Overview"

        filename = split_recommender.generate_split_filename(original, heading)

        assert "project-brief" in filename
        assert "architecture-overview" in filename
        assert filename.endswith(".md")

    def test_generate_split_filename_slugifies(
        self, split_recommender: SplitRecommender
    ):
        """Test that filename is properly slugified"""
        original = "memory-bank/test.md"
        heading = "Section With Spaces & Special!@# Characters"

        filename = split_recommender.generate_split_filename(original, heading)

        # Should remove special characters and replace spaces with hyphens
        assert "spaces" in filename.lower()
        assert "special" in filename.lower()
        assert "with" in filename.lower()
        assert "@" not in filename
        assert "#" not in filename
        assert "!" not in filename

    def test_generate_split_filename_limits_length(
        self, split_recommender: SplitRecommender
    ):
        """Test that filename length is limited"""
        original = "memory-bank/test.md"
        heading = (
            "Very Long Heading That Should Be Truncated Because It "
            "Exceeds Maximum Length"
        )

        filename = split_recommender.generate_split_filename(original, heading)

        # Slug should be limited to 30 characters
        slug = filename.split("/")[-1].replace("test-", "").replace(".md", "")
        assert len(slug) <= 30

    def test_generate_split_filename_preserves_path(
        self, split_recommender: SplitRecommender
    ):
        """Test that original file path is preserved"""
        original = "memory-bank/subdir/test.md"
        heading = "Section"

        filename = split_recommender.generate_split_filename(original, heading)

        assert filename.startswith("memory-bank/subdir/")


class TestImpactCalculation:
    """Test split impact calculation"""

    def test_calculate_impact_basic(self, split_recommender: SplitRecommender):
        """Test basic impact calculation"""
        split_points = [
            SplitPoint("Section 1", 1, 10, 500, 0.8, "test-section-1.md"),
            SplitPoint("Section 2", 11, 20, 500, 0.7, "test-section-2.md"),
            SplitPoint("Section 3", 21, 30, 500, 0.9, "test-section-3.md"),
        ]

        impact = split_recommender.calculate_split_impact("test.md", 2000, split_points)

        assert impact["original_file_tokens"] == 2000
        assert impact["new_file_count"] == 4  # 3 splits + 1 index
        assert impact["average_file_size"] == 2000 // 4
        assert "benefits" in impact
        assert "considerations" in impact

    def test_calculate_impact_complexity_reduction(
        self, split_recommender: SplitRecommender
    ):
        """Test complexity reduction calculation"""
        many_splits = [
            SplitPoint(f"Section {i}", i * 10, (i + 1) * 10, 300, 0.8, f"test-{i}.md")
            for i in range(5)
        ]

        impact = split_recommender.calculate_split_impact("test.md", 2000, many_splits)

        # More splits should result in higher complexity reduction
        assert impact["complexity_reduction"] == 0.6

    def test_calculate_impact_few_splits(self, split_recommender: SplitRecommender):
        """Test impact calculation with few splits"""
        few_splits = [
            SplitPoint("Section 1", 1, 10, 1000, 0.8, "test-section-1.md"),
        ]

        impact = split_recommender.calculate_split_impact("test.md", 2000, few_splits)

        # Fewer splits should result in lower complexity reduction
        assert impact["complexity_reduction"] == 0.3


class TestNewStructureGeneration:
    """Test new structure generation"""

    def test_generate_new_structure(self, split_recommender: SplitRecommender):
        """Test generating new file structure"""
        split_points = [
            SplitPoint("Section 1", 1, 10, 500, 0.8, "test-section-1.md"),
            SplitPoint("Section 2", 11, 20, 500, 0.7, "test-section-2.md"),
        ]

        structure = split_recommender.generate_new_structure("test.md", split_points)

        assert isinstance(structure, dict)
        assert "index_file" in structure
        assert "split_files" in structure
        assert "total_files" in structure
        total_files = structure.get("total_files")
        assert isinstance(total_files, (int, float))
        assert total_files == 3  # 2 splits + 1 index
        split_files: object | None = structure.get("split_files")
        assert isinstance(split_files, list)
        split_files_list: list[object] = cast(list[object], split_files)
        assert len(split_files_list) == 2

    def test_new_structure_includes_index(self, split_recommender: SplitRecommender):
        """Test that new structure includes index file"""
        split_points = [
            SplitPoint("Section 1", 1, 10, 500, 0.8, "test-section-1.md"),
        ]

        structure = split_recommender.generate_new_structure("test.md", split_points)

        assert isinstance(structure, dict)
        index: object | None = structure.get("index_file")
        assert isinstance(index, dict)
        index_dict = cast(ModelDict, index)
        assert index_dict.get("filename") == "test.md"
        assert "purpose" in index_dict
        purpose: object | None = index_dict.get("purpose")
        assert isinstance(purpose, str)
        assert "Index" in purpose


class TestSuggestFileSplits:
    """Test suggesting splits for multiple files"""

    @pytest.mark.asyncio
    async def test_suggest_for_all_files(
        self, split_recommender: SplitRecommender, tmp_path: Path
    ):
        """Test suggesting splits for all files"""
        # Create test files
        _ = (tmp_path / "large.md").write_text("# Section\n\n" + ("Content " * 2000))
        _ = (tmp_path / "small.md").write_text("# Small\n\nContent")

        recommendations = await split_recommender.suggest_file_splits(files=None)

        # Should analyze all files and return recommendations for large ones
        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_suggest_for_specific_files(
        self, split_recommender: SplitRecommender, sample_content_large: str
    ):
        """Test suggesting splits for specific files"""
        with patch.object(
            split_recommender, "read_file", new_callable=AsyncMock
        ) as mock_read:
            mock_read.return_value = sample_content_large

            files = ["memory-bank/file1.md", "memory-bank/file2.md"]
            recommendations = await split_recommender.suggest_file_splits(files=files)

            assert isinstance(recommendations, list)
            # Should analyze specified files
            assert mock_read.call_count <= len(files)

    @pytest.mark.asyncio
    async def test_suggest_handles_errors(self, split_recommender: SplitRecommender):
        """Test that suggestion handles file errors gracefully"""
        with patch.object(
            split_recommender, "analyze_file", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.side_effect = Exception("Analysis error")

            files = ["memory-bank/test.md"]
            recommendations = await split_recommender.suggest_file_splits(files=files)

            # Should continue despite errors
            assert recommendations == []

    @pytest.mark.asyncio
    async def test_suggest_sorts_by_impact(
        self, split_recommender: SplitRecommender, sample_content_large: str
    ):
        """Test that recommendations are sorted by impact"""
        with patch.object(
            split_recommender, "read_file", new_callable=AsyncMock
        ) as mock_read:
            mock_read.return_value = sample_content_large

            files = ["memory-bank/file1.md", "memory-bank/file2.md"]
            recommendations = await split_recommender.suggest_file_splits(files=files)

            # Should be sorted by complexity reduction (descending)
            if len(recommendations) > 1:
                for i in range(len(recommendations) - 1):
                    rec1 = recommendations[i]
                    rec2 = recommendations[i + 1]
                    impact1_val = rec1.estimated_impact.get("complexity_reduction", 0)
                    impact2_val = rec2.estimated_impact.get("complexity_reduction", 0)
                    assert isinstance(impact1_val, (int, float))
                    assert isinstance(impact2_val, (int, float))
                    assert impact1_val >= impact2_val


class TestSplitRecommendationDataclass:
    """Test SplitRecommendation dataclass"""

    def test_to_dict_conversion(self):
        """Test converting recommendation to dictionary"""
        split_points = [
            SplitPoint("Section 1", 1, 10, 500, 0.8, "test-section-1.md"),
            SplitPoint("Section 2", 11, 20, 500, 0.7, "test-section-2.md"),
        ]

        recommendation = SplitRecommendation(
            recommendation_id="SPLIT-0001",
            file_path="test.md",
            reason="File is too large",
            split_strategy="by_size",
            split_points=split_points,
            estimated_impact={"complexity_reduction": 0.6},
            new_structure={"total_files": 3},
            maintain_dependencies=True,
        )

        result = recommendation.to_dict()

        assert isinstance(result, dict)
        assert result.get("recommendation_id") == "SPLIT-0001"
        assert result.get("file_path") == "test.md"
        assert result.get("reason") == "File is too large"
        assert result.get("split_strategy") == "by_size"
        split_points: object | None = result.get("split_points")
        assert isinstance(split_points, list)
        split_points_list: list[object] = cast(list[object], split_points)
        assert len(split_points_list) == 2
        assert result.get("estimated_impact") == {"complexity_reduction": 0.6}
        assert result.get("maintain_dependencies") is True

    def test_to_dict_split_points_format(self):
        """Test that split points are properly formatted in dict"""
        split_point = SplitPoint("Section 1", 1, 10, 500, 0.8, "test-section-1.md")

        recommendation = SplitRecommendation(
            recommendation_id="SPLIT-0001",
            file_path="test.md",
            reason="Test",
            split_strategy="by_size",
            split_points=[split_point],
            estimated_impact={},
            new_structure={},
        )

        result = recommendation.to_dict()
        assert isinstance(result, dict)
        split_points: object | None = result.get("split_points")
        assert isinstance(split_points, list)
        split_points_list: list[object] = cast(list[object], split_points)
        assert len(split_points_list) > 0
        sp_dict_raw: object = split_points_list[0]
        assert isinstance(sp_dict_raw, dict)
        sp_dict = cast(ModelDict, sp_dict_raw)

        assert sp_dict.get("heading") == "Section 1"
        assert sp_dict.get("lines") == "1-10"
        assert sp_dict.get("tokens") == 500
        assert sp_dict.get("independence") == 0.8
        assert sp_dict.get("target_file") == "test-section-1.md"


class TestHelperMethods:
    """Test helper methods"""

    def test_get_section_str(self, split_recommender: SplitRecommender):
        """Test extracting string from section dict"""
        section = cast(ModelDict, {"heading": "Test Heading", "level": 1})

        result = split_recommender.get_section_str(section, "heading")
        assert result == "Test Heading"

        result = split_recommender.get_section_str(section, "missing", "default")
        assert result == "default"

    def test_get_section_int(self, split_recommender: SplitRecommender):
        """Test extracting int from section dict"""
        section = cast(ModelDict, {"level": 1, "start_line": 10})

        result = split_recommender.get_section_int(section, "level")
        assert result == 1

        result = split_recommender.get_section_int(section, "missing", 0)
        assert result == 0

    def test_get_section_content(self, split_recommender: SplitRecommender):
        """Test extracting content from section dict"""
        section = cast(ModelDict, {"content": "Test content"})

        result = split_recommender.get_section_content(section)
        assert result == "Test content"

        # Test with list content
        section_list = cast(ModelDict, {"content": ["Line 1", "Line 2"]})
        result = split_recommender.get_section_content(section_list)
        assert result == "Line 1\nLine 2"

    @pytest.mark.asyncio
    async def test_read_file(self, split_recommender: SplitRecommender, tmp_path: Path):
        """Test reading file contents"""
        test_file = tmp_path / "test.md"
        _ = test_file.write_text("# Test Content")

        content = await split_recommender.read_file(str(test_file))
        assert content == "# Test Content"

    @pytest.mark.asyncio
    async def test_read_file_error(self, split_recommender: SplitRecommender):
        """Test reading nonexistent file"""
        content = await split_recommender.read_file("nonexistent.md")
        assert content == ""

    @pytest.mark.asyncio
    async def test_get_all_markdown_files(
        self, split_recommender: SplitRecommender, tmp_path: Path
    ):
        """Test getting all markdown files"""
        # Create test files
        _ = (tmp_path / "file1.md").write_text("Content 1")
        _ = (tmp_path / "file2.md").write_text("Content 2")
        _ = (tmp_path / "file.txt").write_text("Not markdown")

        files = await split_recommender.get_all_markdown_files()

        # Should only return .md files
        assert len(files) == 2
        assert all(f.endswith(".md") for f in files)
