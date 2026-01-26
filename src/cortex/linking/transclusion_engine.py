"""Transclusion engine for resolving and including content from other files.

This module handles:
1. Resolving {{include: ...}} directives recursively
2. Content caching for performance
3. Circular dependency detection
4. Section extraction
5. Depth limiting

Part of Phase 2: DRY Linking and Transclusion
"""

import re
from typing import cast

from cortex.core.exceptions import MemoryBankError
from cortex.core.file_system import FileSystemManager
from cortex.core.models import JsonValue, ModelDict

from .link_parser import LinkParser
from .models import TransclusionOptions


def _coerce_transclusion_options(
    options: TransclusionOptions | ModelDict | None,
) -> TransclusionOptions:
    if options is None:
        return TransclusionOptions()
    if isinstance(options, TransclusionOptions):
        return options

    lines_raw = options.get("lines")
    lines = int(lines_raw) if isinstance(lines_raw, int) else None
    recursive_raw = options.get("recursive")
    recursive = bool(recursive_raw) if isinstance(recursive_raw, bool) else True
    return TransclusionOptions(lines=lines, recursive=recursive)


class CircularDependencyError(MemoryBankError):
    """Raised when circular transclusion dependency is detected."""

    pass


class MaxDepthExceededError(MemoryBankError):
    """Raised when transclusion depth exceeds maximum."""

    pass


