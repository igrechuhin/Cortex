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

from cortex.core.models import JsonValue, ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import (
    IndexedRuleModel,
    IndexingResultModel,
    IndexingSkipResultModel,
    RuleSectionModel,
    RulesManagerStatusModel,
)

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

        # Track indexed rules (stored as IndexedRuleModel for type safety)
        self.rules_index: dict[str, IndexedRuleModel] = {}
        self.last_index_time: datetime | None = None
        self.rules_content_hashes: dict[str, str] = {}

        # Auto-reindexing task
        self.reindex_task: asyncio.Task[None] | None = None

    async def index_rules(self, rules_folder: str, force: bool = False) -> ModelDict:
        """
        Index all rules files from the specified folder.

        Args:
            rules_folder: Relative path to rules folder
            force: Force reindexing even if recently indexed

        Returns:
            Indexing results model
        """
        skip_result = self._check_skip_indexing(force)
        if skip_result:
            return cast(ModelDict, skip_result.model_dump(mode="json"))

        rules_path = self.project_root / rules_folder
        if not rules_path.exists():
            error = f"Rules folder not found: {rules_folder}"
            return {
                "status": "error",
                "rules_folder": rules_folder,
                "error": error,
                "message": error,
                "errors": [error],
            }

        rule_files = self.find_rule_files(rules_path)
        indexing_results = await self._index_rule_files(rule_files)
        self.last_index_time = datetime.now()

        return self._build_indexing_response(rules_folder, rule_files, indexing_results)

    def _check_skip_indexing(self, force: bool) -> IndexingSkipResultModel | None:
        """Check if indexing should be skipped.

        Args:
            force: Whether to force reindexing

        Returns:
            Skip response model or None
        """
        if not force and self.last_index_time:
            time_since_last = datetime.now() - self.last_index_time
            if time_since_last < self.reindex_interval:
                return IndexingSkipResultModel(
                    status="skipped",
                    message="Recently indexed",
                    last_indexed=self.last_index_time.isoformat(),
                    next_index_in_seconds=int(
                        (self.reindex_interval - time_since_last).total_seconds()
                    ),
                )
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
        result: IndexingResultModel,
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
        status = result.status
        # Dispatch table for status categorization
        status_handlers: dict[str, Callable[[], None]] = {
            "indexed": lambda: (
                indexed_files.append(result.file_key) if result.file_key else None
            ),
            "updated": lambda: (
                updated_files.append(result.file_key) if result.file_key else None
            ),
            "unchanged": lambda: (
                unchanged_files.append(result.file_key) if result.file_key else None
            ),
            "error": lambda: errors.append(result.error) if result.error else None,
        }

        handler = status_handlers.get(status)
        if handler:
            handler()

    async def _index_single_rule_file(self, file_path: Path) -> IndexingResultModel:
        """Index a single rule file.

        Args:
            file_path: Path to rule file

        Returns:
            Indexing result model
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            file_key = str(file_path.relative_to(self.project_root))

            status = self._determine_indexing_status(file_key, content_hash)
            if status == "unchanged":
                return IndexingResultModel(status="unchanged", file_key=file_key)

            self._index_rule_file_content(file_path, file_key, content, content_hash)
            return IndexingResultModel(status=status, file_key=file_key)

        except Exception as e:
            return IndexingResultModel(
                status="error",
                error=f"Error indexing {file_path}: {str(e)}",
            )

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

        # Store as IndexedRuleModel for type safety
        self.rules_index[file_key] = IndexedRuleModel(
            path=str(file_path),
            relative_path=file_key,
            content=content,
            content_hash=content_hash,
            token_count=token_count,
            sections=sections,
            indexed_at=datetime.now().isoformat(),
            file_size=len(content.encode("utf-8")),
        )

        self.rules_content_hashes[file_key] = content_hash

    def _build_indexing_response(
        self,
        rules_folder: str,
        rule_files: list[Path],
        indexing_results: dict[str, list[str]],
    ) -> ModelDict:
        """Build indexing response.

        Args:
            rules_folder: Rules folder path
            rule_files: List of rule files
            indexing_results: Indexing results

        Returns:
            Response model
        """
        indexed = indexing_results["indexed"]
        updated = indexing_results["updated"]
        unchanged = indexing_results["unchanged"]
        errors = indexing_results["errors"]

        counts = self._calculate_indexing_counts(indexed, updated, unchanged)
        json_data = self._convert_to_json(indexed, updated, unchanged, errors)
        return self._build_response_dict(rules_folder, rule_files, counts, json_data)

    def _calculate_indexing_counts(
        self,
        indexed: list[str],
        updated: list[str],
        unchanged: list[str],
    ) -> dict[str, int]:
        """Calculate indexing counts."""
        return {
            "indexed": len(indexed),
            "updated": len(updated),
            "unchanged": len(unchanged),
        }

    def _convert_to_json(
        self,
        indexed: list[str],
        updated: list[str],
        unchanged: list[str],
        errors: list[str],
    ) -> dict[str, list[JsonValue]]:
        """Convert lists to JSON-compatible format."""
        return {
            "indexed": cast(list[JsonValue], indexed),
            "updated": cast(list[JsonValue], updated),
            "unchanged": cast(list[JsonValue], unchanged),
            "errors": cast(list[JsonValue], errors),
        }

    def _build_response_dict(
        self,
        rules_folder: str,
        rule_files: list[Path],
        counts: dict[str, int],
        json_data: dict[str, list[JsonValue]],
    ) -> ModelDict:
        """Build final response dictionary."""
        indexed_count = counts["indexed"]
        updated_count = counts["updated"]
        return {
            "status": "success",
            "rules_folder": rules_folder,
            "total_files": len(rule_files),
            "indexed": indexed_count,
            "updated": updated_count,
            "unchanged": counts["unchanged"],
            "files_unchanged": counts["unchanged"],
            "indexed_files": json_data["indexed"],
            "updated_files": json_data["updated"],
            "unchanged_files": json_data["unchanged"],
            "errors": json_data["errors"],
            "message": (
                f"Indexed {indexed_count} new, {updated_count} updated, "
                f"{counts['unchanged']} unchanged files"
            ),
        }

    def find_rule_files(self, rules_path: Path) -> list[Path]:
        """
        Find all rule files in the rules folder.

        Searches for common rule file patterns including markdown,
        text files, and specific rule file names.

        Performance: O(directories + patterns) - optimized from
        O(directories × patterns²)
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

    def parse_rule_sections(self, content: str) -> list[RuleSectionModel]:
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
        sections: list[RuleSectionModel] = []
        current_section: str | None = None
        current_lines: list[str] = []

        for line in content.split("\n"):
            # Check for markdown heading using pre-compiled pattern
            heading_match = _HEADING_PATTERN.match(line)
            if heading_match:
                # Save previous section
                if current_section:
                    sections.append(
                        RuleSectionModel(
                            name=current_section,
                            content="\n".join(current_lines),
                            line_count=len(current_lines),
                        )
                    )

                # Start new section
                current_section = heading_match.group(1)
                current_lines = []
            elif current_section:
                current_lines.append(line)

        # Save last section
        if current_section:
            sections.append(
                RuleSectionModel(
                    name=current_section,
                    content="\n".join(current_lines),
                    line_count=len(current_lines),
                )
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
                from cortex.core.logging_config import logger

                logger.warning(f"Error in auto-reindex: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    def get_index(self) -> dict[str, IndexedRuleModel]:
        """
        Get the current rules index.

        Returns:
            Dictionary mapping file keys to indexed rule models
        """
        return dict(self.rules_index)

    def get_status(self) -> RulesManagerStatusModel:
        """
        Get indexer status information.

        Returns:
            Status model with indexing statistics
        """
        total_tokens = sum(r.token_count for r in self.rules_index.values())

        return RulesManagerStatusModel(
            enabled=True,  # Indexer is enabled if it exists
            rules_folder=None,  # Not stored in indexer
            indexed_files=len(self.rules_index),
            last_indexed=(
                self.last_index_time.isoformat() if self.last_index_time else None
            ),
            auto_reindex_enabled=self.reindex_task is not None
            and not self.reindex_task.done(),
            reindex_interval_minutes=self.reindex_interval.total_seconds() / 60,
            total_tokens=total_tokens,
        )
