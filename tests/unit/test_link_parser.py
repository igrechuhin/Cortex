"""Comprehensive tests for LinkParser module.

Tests all functionality of the link parser including:
- Markdown link parsing
- Transclusion directive parsing
- Link target parsing (file and section)
- Transclusion options parsing
- Link extraction and counting
- Edge cases and error conditions

Part of Phase 7.2: Test Coverage Implementation
Target: 90%+ coverage for link_parser.py
"""

from typing import cast

import pytest

from cortex.linking.link_parser import LinkParser


class TestLinkParserInitialization:
    """Tests for LinkParser initialization."""

    def test_initialization_creates_patterns(self):
        """Test that initialization creates regex patterns."""
        parser = LinkParser()

        assert hasattr(parser, "link_pattern")
        assert hasattr(parser, "transclusion_pattern")
        assert parser.link_pattern is not None
        assert parser.transclusion_pattern is not None

    def test_link_pattern_is_compiled_regex(self):
        """Test that link pattern is a compiled regex."""
        parser = LinkParser()

        assert hasattr(parser.link_pattern, "search")
        assert hasattr(parser.link_pattern, "finditer")


class TestParseFile:
    """Tests for parse_file method."""

    @pytest.mark.asyncio
    async def test_parse_file_with_no_links(self):
        """Test parsing file with no links or transclusions."""
        parser = LinkParser()
        content = "# Title\n\nThis is plain text with no links."

        result = await parser.parse_file(content)

        assert "markdown_links" in result
        assert "transclusions" in result
        assert len(result["markdown_links"]) == 0
        assert len(result["transclusions"]) == 0

    @pytest.mark.asyncio
    async def test_parse_file_with_markdown_link(self):
        """Test parsing file with a markdown link."""
        parser = LinkParser()
        content = "See [project brief](projectBrief.md) for details."

        result = await parser.parse_file(content)

        assert len(result["markdown_links"]) == 1
        link = result["markdown_links"][0]
        assert link["text"] == "project brief"
        assert link["target"] == "projectBrief.md"
        assert link["section"] is None
        assert link["line"] == 1
        assert link["type"] == "reference"

    @pytest.mark.asyncio
    async def test_parse_file_with_link_and_section(self):
        """Test parsing link with section reference."""
        parser = LinkParser()
        content = "See [architecture](systemPatterns.md#Architecture) section."

        result = await parser.parse_file(content)

        assert len(result["markdown_links"]) == 1
        link = result["markdown_links"][0]
        assert link["text"] == "architecture"
        assert link["target"] == "systemPatterns.md"
        assert link["section"] == "Architecture"
        assert link["line"] == 1

    @pytest.mark.asyncio
    async def test_parse_file_skips_external_urls(self):
        """Test that external URLs are skipped."""
        parser = LinkParser()
        content = """
        [Google](https://google.com)
        [HTTP link](http://example.com)
        [Email](mailto:test@example.com)
        [Local file](projectBrief.md)
        """

        result = await parser.parse_file(content)

        # Should only find the local file link
        assert len(result["markdown_links"]) == 1
        assert result["markdown_links"][0]["target"] == "projectBrief.md"

    @pytest.mark.asyncio
    async def test_parse_file_with_transclusion_directive(self):
        """Test parsing file with transclusion directive."""
        parser = LinkParser()
        content = "{{include: systemPatterns.md}}"

        result = await parser.parse_file(content)

        assert len(result["transclusions"]) == 1
        trans = result["transclusions"][0]
        assert trans["target"] == "systemPatterns.md"
        assert trans["section"] is None
        assert trans["options"] == {}
        assert trans["line"] == 1
        assert trans["type"] == "transclusion"

    @pytest.mark.asyncio
    async def test_parse_file_with_transclusion_and_section(self):
        """Test parsing transclusion with section."""
        parser = LinkParser()
        content = "{{include: systemPatterns.md#Architecture}}"

        result = await parser.parse_file(content)

        assert len(result["transclusions"]) == 1
        trans = result["transclusions"][0]
        assert trans["target"] == "systemPatterns.md"
        assert trans["section"] == "Architecture"

    @pytest.mark.asyncio
    async def test_parse_file_with_transclusion_options(self):
        """Test parsing transclusion with options."""
        parser = LinkParser()
        content = "{{include: systemPatterns.md|lines=5}}"

        result = await parser.parse_file(content)

        assert len(result["transclusions"]) == 1
        trans = result["transclusions"][0]
        assert trans["target"] == "systemPatterns.md"
        assert trans["options"] == {"lines": 5}

    @pytest.mark.asyncio
    async def test_parse_file_with_multiple_links_and_transclusions(self):
        """Test parsing file with multiple links and transclusions."""
        parser = LinkParser()
        content = """
        # Documentation

        See [project brief](projectBrief.md) for overview.
        Check [tech context](techContext.md#Stack) for details.

        {{include: systemPatterns.md#Architecture}}
        {{include: activeContext.md|lines=10}}
        """

        result = await parser.parse_file(content)

        assert len(result["markdown_links"]) == 2
        assert len(result["transclusions"]) == 2
        assert result["markdown_links"][0]["target"] == "projectBrief.md"
        assert result["markdown_links"][1]["target"] == "techContext.md"

    @pytest.mark.asyncio
    async def test_parse_file_with_memory_bank_files_without_md_extension(self):
        """Test that memory bank files without .md are included."""
        parser = LinkParser()
        content = """
        [Instructions](memorybankinstructions)
        [Brief](projectBrief)
        [Context](activeContext)
        """

        result = await parser.parse_file(content)

        # All three should be included as they're memory bank files
        assert len(result["markdown_links"]) == 3

    @pytest.mark.asyncio
    async def test_parse_file_tracks_line_numbers(self):
        """Test that line numbers are correctly tracked."""
        parser = LinkParser()
        content = """Line 1
Line 2 with [link](file.md)
Line 3
Line 4 with {{include: other.md}}
Line 5"""

        result = await parser.parse_file(content)

        assert result["markdown_links"][0]["line"] == 2
        assert result["transclusions"][0]["line"] == 4

    @pytest.mark.asyncio
    async def test_parse_file_with_whitespace_in_targets(self):
        """Test parsing handles whitespace in targets."""
        parser = LinkParser()
        content = "[link](  projectBrief.md  #  Section  )"

        result = await parser.parse_file(content)

        assert len(result["markdown_links"]) == 1
        link = result["markdown_links"][0]
        assert link["target"] == "projectBrief.md"
        assert link["section"] == "Section"


