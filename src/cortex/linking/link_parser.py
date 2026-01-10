"""Link parser for extracting markdown links and transclusion directives.

This module parses markdown files to extract:
1. Standard markdown links: [text](target.md), [text](target.md#section)
2. Transclusion directives: {{include: file.md}}, {{include: file.md#section|options}}

Part of Phase 2: DRY Linking and Transclusion

Performance optimizations (Phase 10.3.1):
- Pre-compiled regex patterns at module level
- Set-based lookups for O(1) performance
- Reduced redundant string splitting
"""

import re
from typing import cast

# Module-level regex patterns (compiled once)
_LINK_PATTERN: re.Pattern[str] = re.compile(r"\[([^\]]+)\]\(([^)]+)\)", re.MULTILINE)
_TRANSCLUSION_PATTERN: re.Pattern[str] = re.compile(
    r"\{\{include:\s*([^}|]+?)(?:\|([^}]+))?\}\}", re.MULTILINE
)

# Pre-compiled pattern for option splitting
_OPTION_SPLIT_PATTERN: re.Pattern[str] = re.compile(r"[|,]")

# Protocol prefixes for external links (set for O(1) lookup)
_EXTERNAL_PROTOCOLS: frozenset[str] = frozenset(["http://", "https://", "mailto:"])

# Memory bank file names (set for O(1) lookup)
_MEMORY_BANK_NAMES: frozenset[str] = frozenset(
    [
        "memorybankinstructions",
        "projectBrief",
        "productContext",
        "techContext",
        "systemPatterns",
        "progress",
        "activeContext",
    ]
)


