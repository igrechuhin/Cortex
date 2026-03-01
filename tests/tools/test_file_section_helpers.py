"""Tests for section_helpers module.

Tests cover section extraction functions to achieve high coverage.
"""

from cortex.tools.files.section_helpers import (
    extract_content_sections,
    extract_nested_section,
    extract_section_from_content,
    extract_sections_from_content,
    find_section_end,
    find_section_heading,
)


class TestFindSectionHeading:
    """Test find_section_heading function."""

    def test_find_section_heading_with_hash_prefix(self):
        """Test finding section heading with hash prefix."""
        lines = ["# Title", "## Section 1", "### Subsection", "## Section 2"]
        result = find_section_heading(lines, "## Section 1")
        assert result == (1, 2)

    def test_find_section_heading_without_hash_prefix(self):
        """Test finding section heading without hash prefix."""
        lines = ["# Title", "## Section 1", "### Subsection", "## Section 2"]
        result = find_section_heading(lines, "Section 1")
        assert result == (1, 2)

    def test_find_section_heading_text_only_with_whitespace(self):
        """Test finding section heading text-only match with whitespace (line 153-160)."""
        lines = ["# Title", "  ## Section 1  ", "### Subsection"]
        result = find_section_heading(lines, "Section 1")
        assert result == (1, 2)

    def test_find_section_heading_text_only_case_insensitive(self):
        """Test finding section heading text-only match case-insensitive."""
        lines = ["# Title", "## SECTION 1", "### Subsection"]
        result = find_section_heading(lines, "section 1")
        assert result == (1, 2)

    def test_find_section_heading_case_insensitive(self):
        """Test finding section heading case-insensitive."""
        lines = ["# Title", "## Section 1", "### Subsection"]
        result = find_section_heading(lines, "section 1")
        assert result == (1, 2)

    def test_find_section_heading_not_found(self):
        """Test finding section heading that doesn't exist."""
        lines = ["# Title", "## Section 1"]
        result = find_section_heading(lines, "## Missing")
        assert result == (None, None)


class TestFindSectionEnd:
    """Test find_section_end function."""

    def test_find_section_end_with_next_same_level(self):
        """Test finding section end with next heading at same level."""
        lines = ["## Section 1", "content", "## Section 2"]
        result = find_section_end(lines, 0, 2)
        assert result == 2

    def test_find_section_end_with_next_higher_level(self):
        """Test finding section end with next heading at higher level."""
        lines = ["## Section 1", "content", "# Title"]
        result = find_section_end(lines, 0, 2)
        assert result == 2

    def test_find_section_end_at_file_end(self):
        """Test finding section end at file end."""
        lines = ["## Section 1", "content"]
        result = find_section_end(lines, 0, 2)
        assert result == 2

    def test_find_section_end_with_none_level(self):
        """Test finding section end with None level (line 179)."""
        lines = ["## Section 1", "content"]
        result = find_section_end(lines, 0, None)
        assert result == 2

    def test_find_section_end_with_none_level_at_end(self):
        """Test finding section end with None level at end of file."""
        lines = ["## Section 1", "content", "more content"]
        result = find_section_end(lines, 0, None)
        assert result == 3


class TestExtractNestedSection:
    """Test extract_nested_section function."""

    def test_extract_nested_section_success(self):
        """Test extracting nested section successfully."""
        lines = [
            "## Parent",
            "parent content",
            "### Child",
            "child content",
            "## Other",
        ]
        result = extract_nested_section(lines, ["## Parent", "### Child"])
        assert result[0] == "### Child\nchild content"
        assert result[1] is None

    def test_extract_nested_section_parent_not_found(self):
        """Test extracting nested section when parent not found."""
        lines = ["## Other", "content"]
        result = extract_nested_section(lines, ["## Parent", "### Child"])
        assert "\n".join(lines) in result[0]
        assert result[1] is not None
        assert "not found" in result[1]

    def test_extract_nested_section_child_not_found(self):
        """Test extracting nested section when child not found (line 58)."""
        lines = ["## Parent", "parent content", "## Other"]
        result = extract_nested_section(lines, ["## Parent", "### Child"])
        assert "\n".join(lines) in result[0]
        assert result[1] is not None
        assert "not found" in result[1]
        assert "Child" in result[1]
        assert "Parent" in result[1]

    def test_extract_nested_section_parent_not_found_returns_full(self):
        """Test extracting nested section when parent not found returns full file (line 48)."""
        lines = ["## Other Section", "content"]
        result = extract_nested_section(lines, ["## Parent", "### Child"])
        assert "\n".join(lines) == result[0]
        assert result[1] is not None
        assert "not found" in result[1]
        assert "Parent" in result[1]


