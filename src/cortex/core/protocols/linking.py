#!/usr/bin/env python3
"""Linking and transclusion protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for link parsing, transclusion
resolution, and link validation, enabling structural subtyping for better
abstraction and reduced circular dependencies.
"""

from pathlib import Path
from typing import Protocol

from cortex.linking.models import LinkValidationResult


class LinkParserProtocol(Protocol):
    r"""Protocol for link parsing operations using structural subtyping (PEP 544).

    This protocol defines the interface for extracting markdown links and
    transclusion syntax from content. Link parsing is essential for building
    dependency graphs and validating references. A class implementing these
    methods automatically satisfies this protocol.

    Used by:
        - LinkParser: Regex-based markdown link and transclusion parser
        - DependencyGraph: For building dependency graph from links
        - LinkValidator: For extracting links to validate
        - TransclusionEngine: For finding transclusion targets

    Example implementation:
        ```python
        import re

        class SimpleLinkParser:
            def parse_markdown_links(self, content: str) -> list[dict[str, str]]:
                # Pattern: [text](target)
                pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
                links = []
                for match in re.finditer(pattern, content):
                    line_number = content[:match.start()].count('\n') + 1
                    links.append({
                        "text": match.group(1),
                        "target": match.group(2),
                        "line_number": str(line_number),
                    })
                return links

            def parse_transclusions(self, content: str) -> list[dict[str, str]]:
                # Pattern: {{include:path}}
                pattern = r'\{\{include:([^\}]+)\}\}'
                transclusions = []
                for match in re.finditer(pattern, content):
                    line_number = content[:match.start()].count('\n') + 1
                    transclusions.append({
                        "target": match.group(1).strip(),
                        "line_number": str(line_number),
                    })
                return transclusions

        # SimpleLinkParser automatically satisfies LinkParserProtocol
        ```

    Note:
        - Regex patterns must handle edge cases (nested brackets, etc.)
        - Line numbers enable precise error reporting
        - Both markdown links and transclusions are tracked
    """

    def parse_markdown_links(self, content: str) -> list[dict[str, str]]:
        """Parse markdown links from content.

        Args:
            content: Markdown content

        Returns:
            List of link dictionaries with text, target, line_number
        """
        ...

    def parse_transclusions(self, content: str) -> list[dict[str, str]]:
        """Parse transclusion syntax from content.

        Args:
            content: Content to parse

        Returns:
            List of transclusion dictionaries
        """
        ...


class TransclusionEngineProtocol(Protocol):
    """Protocol for transclusion resolution using structural subtyping (PEP 544).

    This protocol defines the interface for resolving transclusion syntax
    ({{include:path}}) by recursively including content from other files.
    Transclusion enables DRY (Don't Repeat Yourself) principles in documentation.
    A class implementing these methods automatically satisfies this protocol.

    Used by:
        - TransclusionEngine: Recursive transclusion resolver with cycle detection
        - ValidationTools: For validating fully-resolved content
        - ContextOptimizer: For getting complete file content with includes
        - MCP Tools: For serving resolved content to clients

    Example implementation:
        ```python
        class SimpleTransclusionEngine:
            def __init__(
                self,
                file_system: FileSystemProtocol,
                link_parser: LinkParserProtocol,
            ):
                self.file_system = file_system
                self.link_parser = link_parser
                self.cache = {}
                self.resolution_stack = []

            async def resolve_file(
                self, file_path: Path, max_depth: int | None = None
            ) -> str:
                # Check for circular dependencies
                if str(file_path) in self.resolution_stack:
                    raise CircularDependencyError(
                        f"Circular transclusion: {self.resolution_stack}"
                    )

                self.resolution_stack.append(str(file_path))
                try:
                    content, _ = await self.file_system.read_file(file_path)
                    transclusions = self.link_parser.parse_transclusions(content)

                    # Resolve each transclusion
                    for trans in transclusions:
                        target_path = file_path.parent / trans["target"]
                        included = await self.resolve_file(target_path, max_depth)
                        content = content.replace(
                            f"{{{{include:{trans['target']}}}}}", included
                        )

                    return content
                finally:
                    self.resolution_stack.pop()

            def clear_cache(self):
                self.cache.clear()

        # SimpleTransclusionEngine automatically satisfies TransclusionEngineProtocol
        ```

    Note:
        - Circular dependency detection prevents infinite recursion
        - Caching improves performance for repeated resolutions
        - Max depth limits recursion for safety
    """

    async def resolve_file(self, file_path: Path, max_depth: int | None = None) -> str:
        """Resolve all transclusions in a file.

        Args:
            file_path: Path to file
            max_depth: Maximum recursion depth

        Returns:
            Content with transclusions resolved

        Raises:
            CircularDependencyError: If circular transclusion detected
            FileNotFoundError: If target file not found
        """
        ...

    def clear_cache(self):
        """Clear transclusion cache."""
        ...


