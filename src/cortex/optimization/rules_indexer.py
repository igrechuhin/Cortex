"""
Rules indexing functionality for scanning and parsing rule files.

This module handles the scanning, parsing, and indexing of rule files
from configured directories. It tracks content changes and provides
incremental reindexing capabilities.

Performance optimizations (Phase 10.3.1 Day 5):
- Module-level rule file patterns (compiled once at import)
- Set-based pattern matching for O(1) lookups
- Optimized file scanning with reduced nested loops
- Early exit on duplicate detection
"""

import asyncio
import hashlib
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from cortex.core.token_counter import TokenCounter

# Module-level constants for performance (compiled once at import)
# Pre-define rule file patterns to avoid repeated construction
_RULE_FILE_PATTERNS: frozenset[str] = frozenset(
    [
        "*.md",
        "*.txt",
        "*.rules",
        "*rules*",
        ".cursorrules",
        ".ai-rules",
        ".clinerules",
    ]
)

# Pre-compiled regex for markdown heading detection
# Used in parse_rule_sections() - compiled once vs. every invocation
_HEADING_PATTERN: re.Pattern[str] = re.compile(r"^#+\s*(.+)$")


class RulesIndexer:
    """
    Index rule files from project folders.

    Handles file scanning, content parsing, change detection, and
    automatic reindexing of rule files.
    """

    def __init__(
        self,
        project_root: Path,
        token_counter: TokenCounter,
        reindex_interval_minutes: int = 30,
    ):
        """
        Initialize rules indexer.

        Args:
            project_root: Project root directory
            token_counter: Token counter for content analysis
            reindex_interval_minutes: How often to reindex rules (default: 30 min)
        """
        self.project_root: Path = Path(project_root)
        self.token_counter: TokenCounter = token_counter
        self.reindex_interval: timedelta = timedelta(minutes=reindex_interval_minutes)

        # Track indexed rules
        self.rules_index: dict[str, object] = {}
        self.last_index_time: datetime | None = None
        self.rules_content_hashes: dict[str, str] = {}

        # Auto-reindexing task
        self.reindex_task: asyncio.Task[None] | None = None

    async def index_rules(
        self, rules_folder: str, force: bool = False
    ) -> dict[str, object]:
        """
        Index all rules files from the specified folder.

        Args:
            rules_folder: Relative path to rules folder
            force: Force reindexing even if recently indexed

        Returns:
            Indexing results with statistics
        """
        skip_result = self._check_skip_indexing(force)
        if skip_result:
            return skip_result

        rules_path = self.project_root / rules_folder
        if not rules_path.exists():
            return {
                "status": "error",
                "error": f"Rules folder not found: {rules_folder}",
            }

        rule_files = self.find_rule_files(rules_path)
        indexing_results = await self._index_rule_files(rule_files)
        self.last_index_time = datetime.now()

        return self._build_indexing_response(rules_folder, rule_files, indexing_results)

    def _check_skip_indexing(self, force: bool) -> dict[str, object] | None:
        """Check if indexing should be skipped.

        Args:
            force: Whether to force reindexing

        Returns:
            Skip response or None
        """
        if not force and self.last_index_time:
            time_since_last = datetime.now() - self.last_index_time
            if time_since_last < self.reindex_interval:
                return {
                    "status": "skipped",
                    "message": "Recently indexed",
                    "last_indexed": self.last_index_time.isoformat(),
                    "next_index_in_seconds": int(
                        (self.reindex_interval - time_since_last).total_seconds()
                    ),
                }
        return None

    async def _index_rule_files(self, rule_files: list[Path]) -> dict[str, list[str]]:
        """Index all rule files.

        Reduced nesting: Extracted status categorization to helper method.
        Nesting: 2 levels (down from 5 levels)

        Args:
            rule_files: List of rule file paths

        Returns:
            Dictionary with indexed, updated, unchanged files and errors
        """
        indexed_files: list[str] = []
        updated_files: list[str] = []
        unchanged_files: list[str] = []
        errors: list[str] = []

        for file_path in rule_files:
            result = await self._index_single_rule_file(file_path)
            self._categorize_indexing_result(
                result, indexed_files, updated_files, unchanged_files, errors
            )

        return {
            "indexed": indexed_files,
            "updated": updated_files,
            "unchanged": unchanged_files,
            "errors": errors,
        }

    def _categorize_indexing_result(
        self,
        result: dict[str, object],
        indexed_files: list[str],
        updated_files: list[str],
        unchanged_files: list[str],
        errors: list[str],
    ) -> None:
        """Categorize indexing result into appropriate list.

        Args:
            result: Indexing result from _index_single_rule_file
            indexed_files: List to append newly indexed files
            updated_files: List to append updated files
            unchanged_files: List to append unchanged files
            errors: List to append error messages
        """
        status = cast(str, result["status"])
        # Dispatch table for status categorization
        status_handlers: dict[str, Callable[[], None]] = {
            "indexed": lambda: indexed_files.append(cast(str, result["file_key"])),
            "updated": lambda: updated_files.append(cast(str, result["file_key"])),
            "unchanged": lambda: unchanged_files.append(cast(str, result["file_key"])),
            "error": lambda: errors.append(cast(str, result["error"])),
        }

        handler = status_handlers.get(status)
        if handler:
            handler()

    async def _index_single_rule_file(self, file_path: Path) -> dict[str, object]:
        """Index a single rule file.

        Args:
            file_path: Path to rule file

        Returns:
            Indexing result dictionary
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            file_key = str(file_path.relative_to(self.project_root))

            status = self._determine_indexing_status(file_key, content_hash)
            if status == "unchanged":
                return {"status": "unchanged", "file_key": file_key}

            self._index_rule_file_content(file_path, file_key, content, content_hash)
            return {"status": status, "file_key": file_key}

        except Exception as e:
            return {
                "status": "error",
                "error": f"Error indexing {file_path}: {str(e)}",
            }

    def _determine_indexing_status(self, file_key: str, content_hash: str) -> str:
        """Determine indexing status for a file."""
        if file_key in self.rules_content_hashes:
            if self.rules_content_hashes[file_key] == content_hash:
                return "unchanged"
            return "updated"
        return "indexed"

    def _index_rule_file_content(
        self, file_path: Path, file_key: str, content: str, content_hash: str
    ) -> None:
        """Index rule file content."""
        token_count = self.token_counter.count_tokens(content)
        sections = self.parse_rule_sections(content)

        self.rules_index[file_key] = {
            "path": str(file_path),
            "relative_path": file_key,
            "content": content,
            "content_hash": content_hash,
            "token_count": token_count,
            "sections": sections,
            "indexed_at": datetime.now().isoformat(),
            "file_size": len(content.encode("utf-8")),
        }

        self.rules_content_hashes[file_key] = content_hash

    def _build_indexing_response(
        self,
        rules_folder: str,
        rule_files: list[Path],
        indexing_results: dict[str, list[str]],
    ) -> dict[str, object]:
        """Build indexing response.

        Args:
            rules_folder: Rules folder path
            rule_files: List of rule files
            indexing_results: Indexing results

        Returns:
            Response dictionary
        """
        indexed = indexing_results["indexed"]
        updated = indexing_results["updated"]
        unchanged = indexing_results["unchanged"]
        errors = indexing_results["errors"]

        return {
            "status": "success",
            "indexed_at": (
                self.last_index_time.isoformat() if self.last_index_time else None
            ),
            "rules_folder": rules_folder,
            "total_files": len(rule_files),
            "indexed": len(indexed),
            "updated": len(updated),
            "unchanged": len(unchanged),
            "errors": len(errors),
            "new_files": indexed,
            "updated_files": updated,
            "error_details": errors if errors else None,
        }

    def find_rule_files(self, rules_path: Path) -> list[Path]:
        """
        Find all rule files in the rules folder.

        Searches for common rule file patterns including markdown,
        text files, and specific rule file names.

        Performance: O(directories + patterns) - optimized from O(directories × patterns²)
        - Uses module-level _RULE_FILE_PATTERNS constant
        - Set-based duplicate detection (O(1) membership check)
        - Single pass through directories with batched pattern matching

        Args:
            rules_path: Path to rules folder

        Returns:
            List of rule file paths
        """
        # Use set for O(1) duplicate detection
        rule_files_set: set[Path] = set()

        # Search root directory with all patterns
        for pattern in _RULE_FILE_PATTERNS:
            rule_files_set.update(rules_path.glob(pattern))

        # Search subdirectories (one level) - single pass
        for subdir in rules_path.iterdir():
            if subdir.is_dir():
                for pattern in _RULE_FILE_PATTERNS:
                    rule_files_set.update(subdir.glob(pattern))

        # Sort once at the end
        return sorted(rule_files_set)

    def parse_rule_sections(self, content: str) -> list[dict[str, object]]:
        """
        Parse sections from rule content.

        Extracts markdown sections based on heading markers.

        Performance: O(n) where n = number of lines
        - Uses pre-compiled _HEADING_PATTERN regex (module-level constant)
        - Single pass through content

        Args:
            content: Rule file content

        Returns:
            List of sections with metadata (name, content, line_count)
        """
        sections: list[dict[str, object]] = []
        current_section: str | None = None
        current_lines: list[str] = []

        for line in content.split("\n"):
            # Check for markdown heading using pre-compiled pattern
            heading_match = _HEADING_PATTERN.match(line)
            if heading_match:
                # Save previous section
                if current_section:
                    sections.append(
                        {
                            "name": current_section,
                            "content": "\n".join(current_lines),
                            "line_count": len(current_lines),
                        }
                    )

                # Start new section
                current_section = heading_match.group(1)
                current_lines = []
            elif current_section:
                current_lines.append(line)

        # Save last section
        if current_section:
            sections.append(
                {
                    "name": current_section,
                    "content": "\n".join(current_lines),
                    "line_count": len(current_lines),
                }
            )

        return sections

    async def start_auto_reindex(self, rules_folder: str):
        """
        Start automatic re-indexing task.

        Args:
            rules_folder: Rules folder to reindex
        """
        if self.reindex_task and not self.reindex_task.done():
            return  # Already running

        self.reindex_task = asyncio.create_task(self._auto_reindex_loop(rules_folder))

    async def stop_auto_reindex(self):
        """Stop automatic re-indexing task."""
        if self.reindex_task and not self.reindex_task.done():
            _ = self.reindex_task.cancel()
            try:
                _ = await self.reindex_task
            except asyncio.CancelledError:
                pass

    async def _auto_reindex_loop(self, rules_folder: str):
        """
        Background task for automatic re-indexing.

        Args:
            rules_folder: Rules folder to reindex
        """
        while True:
            try:
                # Wait for the interval
                await asyncio.sleep(self.reindex_interval.total_seconds())

                # Reindex rules
                _ = await self.index_rules(rules_folder, force=False)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue
                print(f"Error in auto-reindex: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    def get_index(self) -> dict[str, dict[str, object]]:
        """
        Get the current rules index.

        Returns:
            Dictionary of indexed rules
        """
        result: dict[str, dict[str, object]] = {}
        for key, value in self.rules_index.items():
            if isinstance(value, dict):
                result[key] = value
        return result

    def get_status(self) -> dict[str, object]:
        """
        Get indexer status information.

        Returns:
            Status dictionary with indexing statistics
        """
        return {
            "indexed_files": len(self.rules_index),
            "last_indexed": (
                self.last_index_time.isoformat() if self.last_index_time else None
            ),
            "auto_reindex_enabled": self.reindex_task is not None
            and not self.reindex_task.done(),
            "reindex_interval_minutes": self.reindex_interval.total_seconds() / 60,
            "total_tokens": sum(
                (
                    (
                        int(token_count)
                        if isinstance(
                            token_count := cast(dict[str, object], r).get(
                                "token_count", 0
                            ),
                            (int, str),
                        )
                        and (isinstance(token_count, int) or str(token_count).isdigit())
                        else 0
                    )
                    if isinstance(r, dict)
                    else 0
                )
                for r in self.rules_index.values()
            ),
        }