class TransclusionEngine:
    """Resolve and include content from transclusion directives."""

    def __init__(
        self,
        file_system: FileSystemManager,
        link_parser: LinkParser,
        max_depth: int = 5,
        cache_enabled: bool = True,
    ):
        """
        Initialize transclusion engine.

        Args:
            file_system: File system manager for reading files
            link_parser: Link parser for detecting transclusions
            max_depth: Maximum transclusion depth (default: 5)
            cache_enabled: Enable content caching (default: True)
        """
        self.fs: FileSystemManager = file_system
        self.parser: LinkParser = link_parser
        self.max_depth: int = max_depth
        self.cache_enabled: bool = cache_enabled

        # Cache: key = (file, section, options_tuple), value = resolved content
        self.cache: dict[tuple[str, str, tuple[tuple[str, JsonValue], ...]], str] = {}
        self.cache_hits: int = 0
        self.cache_misses: int = 0

        # Resolution stack for circular dependency detection
        self.resolution_stack: list[str] = []

    async def resolve_content(
        self, content: str, source_file: str, depth: int = 0
    ) -> str:
        """
        Resolve all transclusions in content.

        Args:
            content: Markdown content with transclusion directives
            source_file: Name of source file (for relative paths and error messages)
            depth: Current recursion depth

        Returns:
            Content with transclusions resolved

        Raises:
            CircularDependencyError: If circular transclusion detected
            MaxDepthExceededError: If max depth exceeded
        """
        self._validate_depth(depth, source_file)

        if not self.parser.has_transclusions(content):
            return content

        parsed: ModelDict = await self.parser.parse_file(content)
        transclusions_raw: JsonValue = parsed.get("transclusions", [])
        if not isinstance(transclusions_raw, list) or not transclusions_raw:
            return content

        self._validate_depth_with_transclusions(depth, source_file)
        return await self._resolve_all_transclusions(
            content, cast(list[ModelDict], transclusions_raw), depth, source_file
        )

    def _validate_depth(self, depth: int, source_file: str) -> None:
        """Validate current depth is within limits."""
        if depth > self.max_depth:
            raise MaxDepthExceededError(
                f"Failed to resolve transclusion in '{source_file}': "
                + f"Maximum transclusion depth ({self.max_depth}) exceeded. "
                + "Cause: Too many nested {{include:}} directives. "
                + "Try: Reduce nesting depth, increase max_depth limit, "
                + "or reorganize content to avoid deep transclusion chains."
            )

    def _validate_depth_with_transclusions(self, depth: int, source_file: str) -> None:
        """Validate depth when transclusions need to be resolved."""
        if depth >= self.max_depth:
            raise MaxDepthExceededError(
                f"Failed to resolve transclusion in '{source_file}': "
                + f"Maximum transclusion depth ({self.max_depth}) exceeded. "
                + "Cause: Too many nested {{include:}} directives. "
                + "Try: Reduce nesting depth, increase max_depth limit, "
                + "or reorganize content to avoid deep transclusion chains."
            )

    async def _resolve_all_transclusions(
        self,
        content: str,
        transclusions: list[ModelDict],
        depth: int,
        source_file: str,
    ) -> str:
        """Resolve all transclusion directives in content."""
        resolved_content = content
        for trans in reversed(transclusions):  # Process from end to maintain positions
            resolved_content = await self._resolve_single_transclusion(
                resolved_content, trans, depth, source_file
            )
        return resolved_content

    async def _resolve_single_transclusion(
        self, content: str, trans: ModelDict, depth: int, source_file: str
    ) -> str:
        """Resolve a single transclusion directive in content."""
        target_file, section, options = self._parse_transclusion_params(trans)
        if target_file is None:
            return content

        if self.detect_circular_dependency(target_file):
            chain = " -> ".join(self.resolution_stack)
            raise CircularDependencyError(
                "Failed to resolve transclusion: Circular dependency detected. "
                + f"Cause: '{chain}' -> '{target_file}' forms a cycle. "
                + "Try: Remove one of the {{include:}} directives to break the cycle, "
                + "use section-level includes instead of full file includes, "
                + "or reorganize content to avoid circular references."
            )

        try:
            included_content = await self.resolve_transclusion(
                target_file=target_file,
                section=section,
                options=options,
                depth=depth,
                source_file=source_file,
            )
            return self._replace_directive_with_content(
                content, trans, included_content
            )
        except (CircularDependencyError, MaxDepthExceededError):
            raise
        except Exception as e:
            return self._replace_directive_with_error(content, trans, str(e))

    def _parse_transclusion_params(
        self, trans: ModelDict
    ) -> tuple[str | None, str | None, ModelDict | None]:
        """Parse transclusion parameters from directive."""
        target_raw = trans.get("target")
        target_file = target_raw if isinstance(target_raw, str) else None
        section_raw = trans.get("section")
        section = section_raw if isinstance(section_raw, str) else None
        options_raw = trans.get("options")
        options = options_raw if isinstance(options_raw, dict) else None
        return target_file, section, cast(ModelDict | None, options)

    def _replace_directive_with_content(
        self, content: str, trans: ModelDict, included_content: str
    ) -> str:
        """Replace transclusion directive with resolved content."""
        # Use full_syntax to match the exact directive
        full_syntax_raw = trans.get("full_syntax")
        if not isinstance(full_syntax_raw, str) or not full_syntax_raw:
            return content
        directive_pattern = re.escape(full_syntax_raw)
        return re.sub(directive_pattern, included_content, content, count=1)

    def _replace_directive_with_error(
        self, content: str, trans: ModelDict, error: str
    ) -> str:
        """Replace transclusion directive with error message."""
        error_msg = f"\n<!-- TRANSCLUSION ERROR: {error} -->\n"
        # Use full_syntax to match the exact directive
        full_syntax_raw = trans.get("full_syntax")
        if not isinstance(full_syntax_raw, str) or not full_syntax_raw:
            return content
        directive_pattern = re.escape(full_syntax_raw)
        return re.sub(directive_pattern, error_msg, content, count=1)

    async def resolve_transclusion(
        self,
        target_file: str,
        section: str | None = None,
        options: TransclusionOptions | ModelDict | None = None,
        depth: int = 0,
        source_file: str = "",
    ) -> str:
        """
        Resolve a single transclusion directive.

        Args:
            target_file: Target file name
            section: Optional section heading
            options: Transclusion options (lines, recursive, etc.)
            depth: Current recursion depth
            source_file: Source file (for error messages)

        Returns:
            Resolved content

        Raises:
            CircularDependencyError: If circular dependency detected
            FileNotFoundError: If target file not found
        """
        options_model = _coerce_transclusion_options(options)

        # Check cache first
        cached_result = self._check_cache(target_file, section, options_model)
        if cached_result is not None:
            return cached_result

        self._validate_transclusion(target_file, depth, source_file)
        self.resolution_stack.append(target_file)

        try:
            target_content = await self._read_and_process_target(
                target_file, section, options_model, depth, source_file
            )
            self._cache_result(target_file, section, options_model, target_content)
            return target_content
        finally:
            _ = self.resolution_stack.pop()

    def _check_cache(
        self, target_file: str, section: str | None, options: TransclusionOptions
    ) -> str | None:
        """Check cache for resolved transclusion."""
        cache_key = self.make_cache_key(target_file, section, options)
        if self.cache_enabled and cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        self.cache_misses += 1
        return None

    def _validate_transclusion(
        self, target_file: str, depth: int, source_file: str
    ) -> None:
        """Validate transclusion depth and circular dependencies."""
        if depth > self.max_depth:
            raise MaxDepthExceededError(
                f"Failed to resolve transclusion of '{target_file}' from '{source_file}': "
                + f"Maximum transclusion depth ({self.max_depth}) exceeded. "
                + "Cause: Too many nested {{include:}} directives. "
                + "Try: Reduce nesting depth, increase max_depth limit, "
                + "or reorganize content to avoid deep transclusion chains."
            )
        if self.detect_circular_dependency(target_file):
            chain = " -> ".join(self.resolution_stack)
            raise CircularDependencyError(
                "Failed to resolve transclusion: Circular dependency detected. "
                + f"Cause: '{chain}' -> '{target_file}' forms a cycle. "
                + "Try: Remove one of the {{include:}} directives to break the cycle, "
                + "use section-level includes instead of full file includes, "
                + "or reorganize content to avoid circular references."
            )

    async def _read_and_process_target(
        self,
        target_file: str,
        section: str | None,
        options: TransclusionOptions,
        depth: int,
        source_file: str,
    ) -> str:
        """Read target file and process content with options."""
        target_content = await self._read_target_file(target_file, source_file)
        target_content = self._apply_section_filter(target_content, section, options)
        target_content = await self._apply_recursive_resolution(
            target_content, target_file, options, depth
        )
        return target_content

    async def _read_target_file(self, target_file: str, source_file: str) -> str:
        """Read content from target file."""
        memory_bank_dir = self.fs.memory_bank_dir
        target_path = memory_bank_dir / target_file

        if not target_path.exists():
            raise FileNotFoundError(
                f"Failed to transclude '{target_file}' from '{source_file}': "
                + f"Target file not found at {target_path}. "
                + "Try: Check file name is correct (case-sensitive), "
                + "verify file exists in memory-bank directory, "
                + "or run initialize_memory_bank() to create missing files."
            )

        target_content, _ = await self.fs.read_file(target_path)
        return target_content

    def _apply_section_filter(
        self, content: str, section: str | None, options: TransclusionOptions
    ) -> str:
        """Apply section extraction or line limit."""
        if section:
            lines_limit = options.lines
            return self.extract_section(
                content=content, section_heading=section, lines_limit=lines_limit
            )
        elif options.lines is not None:
            lines = content.split("\n")
            return "\n".join(lines[: options.lines])
        return content

    async def _apply_recursive_resolution(
        self, content: str, target_file: str, options: TransclusionOptions, depth: int
    ) -> str:
        """Apply recursive transclusion if enabled."""
        if options.recursive and depth < self.max_depth:
            return await self.resolve_content(
                content=content, source_file=target_file, depth=depth + 1
            )
        return content

    def _cache_result(
        self,
        target_file: str,
        section: str | None,
        options: TransclusionOptions,
        content: str,
    ) -> None:
        """Cache resolved content."""
        if self.cache_enabled:
            cache_key = self.make_cache_key(target_file, section, options)
            self.cache[cache_key] = content

    def extract_section(
        self, content: str, section_heading: str, lines_limit: int | None = None
    ) -> str:
        """
        Extract a specific section from content.

        Args:
            content: Full file content
            section_heading: Heading to find (e.g., "Architecture")
            lines_limit: Optional limit on number of lines

        Returns:
            Section content (without the heading itself)

        Raises:
            ValueError: If section not found
        """
        lines = content.split("\n")
        section_start, section_level = self._find_section_heading(
            lines, section_heading
        )
        if section_start is None:
            self._raise_section_not_found_error(section_heading)
        # section_start is guaranteed to be int here due to check above
        assert section_start is not None
        section_end = self._find_section_end(lines, section_start, section_level)

        # Extract section content (skip the heading line itself)
        section_lines = lines[section_start + 1 : section_end]

        # Apply line limit if specified
        if lines_limit is not None:
            section_lines = section_lines[:lines_limit]

        return "\n".join(section_lines).strip()

    def _find_section_heading(
        self, lines: list[str], section_heading: str
    ) -> tuple[int | None, int | None]:
        """Find section heading in lines."""
        section_start = None
        section_level = None
        for i, line in enumerate(lines):
            heading_match = re.match(r"^(#+)\s+(.+)$", line.strip())
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                if heading_text.lower() == section_heading.lower():
                    section_start = i
                    section_level = level
                    break
        return section_start, section_level

    def _raise_section_not_found_error(self, section_heading: str) -> None:
        """Raise error when section not found."""
        raise ValueError(
            f"Failed to transclude section '{section_heading}': "
            + "Section heading not found in target file. "
            + "Try: Check the exact heading text including case and special characters, "
            + "list available sections with parse_file_links(), "
            + "or verify the section exists in the target file."
        )

    def _find_section_end(
        self, lines: list[str], section_start: int, section_level: int | None
    ) -> int:
        """Find end of section (next heading of same or higher level)."""
        # Early return if no section level specified
        if section_level is None:
            return len(lines)

        # Find next heading at same or higher level
        for i in range(section_start + 1, len(lines)):
            heading_match = re.match(r"^(#+)\s+", lines[i].strip())
            if not heading_match:
                continue

            level = len(heading_match.group(1))
            if level <= section_level:
                return i

        return len(lines)

    def detect_circular_dependency(self, target: str) -> bool:
        """
        Check if target is in resolution stack.

        Args:
            target: Target file being resolved

        Returns:
            True if circular dependency detected
        """
        return target in self.resolution_stack

    def clear_cache(self):
        """Clear resolved content cache."""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0

    def invalidate_cache_for_file(self, file_name: str):
        """
        Invalidate cache entries for a specific file.

        Args:
            file_name: Name of file that changed
        """
        keys_to_remove = [
            key
            for key in self.cache.keys()
            if key[0] == file_name  # key[0] is target_file
        ]

        for key in keys_to_remove:
            del self.cache[key]

    def get_cache_stats(self) -> dict[str, int | float]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0.0

        return {
            "entries": len(self.cache),
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
        }

    def make_cache_key(
        self,
        target_file: str,
        section: str | None,
        options: TransclusionOptions | ModelDict | None,
    ) -> tuple[str, str, tuple[tuple[str, JsonValue], ...]]:
        """Create cache key from transclusion parameters."""
        # Convert options model to sorted tuple for hashability
        # Normalize None section to empty string for cache key consistency
        section_normalized = section if section is not None else ""
        if options is not None:
            if isinstance(options, TransclusionOptions):
                options_dict = cast(
                    ModelDict, options.model_dump(exclude_none=True, mode="json")
                )
            else:
                options_dict = dict(options)

            options_filtered: ModelDict = {
                str(k): v for k, v in options_dict.items() if v is not None
            }
            options_tuple = tuple(sorted(options_filtered.items()))
        else:
            options_tuple = ()
        return (target_file, section_normalized, options_tuple)

    def build_directive_pattern(self, trans: ModelDict) -> str:
        """
        Build regex pattern to match the transclusion directive.

        Args:
            trans: Transclusion model from parser

        Returns:
            Regex pattern string (escaped full_syntax)
        """
        # For dict inputs, synthesize a robust pattern.
        full_syntax = str(trans.get("full_syntax", "") or "")
        if full_syntax:
            return re.escape(full_syntax)

        target = str(trans.get("target", "") or "")
        if not target:
            return ""

        section_raw = trans.get("section", None)
        section = (
            str(section_raw) if isinstance(section_raw, str) and section_raw else ""
        )

        pattern = r"\{\{include:\s*" + re.escape(target)
        if section:
            pattern += r"\#" + re.escape(section)
        pattern += r"\s*\}\}"
        return pattern