class LinkValidatorProtocol(Protocol):
    """Protocol for link validation using structural subtyping (PEP 544).

    This protocol defines the interface for validating markdown links and
    transclusions, ensuring all references point to existing files or valid
    URLs. A class implementing these methods automatically satisfies this
    protocol.

    Used by:
        - LinkValidator: Validates both internal links and external URLs
        - ValidationTools: For comprehensive memory bank validation
        - QualityMetrics: For calculating completeness scores
        - MCP Tools: For reporting broken links

    Example implementation:
        ```python
        class SimpleLinkValidator:
            def __init__(
                self,
                file_system: FileSystemProtocol,
                link_parser: LinkParserProtocol,
            ):
                self.file_system = file_system
                self.link_parser = link_parser

            async def validate_file_links(
                self, file_path: Path, memory_bank_path: Path
            ) -> LinkValidationResult:
                from cortex.linking.models import BrokenLinkInfo
                content, _ = await self.file_system.read_file(file_path)
                links = self.link_parser.parse_markdown_links(content)
                transclusions = self.link_parser.parse_transclusions(content)

                broken_links = []
                for link in links:
                    target_str = link.get("target", "")
                    if not target_str.startswith("http"):
                        # Validate internal link
                        target = memory_bank_path / target_str
                        if not await self.file_system.file_exists(target):
                            broken_links.append(BrokenLinkInfo(
                                target=target_str,
                                line_number=int(link.get("line_number", "0")) or 1,
                                link_type="markdown",
                                error="Target file does not exist",
                            ))

                broken_transclusions = []
                for trans in transclusions:
                    target_str = trans.get("target", "")
                    target = memory_bank_path / target_str
                    if not await self.file_system.file_exists(target):
                        broken_transclusions.append(BrokenLinkInfo(
                            target=target_str,
                            line_number=int(trans.get("line_number", "0")) or 1,
                            link_type="transclusion",
                            error="Target file does not exist",
                        ))

                return LinkValidationResult(
                    valid=len(broken_links) == 0 and len(broken_transclusions) == 0,
                    total_links=len(links) + len(transclusions),
                    valid_links=(
                        len(links) + len(transclusions)
                        - len(broken_links) - len(broken_transclusions)
                    ),
                    broken_links=broken_links,
                    broken_transclusions=broken_transclusions,
                )

        # SimpleLinkValidator automatically satisfies LinkValidatorProtocol
        ```

    Note:
        - Validates both relative and absolute paths
        - Distinguishes between internal links and external URLs
        - Reports line numbers for broken links
    """

    async def validate_file_links(
        self, file_path: Path, memory_bank_path: Path
    ) -> LinkValidationResult:
        """Validate all links in a file.

        Args:
            file_path: Path to file
            memory_bank_path: Path to memory bank directory

        Returns:
            Link validation result model
        """
        ...


__all__ = [
    "LinkParserProtocol",
    "TransclusionEngineProtocol",
    "LinkValidatorProtocol",
]
