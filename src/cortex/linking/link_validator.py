"""Link validator for checking link integrity across Memory Bank files.

This module provides:
1. Link validation (file existence, section existence)
2. Broken link detection
3. Validation reports with suggestions
4. Batch validation for entire Memory Bank

Part of Phase 2: DRY Linking and Transclusion
"""

import re
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager

from .link_parser import LinkParser


class LinkValidator:
    """Validate link integrity across Memory Bank files."""

    def __init__(self, file_system: FileSystemManager, link_parser: LinkParser):
        """
        Initialize link validator.

        Args:
            file_system: File system manager for reading files
            link_parser: Link parser for extracting links
        """
        self.fs: FileSystemManager = file_system
        self.parser: LinkParser = link_parser

    async def _parse_file_links(self, file_path: Path) -> list[dict[str, object]]:
        """Parse all links from a file.

        Args:
            file_path: Path to file to parse

        Returns:
            List of all links (markdown + transclusions)
        """
        content, _ = await self.fs.read_file(file_path)
        parsed = await self.parser.parse_file(content)
        return parsed["markdown_links"] + parsed["transclusions"]

    async def _validate_link_file(
        self, link: dict[str, object]
    ) -> dict[str, object] | None:
        """Validate that a link's target file exists.

        Args:
            link: Link dictionary to validate

        Returns:
            Broken link dictionary if file missing, None if valid
        """
        target_file: str = cast(str, link["target"])
        section: str | None = cast(str | None, link.get("section"))
        line: int = cast(int, link["line"])
        link_type: str = cast(str, link["type"])

        file_exists = await self.check_file_exists(target_file)
        if not file_exists:
            suggestion = await self.generate_file_not_found_suggestion(target_file)
            return {
                "line": line,
                "target": target_file,
                "section": section,
                "type": link_type,
                "error": "File not found",
                "suggestion": suggestion,
            }
        return None

    async def _validate_link_section(
        self, link: dict[str, object]
    ) -> dict[str, object] | None:
        """Validate that a link's target section exists.

        Args:
            link: Link dictionary to validate

        Returns:
            Warning dictionary if section missing, None if valid
        """
        target_file: str = cast(str, link["target"])
        section: str | None = cast(str | None, link.get("section"))
        line: int = cast(int, link["line"])
        link_type: str = cast(str, link["type"])

        if not section:
            return None

        section_exists, available_sections = await self.check_section_exists(
            target_file, section
        )

        if not section_exists:
            return {
                "line": line,
                "target": target_file,
                "section": section,
                "type": link_type,
                "warning": "Section not found",
                "available_sections": available_sections,
                "suggestion": self.generate_section_suggestion(
                    section, available_sections
                ),
            }
        return None

    async def validate_file(self, file_path: Path) -> dict[str, object]:
        """
        Validate all links in a file.

        Args:
            file_path: Path to file to validate

        Returns:
            {
                "file": "activeContext.md",
                "valid_links": [...],
                "broken_links": [
                    {
                        "line": 15,
                        "target": "missing.md",
                        "section": None,
                        "error": "File not found",
                        "suggestion": "Create file or update link"
                    }
                ],
                "warnings": [
                    {
                        "line": 42,
                        "target": "file.md",
                        "section": "nonexistent",
                        "warning": "Section not found",
                        "available_sections": ["Intro", "Details"]
                    }
                ]
            }
        """
        all_links = await self._parse_file_links(file_path)

        valid_links: list[dict[str, object]] = []
        broken_links: list[dict[str, object]] = []
        warnings: list[dict[str, object]] = []

        for link in all_links:
            broken_link = await self._validate_link_file(link)
            if broken_link:
                broken_links.append(broken_link)
                continue

            warning = await self._validate_link_section(link)
            if warning:
                warnings.append(warning)
            else:
                valid_links.append(link)

        return {
            "file": file_path.name,
            "valid_links": valid_links,
            "broken_links": broken_links,
            "warnings": warnings,
        }

    async def validate_all(self, memory_bank_dir: Path) -> dict[str, object]:
        """
        Validate all links in all Memory Bank files.

        Args:
            memory_bank_dir: Path to memory-bank directory

        Returns:
            {
                "files_checked": 7,
                "total_links": 45,
                "valid_links": 42,
                "broken_links": 3,
                "warnings": 2,
                "validation_errors": [...],
                "validation_warnings": [...],
                "by_file": {
                    "activeContext.md": {...},
                    ...
                }
            }
        """
        md_files = list(memory_bank_dir.glob("*.md"))
        stats = self._initialize_validation_stats()

        for file_path in md_files:
            await self._process_file_validation(file_path, stats)

        return self._build_validation_result(stats)

    async def check_file_exists(self, target_file: str) -> bool:
        """
        Check if target file exists.

        Args:
            target_file: Name of target file (e.g., "projectBrief.md")

        Returns:
            True if file exists
        """
        memory_bank_dir = self.fs.memory_bank_dir
        target_path = memory_bank_dir / target_file

        return target_path.exists() and target_path.is_file()

    async def check_section_exists(
        self, target_file: str, section_heading: str
    ) -> tuple[bool, list[str]]:
        """
        Check if section exists in file.

        Args:
            target_file: Name of target file
            section_heading: Heading to find

        Returns:
            Tuple of (exists: bool, available_sections: list[str])
        """
        memory_bank_dir = self.fs.memory_bank_dir
        target_path = memory_bank_dir / target_file

        if not target_path.exists():
            return False, []

        # Read file and extract all headings
        content, _ = await self.fs.read_file(target_path)
        headings = self.extract_headings(content)

        # Check if section exists (case-insensitive)
        section_exists = any(h.lower() == section_heading.lower() for h in headings)

        return section_exists, headings

    def extract_headings(self, content: str) -> list[str]:
        """
        Extract all markdown headings from content.

        Args:
            content: Markdown content

        Returns:
            List of heading texts (without # symbols)
        """
        headings: list[str] = []
        lines = content.split("\n")

        for line in lines:
            # Match heading with any number of #
            heading_match = re.match(r"^(#+)\s+(.+)$", line.strip())
            if heading_match:
                heading_text = heading_match.group(2).strip()
                headings.append(heading_text)

        return headings

    async def generate_file_not_found_suggestion(self, target_file: str) -> str:
        """
        Generate suggestion for missing file.

        Args:
            target_file: Missing file name

        Returns:
            Suggestion text
        """
        # Check if similar files exist
        memory_bank_dir = self.fs.memory_bank_dir
        all_files = [f.name for f in memory_bank_dir.glob("*.md")]

        # Simple similarity check (could be improved with fuzzy matching)
        similar_files = [
            f for f in all_files if self.similarity_score(target_file, f) > 0.5
        ]

        if similar_files:
            return f"Did you mean: {', '.join(similar_files[:3])}?"
        else:
            return f"Create '{target_file}' or update the link"

    def generate_section_suggestion(
        self, missing_section: str, available_sections: list[str]
    ) -> str:
        """
        Generate suggestion for missing section.

        Args:
            missing_section: Section that wasn't found
            available_sections: List of available sections

        Returns:
            Suggestion text
        """
        if not available_sections:
            return "File has no sections"

        # Find similar sections
        similar: list[str] = []
        for section in available_sections:
            if self.similarity_score(missing_section, section) > 0.5:
                similar.append(section)

        if similar:
            return f"Did you mean: {', '.join(similar[:3])}?"
        else:
            return f"Available sections: {', '.join(available_sections[:5])}"

    def similarity_score(self, str1: str, str2: str) -> float:
        """
        Calculate simple similarity score between two strings.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score between 0.0 and 1.0
        """
        str1_lower = str1.lower()
        str2_lower = str2.lower()

        # Check if one contains the other
        if str1_lower in str2_lower or str2_lower in str1_lower:
            return 0.8

        # Check common prefix
        common_prefix_len = 0
        for c1, c2 in zip(str1_lower, str2_lower, strict=False):
            if c1 == c2:
                common_prefix_len += 1
            else:
                break

        if common_prefix_len > 0:
            return common_prefix_len / max(len(str1), len(str2))

        return 0.0

    def _generate_report_summary(
        self, validation_result: dict[str, object]
    ) -> list[str]:
        """Generate summary section of validation report.

        Args:
            validation_result: Result from validate_all()

        Returns:
            List of summary report lines
        """
        report: list[str] = []
        report.append("# Link Validation Report\n")

        files_checked = cast(int, validation_result["files_checked"])
        total_links = cast(int, validation_result["total_links"])
        valid_links = cast(int, validation_result["valid_links"])
        broken_links = cast(int, validation_result["broken_links"])
        warnings = cast(int, validation_result["warnings"])

        report.append(f"Files checked: {files_checked}")
        report.append(f"Total links: {total_links}")
        report.append(f"Valid links: {valid_links}")
        report.append(f"Broken links: {broken_links}")
        report.append(f"Warnings: {warnings}\n")

        return report

    def _generate_broken_links_section(
        self, validation_result: dict[str, object]
    ) -> list[str]:
        """Generate broken links section of validation report.

        Args:
            validation_result: Result from validate_all()

        Returns:
            List of broken links report lines
        """
        report: list[str] = []
        validation_errors = cast(
            list[dict[str, object]], validation_result.get("validation_errors", [])
        )

        if validation_errors:
            report.append("## Broken Links\n")
            for error in validation_errors:
                error_dict: dict[str, object] = error
                section = cast(str | None, error_dict.get("section"))
                section_part = f"#{section}" if section else ""
                file_name = cast(str, error_dict["file"])
                line = cast(int, error_dict["line"])
                target = cast(str, error_dict["target"])
                error_msg = cast(str, error_dict["error"])
                suggestion = cast(str, error_dict["suggestion"])

                report.append(
                    f"- {file_name}:{line} - "
                    + f"{target}{section_part} "
                    + f"({error_msg})"
                )
                report.append(f"  → {suggestion}\n")

        return report

    def _generate_warnings_section(
        self, validation_result: dict[str, object]
    ) -> list[str]:
        """Generate warnings section of validation report.

        Args:
            validation_result: Result from validate_all()

        Returns:
            List of warnings report lines
        """
        report: list[str] = []
        validation_warnings = cast(
            list[dict[str, object]], validation_result.get("validation_warnings", [])
        )

        if validation_warnings:
            report.append("## Warnings\n")
            for warning in validation_warnings:
                warning_dict: dict[str, object] = warning
                file_name = cast(str, warning_dict["file"])
                line = cast(int, warning_dict["line"])
                target = cast(str, warning_dict["target"])
                section = cast(str, warning_dict["section"])
                warning_msg = cast(str, warning_dict["warning"])
                suggestion = cast(str, warning_dict["suggestion"])

                report.append(
                    f"- {file_name}:{line} - "
                    + f"{target}#{section} "
                    + f"({warning_msg})"
                )
                report.append(f"  → {suggestion}\n")

        return report

    def generate_report(self, validation_result: dict[str, object]) -> str:
        """
        Generate human-readable validation report.

        Args:
            validation_result: Result from validate_all()

        Returns:
            Formatted report string
        """
        report: list[str] = []
        report.extend(self._generate_report_summary(validation_result))
        report.extend(self._generate_broken_links_section(validation_result))
        report.extend(self._generate_warnings_section(validation_result))
        return "\n".join(report)

    def _initialize_validation_stats(self) -> dict[str, object]:
        """Initialize validation statistics dictionary."""
        return {
            "files_checked": 0,
            "total_links": 0,
            "valid_links_count": 0,
            "all_broken_links": [],
            "all_warnings": [],
            "by_file": {},
        }

    async def _process_file_validation(
        self, file_path: Path, stats: dict[str, object]
    ) -> None:
        """Process validation for a single file and update stats."""
        try:
            validation_result = await self.validate_file(file_path)
            by_file = cast(dict[str, object], stats["by_file"])
            by_file[file_path.name] = validation_result

            stats["files_checked"] = cast(int, stats["files_checked"]) + 1
            self._update_link_counts(validation_result, stats, file_path.name)
            self._collect_broken_links_and_warnings(
                validation_result, stats, file_path.name
            )

        except Exception as e:
            by_file = cast(dict[str, object], stats["by_file"])
            by_file[file_path.name] = {"error": str(e)}

    def _build_validation_result(self, stats: dict[str, object]) -> dict[str, object]:
        """Build final validation result dictionary."""
        all_broken_links = cast(list[dict[str, object]], stats["all_broken_links"])
        all_warnings = cast(list[dict[str, object]], stats["all_warnings"])

        return {
            "files_checked": stats["files_checked"],
            "total_links": stats["total_links"],
            "valid_links": stats["valid_links_count"],
            "broken_links": len(all_broken_links),
            "warnings": len(all_warnings),
            "validation_errors": all_broken_links,
            "validation_warnings": all_warnings,
            "by_file": stats["by_file"],
        }

    def _update_link_counts(
        self,
        validation_result: dict[str, object],
        stats: dict[str, object],
        file_name: str,
    ) -> None:
        """Update link counts in stats from validation result."""
        valid_links_list = cast(
            list[dict[str, object]], validation_result["valid_links"]
        )
        broken_links_list = cast(
            list[dict[str, object]], validation_result["broken_links"]
        )
        valid_count = len(valid_links_list)
        broken_count = len(broken_links_list)

        stats["total_links"] = (
            cast(int, stats["total_links"]) + valid_count + broken_count
        )
        stats["valid_links_count"] = cast(int, stats["valid_links_count"]) + valid_count

    def _collect_broken_links_and_warnings(
        self,
        validation_result: dict[str, object],
        stats: dict[str, object],
        file_name: str,
    ) -> None:
        """Collect broken links and warnings from validation result."""
        broken_links_list = cast(
            list[dict[str, object]], validation_result["broken_links"]
        )
        all_broken_links = cast(list[dict[str, object]], stats["all_broken_links"])
        for broken in broken_links_list:
            broken["file"] = file_name
            all_broken_links.append(broken)

        warnings_list = cast(list[dict[str, object]], validation_result["warnings"])
        all_warnings = cast(list[dict[str, object]], stats["all_warnings"])
        for warning in warnings_list:
            warning["file"] = file_name
            all_warnings.append(warning)
