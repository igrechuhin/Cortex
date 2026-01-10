"""
File analysis functionality for split recommendations.

This module handles the analysis of file structure, complexity assessment,
and determination of whether and how files should be split.
"""

import re
from typing import cast


class SplitAnalyzer:
    """
    Analyze files to determine if they need splitting.

    Evaluates file structure, section independence, and complexity
    to provide recommendations on split strategies.
    """

    def __init__(
        self,
        max_file_size: int = 5000,  # tokens
        max_sections: int = 10,
        min_section_independence: float = 0.6,
    ):
        """
        Initialize the split analyzer.

        Args:
            max_file_size: Maximum recommended file size in tokens
            max_sections: Maximum recommended number of sections per file
            min_section_independence: Minimum independence score for split (0-1)
        """
        self.max_file_size: int = max_file_size
        self.max_sections: int = max_sections
        self.min_section_independence: float = min_section_independence

    def parse_file_structure(self, content: str) -> list[dict[str, object]]:
        """
        Parse file into structured sections.

        Identifies markdown sections and their boundaries for analysis.

        Args:
            content: File content to parse

        Returns:
            List of section dictionaries with heading, level, lines, and content
        """
        sections: list[dict[str, object]] = []
        lines = content.split("\n")
        current_section = None

        for i, line in enumerate(lines, start=1):
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if heading_match:
                if current_section:
                    current_section = self._close_parsed_section(
                        current_section, i, sections, lines
                    )

                current_section = self._start_new_section(heading_match, i)

        if current_section:
            _ = self._close_final_section(current_section, sections, lines)

        return sections

    def _close_parsed_section(
        self,
        current_section: dict[str, object],
        end_line: int,
        sections: list[dict[str, object]],
        lines: list[str],
    ) -> dict[str, object] | None:
        """Close current section and add to sections list."""
        start_line_val = current_section.get("start_line")
        if not isinstance(start_line_val, int):
            return None

        current_section["end_line"] = end_line - 1
        current_section["content"] = "\n".join(lines[start_line_val - 1 : end_line - 1])
        sections.append(current_section)
        return None

    def _start_new_section(
        self, heading_match: re.Match[str], line_num: int
    ) -> dict[str, object]:
        """Start a new section from heading match."""
        level = len(heading_match.group(1))
        heading = heading_match.group(2).strip()

        return {
            "heading": heading,
            "level": level,
            "start_line": line_num,
            "end_line": None,
            "content": "",
        }

    def _close_final_section(
        self,
        current_section: dict[str, object],
        sections: list[dict[str, object]],
        lines: list[str],
    ) -> list[dict[str, object]]:
        """Close the final section."""
        start_line_val = current_section.get("start_line")
        if isinstance(start_line_val, int):
            current_section["end_line"] = len(lines)
            current_section["content"] = "\n".join(lines[start_line_val - 1 :])
            sections.append(current_section)

        return sections

    async def should_split_file(
        self,
        file_path: str,  # noqa: ARG002
        content: str,  # noqa: ARG002
        token_count: int,
        sections: list[dict[str, object]],
    ) -> tuple[bool, list[str]]:
        """
        Determine if a file should be split.

        Analyzes multiple criteria including size, section count,
        and structural complexity.

        Args:
            file_path: Path to the file
            content: File content
            token_count: Number of tokens in file
            sections: Parsed sections from file

        Returns:
            Tuple of (should_split boolean, list of reasons)
        """
        reasons: list[str] = []

        # Check file size
        if token_count > self.max_file_size:
            reasons.append(f"File exceeds recommended size ({token_count} tokens)")

        # Check number of sections
        if len(sections) > self.max_sections:
            reasons.append(f"File has too many sections ({len(sections)} sections)")

        # Check section complexity
        avg_section_size = token_count / len(sections) if sections else 0
        if avg_section_size > 1000 and len(sections) > 5:
            reasons.append("Sections are large and numerous")

        # Check for logical divisions (multiple top-level sections)
        top_level_sections = [s for s in sections if s["level"] == 1]
        if len(top_level_sections) > 3:
            reasons.append(
                f"Multiple distinct topics ({len(top_level_sections)} top-level sections)"
            )

        should_split = len(reasons) > 0

        return should_split, reasons

    def determine_split_strategy(
        self, token_count: int, section_count: int, sections: list[dict[str, object]]
    ) -> str:
        """
        Determine the best split strategy.

        Analyzes file characteristics to recommend the optimal approach
        for splitting.

        Args:
            token_count: Total tokens in file
            section_count: Number of sections
            sections: Parsed sections

        Returns:
            Strategy name: "by_topics", "by_size", or "by_sections"
        """
        # Check for multiple top-level sections (topic-based split)
        top_level_sections = [s for s in sections if s["level"] == 1]
        if len(top_level_sections) > 3:
            return "by_topics"

        # Check if file is too large (size-based split)
        if token_count > self.max_file_size * 1.5:
            return "by_size"

        # Check if too many sections (section-based split)
        if section_count > self.max_sections:
            return "by_sections"

        # Default to section-based
        return "by_sections"

    def calculate_section_independence(
        self,
        section: dict[str, object],
        all_sections: list[dict[str, object]],
        full_content: str,
    ) -> float:
        """
        Calculate how independent a section is.

        Evaluates internal references, content structure, and
        self-containment to score independence.

        Args:
            section: Section to evaluate
            all_sections: All sections in file
            full_content: Full file content

        Returns:
            Independence score (0.0 - 1.0)
        """
        independence_score = 0.5  # Base score

        content = cast(str, section["content"])

        # Check for internal references (links to other sections)
        internal_refs = len(re.findall(r"\[.*?\]\(#.*?\)", content))
        if internal_refs == 0:
            independence_score += 0.2
        elif internal_refs <= 2:
            independence_score += 0.1

        # Check for self-contained content (definitions, explanations)
        has_code_blocks = "```" in content
        has_lists = bool(re.search(r"^\s*[-*+]\s", content, re.MULTILINE))
        has_headings = bool(re.search(r"^#{2,6}\s", content, re.MULTILINE))

        if has_code_blocks:
            independence_score += 0.1
        if has_lists:
            independence_score += 0.1
        if has_headings:
            independence_score += 0.1

        return min(independence_score, 1.0)

    def calculate_group_independence(
        self,
        group_sections: list[dict[str, object]],
        all_sections: list[dict[str, object]],
        full_content: str,
    ) -> float:
        """
        Calculate independence score for a group of sections.

        Args:
            group_sections: Sections in the group
            all_sections: All sections in file
            full_content: Full file content

        Returns:
            Average independence score for the group
        """
        if not group_sections:
            return 0.0

        # Average independence of individual sections
        scores = [
            self.calculate_section_independence(s, all_sections, full_content)
            for s in group_sections
        ]

        return sum(scores) / len(scores)

    def group_related_sections(
        self, sections: list[dict[str, object]]
    ) -> dict[str, list[dict[str, object]]]:
        """
        Group related sections together.

        Uses heading hierarchy to identify related content that
        should stay together.

        Args:
            sections: List of sections to group

        Returns:
            Dictionary mapping group names to section lists
        """
        groups: dict[str, list[dict[str, object]]] = {}

        for section in sections:
            # Use top-level heading as group name
            if section["level"] == 1:
                group_name: str = cast(str, section["heading"])
                groups[group_name] = [section]
            elif section["level"] == 2 and groups:
                # Add to last group
                last_group: list[dict[str, object]] = list(groups.values())[-1]
                last_group.append(section)

        return groups