class TestParseLinkTarget:
    """Tests for parse_link_target method."""

    def test_parse_link_target_with_file_only(self):
        """Test parsing target with file only."""
        parser = LinkParser()

        file_path, section = parser.parse_link_target("projectBrief.md")

        assert file_path == "projectBrief.md"
        assert section is None

    def test_parse_link_target_with_file_and_section(self):
        """Test parsing target with file and section."""
        parser = LinkParser()

        file_path, section = parser.parse_link_target("systemPatterns.md#Architecture")

        assert file_path == "systemPatterns.md"
        assert section == "Architecture"

    def test_parse_link_target_with_multiple_hash_symbols(self):
        """Test parsing target with multiple # symbols (only first is used)."""
        parser = LinkParser()

        file_path, section = parser.parse_link_target("file.md#Section#Subsection")

        assert file_path == "file.md"
        assert section == "Section#Subsection"

    def test_parse_link_target_with_whitespace(self):
        """Test parsing target with whitespace."""
        parser = LinkParser()

        file_path, section = parser.parse_link_target("  file.md  #  Section  ")

        assert file_path == "file.md"
        assert section == "Section"

    def test_parse_link_target_with_empty_section(self):
        """Test parsing target with empty section after #."""
        parser = LinkParser()

        file_path, section = parser.parse_link_target("file.md#")

        assert file_path == "file.md"
        assert section == ""