class TestExtractSectionFromContent:
    """Test extract_section_from_content function."""

    def test_extract_section_from_content_simple(self):
        """Test extracting simple section."""
        content = "## Section 1\ncontent 1\n## Section 2\ncontent 2"
        result = extract_section_from_content(content, "## Section 1")
        assert result[0] == "## Section 1\ncontent 1"
        assert result[1] is None

    def test_extract_section_from_content_nested(self):
        """Test extracting nested section."""
        content = "## Parent\nparent content\n### Child\nchild content\n## Other"
        result = extract_section_from_content(content, "## Parent/### Child")
        assert "### Child\nchild content" in result[0]
        assert result[1] is None

    def test_extract_section_from_content_not_found(self):
        """Test extracting section that doesn't exist."""
        content = "## Section 1\ncontent"
        result = extract_section_from_content(content, "## Missing")
        assert result[0] == content
        assert result[1] is not None
        assert "not found" in result[1]


class TestExtractSectionsFromContent:
    """Test extract_sections_from_content function."""

    def test_extract_sections_from_content_multiple(self):
        """Test extracting multiple sections."""
        content = (
            "## Section 1\ncontent 1\n## Section 2\ncontent 2\n## Section 3\ncontent 3"
        )
        result = extract_sections_from_content(
            content, ["## Section 1", "## Section 3"]
        )
        assert "## Section 1\ncontent 1" in result[0]
        assert "## Section 3\ncontent 3" in result[0]
        assert "---" in result[0]
        assert result[1] is None

    def test_extract_sections_from_content_with_warnings(self):
        """Test extracting sections with some not found."""
        content = "## Section 1\ncontent 1"
        result = extract_sections_from_content(content, ["## Section 1", "## Missing"])
        assert "## Section 1\ncontent 1" in result[0]
        assert result[1] is not None
        assert "not found" in result[1]


class TestExtractContentSections:
    """Test extract_content_sections function."""

    def test_extract_content_sections_with_sections(self):
        """Test extracting content with sections specified."""
        content = "## Section 1\ncontent 1\n## Section 2\ncontent 2"
        result = extract_content_sections(content, ["## Section 1"])
        assert "## Section 1\ncontent 1" in result[0]
        assert result[1] is None

    def test_extract_content_sections_without_sections(self):
        """Test extracting content without sections specified."""
        content = "## Section 1\ncontent 1"
        result = extract_content_sections(content, None)
        assert result[0] == content
        assert result[1] is None

    def test_find_section_heading_with_whitespace(self):
        """Test finding section heading with whitespace."""
        lines = ["  ## Section 1  ", "content"]
        result = find_section_heading(lines, "## Section 1")
        assert result == (0, 2)

    def test_find_section_end_with_lower_level(self):
        """Test finding section end with next heading at lower level."""
        lines = ["## Section 1", "content", "### Subsection"]
        result = find_section_end(lines, 0, 2)
        assert result == 3

    def test_extract_nested_section_deep_nesting(self):
        """Test extracting deeply nested section."""
        lines = [
            "## Parent",
            "parent content",
            "### Child",
            "child content",
            "#### Grandchild",
            "grandchild content",
            "## Other",
        ]
        result = extract_nested_section(lines, ["## Parent", "#### Grandchild"])
        assert "#### Grandchild" in result[0]
        assert result[1] is None

    def test_extract_section_from_content_empty_content(self):
        """Test extracting section from empty content."""
        content = ""
        result = extract_section_from_content(content, "## Missing")
        assert result[0] == ""
        assert result[1] is not None
        assert "not found" in result[1]

    def test_extract_sections_from_content_empty_list(self):
        """Test extracting sections with empty list."""
        content = "## Section 1\ncontent"
        result = extract_sections_from_content(content, [])
        assert result[0] == ""
        assert result[1] is None

    def test_find_section_heading_with_multiple_matches(self):
        """Test finding section heading when multiple matches exist."""
        lines = ["## Section", "content", "## Section", "more content"]
        result = find_section_heading(lines, "## Section")
        # Should return first match
        assert result == (0, 2)

    def test_find_section_end_at_start(self):
        """Test finding section end when section starts at beginning."""
        lines = ["## Section", "content"]
        result = find_section_end(lines, 0, 2)
        assert result == 2

    def test_extract_section_from_content_with_trailing_newlines(self):
        """Test extracting section with trailing newlines."""
        content = "## Section 1\ncontent\n\n## Section 2"
        result = extract_section_from_content(content, "## Section 1")
        assert "## Section 1" in result[0]
        assert "content" in result[0]
        assert result[1] is None

    def test_extract_nested_section_with_empty_parent(self):
        """Test extracting nested section when parent has no content."""
        lines = ["## Parent", "### Child", "content", "## Other"]
        result = extract_nested_section(lines, ["## Parent", "### Child"])
        assert "### Child" in result[0]
        assert result[1] is None