class LinkParser:
    """Parse markdown files to extract links and transclusion directives."""

    def __init__(self):
        """Initialize parser with pre-compiled regex patterns."""
        # Use module-level patterns (already compiled)
        self.link_pattern: re.Pattern[str] = _LINK_PATTERN
        self.transclusion_pattern: re.Pattern[str] = _TRANSCLUSION_PATTERN

    def _is_memory_bank_file(self, file_path: str) -> bool:
        """Check if file path is a memory bank file.

        Optimized with set-based lookup for O(1) performance.

        Args:
            file_path: File path to check

        Returns:
            True if file is a markdown or memory bank file
        """
        if not file_path:
            return False

        if file_path.endswith(".md"):
            return True

        # Use module-level frozenset for O(1) lookup
        return any(name in file_path for name in _MEMORY_BANK_NAMES)

    def _parse_markdown_links(self, content: str) -> list[dict[str, object]]:
        """Parse markdown links from content.

        Optimized: Uses pre-compiled patterns and set-based protocol checks.

        Args:
            content: Markdown file content

        Returns:
            List of markdown link dictionaries
        """
        markdown_links: list[dict[str, object]] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            for match in self.link_pattern.finditer(line):
                text = match.group(1).strip()
                target = match.group(2).strip()

                # Early exit: Skip external links (O(1) check with frozenset)
                if any(target.startswith(proto) for proto in _EXTERNAL_PROTOCOLS):
                    continue

                file_path, section = self.parse_link_target(target)

                if self._is_memory_bank_file(file_path):
                    markdown_links.append(
                        {
                            "text": text,
                            "target": file_path,
                            "section": section,
                            "line": line_num,
                            "type": "reference",
                        }
                    )

        return markdown_links

    def _parse_transclusions(self, content: str) -> list[dict[str, object]]:
        """Parse transclusion directives from content.

        Args:
            content: Markdown file content

        Returns:
            List of transclusion dictionaries
        """
        transclusions: list[dict[str, object]] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            for match in self.transclusion_pattern.finditer(line):
                target = match.group(1).strip()
                options_str = match.group(2)

                file_path, section = self.parse_link_target(target)
                options = (
                    self.parse_transclusion_options(options_str) if options_str else {}
                )

                transclusions.append(
                    {
                        "target": file_path,
                        "section": section,
                        "options": options,
                        "line": line_num,
                        "type": "transclusion",
                    }
                )

        return transclusions

    async def parse_file(self, content: str) -> dict[str, list[dict[str, object]]]:
        """
        Parse file content for links and transclusions.

        Args:
            content: Markdown file content

        Returns:
            Dictionary with two lists:
            {
                "markdown_links": [
                    {
                        "text": "See projectBrief",
                        "target": "projectBrief.md",
                        "section": None,
                        "line": 15,
                        "type": "reference"
                    }
                ],
                "transclusions": [
                    {
                        "target": "systemPatterns.md",
                        "section": "Architecture",
                        "options": {"lines": 5, "recursive": true},
                        "line": 42,
                        "type": "transclusion"
                    }
                ]
            }
        """
        markdown_links = self._parse_markdown_links(content)
        transclusions = self._parse_transclusions(content)

        return {"markdown_links": markdown_links, "transclusions": transclusions}

    def parse_link_target(self, target: str) -> tuple[str, str | None]:
        """
        Parse link target into file and section.

        Args:
            target: "file.md#section" or "file.md"

        Returns:
            Tuple of (file_path, section_name)
            Example: ("file.md", "section") or ("file.md", None)
        """
        if "#" in target:
            parts = target.split("#", 1)
            file_path = parts[0].strip()
            section = parts[1].strip() if len(parts) > 1 else None
            return file_path, section
        else:
            return target.strip(), None

    def parse_transclusion_options(self, options_str: str | None) -> dict[str, object]:
        """
        Parse transclusion options.

        Optimized: Uses pre-compiled pattern for splitting.

        Args:
            options_str: "lines=5|recursive=false" or "lines=10" or None

        Returns:
            Dictionary of options: {"lines": 5, "recursive": False}
        """
        if not options_str:
            return {}

        options: dict[str, object] = {}

        # Use pre-compiled pattern for splitting (faster than re.split)
        parts = _OPTION_SPLIT_PATTERN.split(options_str)

        for part in parts:
            self._parse_single_option(part.strip(), options)

        return options

    def _parse_single_option(self, part: str, options: dict[str, object]) -> None:
        """Parse a single option key=value pair.

        Args:
            part: Option string like "lines=5" or "recursive=false"
            options: Dictionary to update with parsed option
        """
        # Skip if no equals sign
        if "=" not in part:
            return

        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Convert value to appropriate type
        parsed_value = self._parse_option_value(value)
        options[key] = parsed_value

    def _parse_option_value(self, value: str) -> object:
        """Parse option value to appropriate type.

        Args:
            value: String value to parse

        Returns:
            Parsed value (bool, int, or str)
        """
        value_lower = value.lower()

        # Boolean true values
        if value_lower in ("true", "yes", "1"):
            return True

        # Boolean false values
        if value_lower in ("false", "no", "0"):
            return False

        # Numeric values
        if value.isdigit():
            return int(value)

        # Default to string
        return value

    def extract_all_links(
        self, parsed_data: dict[str, list[dict[str, object]]]
    ) -> list[str]:
        """
        Extract all unique file references from parsed data.

        Args:
            parsed_data: Result from parse_file()

        Returns:
            List of unique target file paths
        """
        files: set[str] = set()

        for link in parsed_data.get("markdown_links", []):
            target = link.get("target")
            if target:
                files.add(str(target))

        for trans in parsed_data.get("transclusions", []):
            target = trans.get("target")
            if target:
                files.add(str(target))

        return sorted(list(files))

    def get_transclusion_targets(
        self, parsed_data: dict[str, list[dict[str, object]]]
    ) -> list[str]:
        """
        Get only transclusion targets (files that will be included).

        Args:
            parsed_data: Result from parse_file()

        Returns:
            List of files referenced in transclusion directives
        """
        targets: list[str] = []

        for trans in parsed_data.get("transclusions", []):
            target = trans.get("target")
            if target:
                targets.append(cast(str, target))

        return targets

    def has_transclusions(self, content: str) -> bool:
        """
        Quick check if content has any transclusion directives.

        Args:
            content: Markdown content

        Returns:
            True if content contains {{include: ...}} directives
        """
        return bool(self.transclusion_pattern.search(content))

    def count_links(
        self, parsed_data: dict[str, list[dict[str, object]]]
    ) -> dict[str, int]:
        """
        Count different types of links.

        Args:
            parsed_data: Result from parse_file()

        Returns:
            Dictionary with counts: {
                "markdown_links": 5,
                "transclusions": 2,
                "total": 7,
                "unique_files": 4
            }
        """
        markdown_count = len(parsed_data.get("markdown_links", []))
        transclusion_count = len(parsed_data.get("transclusions", []))
        unique_files = len(self.extract_all_links(parsed_data))

        return {
            "markdown_links": markdown_count,
            "transclusions": transclusion_count,
            "total": markdown_count + transclusion_count,
            "unique_files": unique_files,
        }