class TestParseTransclusionOptions:
    """Tests for parse_transclusion_options method."""

    def test_parse_transclusion_options_with_empty_string(self):
        """Test parsing empty options string."""
        parser = LinkParser()

        options = parser.parse_transclusion_options("")

        assert options == {}

    def test_parse_transclusion_options_with_none(self):
        """Test parsing None options."""
        parser = LinkParser()

        options = parser.parse_transclusion_options(None)

        assert options == {}

    def test_parse_transclusion_options_with_integer_value(self):
        """Test parsing options with integer value."""
        parser = LinkParser()

        options = parser.parse_transclusion_options("lines=5")

        assert options == {"lines": 5}
        assert isinstance(options["lines"], int)

    def test_parse_transclusion_options_with_boolean_true(self):
        """Test parsing options with boolean true values."""
        parser = LinkParser()

        # Test various true representations
        assert parser.parse_transclusion_options("recursive=true") == {
            "recursive": True
        }
        assert parser.parse_transclusion_options("recursive=True") == {
            "recursive": True
        }
        assert parser.parse_transclusion_options("recursive=yes") == {"recursive": True}
        assert parser.parse_transclusion_options("recursive=1") == {"recursive": True}

    def test_parse_transclusion_options_with_boolean_false(self):
        """Test parsing options with boolean false values."""
        parser = LinkParser()

        # Test various false representations
        assert parser.parse_transclusion_options("recursive=false") == {
            "recursive": False
        }
        assert parser.parse_transclusion_options("recursive=False") == {
            "recursive": False
        }
        assert parser.parse_transclusion_options("recursive=no") == {"recursive": False}
        assert parser.parse_transclusion_options("recursive=0") == {"recursive": False}

    def test_parse_transclusion_options_with_string_value(self):
        """Test parsing options with string value."""
        parser = LinkParser()

        options = parser.parse_transclusion_options("mode=summary")

        assert options == {"mode": "summary"}
        assert isinstance(options["mode"], str)

    def test_parse_transclusion_options_with_multiple_options_pipe_separated(self):
        """Test parsing multiple options separated by pipe."""
        parser = LinkParser()

        options = parser.parse_transclusion_options("lines=5|recursive=true")

        assert options == {"lines": 5, "recursive": True}

    def test_parse_transclusion_options_with_multiple_options_comma_separated(self):
        """Test parsing multiple options separated by comma."""
        parser = LinkParser()

        options = parser.parse_transclusion_options("lines=10,mode=full")

        assert options == {"lines": 10, "mode": "full"}

    def test_parse_transclusion_options_with_whitespace(self):
        """Test parsing options with extra whitespace."""
        parser = LinkParser()

        options = parser.parse_transclusion_options(
            "  lines = 5  |  recursive = true  "
        )

        assert options == {"lines": 5, "recursive": True}

    def test_parse_transclusion_options_ignores_invalid_pairs(self):
        """Test parsing ignores invalid option pairs (no =)."""
        parser = LinkParser()

        options = parser.parse_transclusion_options("lines=5|invalid|recursive=true")

        # Should skip 'invalid' and only parse valid key=value pairs
        assert options == {"lines": 5, "recursive": True}


class TestExtractAllLinks:
    """Tests for extract_all_links method."""

    def test_extract_all_links_with_empty_data(self):
        """Test extracting links from empty parsed data."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {"markdown_links": [], "transclusions": []},
        )

        links = parser.extract_all_links(parsed_data)

        assert links == []

    def test_extract_all_links_from_markdown_links_only(self):
        """Test extracting links from markdown links only."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [
                    {"target": "file1.md", "section": None},
                    {"target": "file2.md", "section": "Section"},
                ],
                "transclusions": [],
            },
        )

        links = parser.extract_all_links(parsed_data)

        assert links == ["file1.md", "file2.md"]

    def test_extract_all_links_from_transclusions_only(self):
        """Test extracting links from transclusions only."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [],
                "transclusions": [
                    {"target": "file1.md", "section": None},
                    {"target": "file2.md", "section": "Section"},
                ],
            },
        )

        links = parser.extract_all_links(parsed_data)

        assert links == ["file1.md", "file2.md"]

    def test_extract_all_links_removes_duplicates(self):
        """Test that duplicate targets are removed."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [
                    {"target": "file1.md", "section": None},
                    {"target": "file2.md", "section": "Section"},
                ],
                "transclusions": [
                    {"target": "file1.md", "section": "Different"},
                    {"target": "file3.md", "section": None},
                ],
            },
        )

        links = parser.extract_all_links(parsed_data)

        # Should return unique files, sorted
        assert links == ["file1.md", "file2.md", "file3.md"]

    def test_extract_all_links_returns_sorted_list(self):
        """Test that links are returned in sorted order."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [
                    {"target": "zzz.md", "section": None},
                    {"target": "aaa.md", "section": None},
                ],
                "transclusions": [{"target": "mmm.md", "section": None}],
            },
        )

        links = parser.extract_all_links(parsed_data)

        assert links == ["aaa.md", "mmm.md", "zzz.md"]

    def test_extract_all_links_skips_empty_targets(self):
        """Test that empty targets are skipped."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [
                    {"target": "file1.md", "section": None},
                    {"target": "", "section": None},
                    {"target": "file2.md", "section": None},
                ],
                "transclusions": [],
            },
        )

        links = parser.extract_all_links(parsed_data)

        assert links == ["file1.md", "file2.md"]


class TestGetTransclusionTargets:
    """Tests for get_transclusion_targets method."""

    def test_get_transclusion_targets_with_no_transclusions(self):
        """Test getting targets when no transclusions exist."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {"markdown_links": [{"target": "file1.md"}], "transclusions": []},
        )

        targets = parser.get_transclusion_targets(parsed_data)

        assert targets == []

    def test_get_transclusion_targets_with_single_transclusion(self):
        """Test getting targets with single transclusion."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {"markdown_links": [], "transclusions": [{"target": "file1.md"}]},
        )

        targets = parser.get_transclusion_targets(parsed_data)

        assert targets == ["file1.md"]

    def test_get_transclusion_targets_with_multiple_transclusions(self):
        """Test getting targets with multiple transclusions."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [],
                "transclusions": [
                    {"target": "file1.md"},
                    {"target": "file2.md"},
                    {"target": "file3.md"},
                ],
            },
        )

        targets = parser.get_transclusion_targets(parsed_data)

        assert targets == ["file1.md", "file2.md", "file3.md"]

    def test_get_transclusion_targets_preserves_duplicates(self):
        """Test that duplicates are preserved (not unique)."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [],
                "transclusions": [
                    {"target": "file1.md"},
                    {"target": "file1.md"},
                    {"target": "file2.md"},
                ],
            },
        )

        targets = parser.get_transclusion_targets(parsed_data)

        # Should preserve duplicates
        assert len(targets) == 3
        assert targets == ["file1.md", "file1.md", "file2.md"]

    def test_get_transclusion_targets_skips_empty_targets(self):
        """Test that empty targets are skipped."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [],
                "transclusions": [
                    {"target": "file1.md"},
                    {"target": ""},
                    {"target": "file2.md"},
                ],
            },
        )

        targets = parser.get_transclusion_targets(parsed_data)

        assert targets == ["file1.md", "file2.md"]


class TestHasTransclusions:
    """Tests for has_transclusions method."""

    def test_has_transclusions_with_no_transclusions(self):
        """Test content with no transclusions."""
        parser = LinkParser()
        content = "# Title\n\nPlain text with [link](file.md)"

        assert parser.has_transclusions(content) is False

    def test_has_transclusions_with_basic_transclusion(self):
        """Test content with basic transclusion."""
        parser = LinkParser()
        content = "{{include: file.md}}"

        assert parser.has_transclusions(content) is True

    def test_has_transclusions_with_transclusion_and_section(self):
        """Test content with transclusion and section."""
        parser = LinkParser()
        content = "Text {{include: file.md#section}} more text"

        assert parser.has_transclusions(content) is True

    def test_has_transclusions_with_transclusion_and_options(self):
        """Test content with transclusion and options."""
        parser = LinkParser()
        content = "{{include: file.md|lines=5}}"

        assert parser.has_transclusions(content) is True

    def test_has_transclusions_with_multiple_transclusions(self):
        """Test content with multiple transclusions."""
        parser = LinkParser()
        content = """
        {{include: file1.md}}
        Some text
        {{include: file2.md#section}}
        """

        assert parser.has_transclusions(content) is True

    def test_has_transclusions_with_partial_syntax(self):
        """Test that partial syntax doesn't match."""
        parser = LinkParser()
        content = "This has {{include but not complete syntax"

        assert parser.has_transclusions(content) is False


class TestCountLinks:
    """Tests for count_links method."""

    def test_count_links_with_empty_data(self):
        """Test counting with empty parsed data."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {"markdown_links": [], "transclusions": []},
        )

        counts = parser.count_links(parsed_data)

        assert counts["markdown_links"] == 0
        assert counts["transclusions"] == 0
        assert counts["total"] == 0
        assert counts["unique_files"] == 0

    def test_count_links_with_markdown_links_only(self):
        """Test counting with markdown links only."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [
                    {"target": "file1.md"},
                    {"target": "file2.md"},
                    {"target": "file3.md"},
                ],
                "transclusions": [],
            },
        )

        counts = parser.count_links(parsed_data)

        assert counts["markdown_links"] == 3
        assert counts["transclusions"] == 0
        assert counts["total"] == 3
        assert counts["unique_files"] == 3

    def test_count_links_with_transclusions_only(self):
        """Test counting with transclusions only."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [],
                "transclusions": [{"target": "file1.md"}, {"target": "file2.md"}],
            },
        )

        counts = parser.count_links(parsed_data)

        assert counts["markdown_links"] == 0
        assert counts["transclusions"] == 2
        assert counts["total"] == 2
        assert counts["unique_files"] == 2

    def test_count_links_with_both_types(self):
        """Test counting with both markdown links and transclusions."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [{"target": "file1.md"}, {"target": "file2.md"}],
                "transclusions": [{"target": "file3.md"}, {"target": "file4.md"}],
            },
        )

        counts = parser.count_links(parsed_data)

        assert counts["markdown_links"] == 2
        assert counts["transclusions"] == 2
        assert counts["total"] == 4
        assert counts["unique_files"] == 4

    def test_count_links_with_duplicate_targets(self):
        """Test counting correctly handles duplicate targets."""
        parser = LinkParser()
        parsed_data = cast(
            dict[str, list[dict[str, object]]],
            {
                "markdown_links": [{"target": "file1.md"}, {"target": "file2.md"}],
                "transclusions": [
                    {"target": "file1.md"},  # Duplicate
                    {"target": "file3.md"},
                ],
            },
        )

        counts = parser.count_links(parsed_data)

        assert counts["markdown_links"] == 2
        assert counts["transclusions"] == 2
        assert counts["total"] == 4
        assert counts["unique_files"] == 3  # file1, file2, file3


class TestLinkParserEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_parse_file_with_unicode_content(self):
        """Test parsing file with unicode characters."""
        parser = LinkParser()
        content = "See [ссылка](файл.md) and [链接](文件.md)"

        result = await parser.parse_file(content)

        # Should handle unicode in link text and filenames
        assert len(result["markdown_links"]) == 2

    @pytest.mark.asyncio
    async def test_parse_file_with_nested_brackets(self):
        """Test parsing with nested brackets in link text."""
        parser = LinkParser()
        content = "[See [nested] text](file.md)"

        result = await parser.parse_file(content)

        # May or may not match depending on regex, but shouldn't crash
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_parse_file_with_multiline_content(self):
        """Test parsing multiline content."""
        parser = LinkParser()
        content = """Line 1 [link1](file1.md)
Line 2 with {{include: file2.md}}
Line 3 [link2](file3.md)
Line 4 {{include: file4.md}}"""

        result = await parser.parse_file(content)

        assert len(result["markdown_links"]) == 2
        assert len(result["transclusions"]) == 2

    @pytest.mark.asyncio
    async def test_parse_file_with_empty_content(self):
        """Test parsing empty content."""
        parser = LinkParser()
        content = ""

        result = await parser.parse_file(content)

        assert result["markdown_links"] == []
        assert result["transclusions"] == []

    @pytest.mark.asyncio
    async def test_parse_file_with_only_whitespace(self):
        """Test parsing content with only whitespace."""
        parser = LinkParser()
        content = "   \n\n   \t\t   \n"

        result = await parser.parse_file(content)

        assert result["markdown_links"] == []
        assert result["transclusions"] == []

    def test_parse_transclusion_options_with_special_characters_in_values(self):
        """Test parsing options with special characters."""
        parser = LinkParser()

        # Special characters in string values
        options = parser.parse_transclusion_options("mode=full-width")

        assert options == {"mode": "full-width"}

    @pytest.mark.asyncio
    async def test_parse_file_with_same_line_multiple_links(self):
        """Test parsing line with multiple links."""
        parser = LinkParser()
        content = "See [file1](file1.md) and [file2](file2.md) for details."

        result = await parser.parse_file(content)

        assert len(result["markdown_links"]) == 2
        assert result["markdown_links"][0]["line"] == 1
        assert result["markdown_links"][1]["line"] == 1
