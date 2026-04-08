"""Formatting helpers for memory-bank operations log entries."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from cortex.core.constants import OPERATIONS_LOG_MAX_ENTRIES


class OperationsLogType(StrEnum):
    """Allowed operation types for memory-bank operations log entries."""

    INGEST = "ingest"
    PLAN = "plan"
    COMMIT = "commit"
    REVIEW = "review"
    FIX = "fix"
    ANALYZE = "analyze"
    LINT = "lint"


def format_operations_log_entry(
    operation_type: OperationsLogType,
    title: str,
    summary: str | None = None,
    timestamp: datetime | None = None,
) -> str:
    """Build one parseable operations-log entry block.

    Format:
    ## [YYYY-MM-DDTHH:MM] {operation} | {title}
    {summary}
    """
    entry_time = timestamp or datetime.now()
    # AI: Minute precision keeps entries grep-friendly while avoiding noisy seconds.
    heading = (
        f"## [{entry_time.strftime('%Y-%m-%dT%H:%M')}] "
        f"{operation_type.value} | {title.strip()}"
    )
    normalized_summary = (summary or "").strip()
    if not normalized_summary:
        return f"{heading}\n\n"
    return f"{heading}\n\n{normalized_summary}\n\n"


def append_operations_log_entry(
    log_path: Path,
    operation_type: OperationsLogType,
    title: str,
    summary: str | None = None,
    timestamp: datetime | None = None,
) -> int:
    """Append one operations-log entry and return the heading line number."""
    header = "# Cortex Operations Log\n\n"
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    if not existing:
        existing = header
    elif not existing.startswith("# Cortex Operations Log"):
        # AI: Preserve existing content but normalize to canonical header for tooling.
        existing = f"{header}{existing.lstrip()}"
    # AI: Self-heal legacy entries so every heading stays markdown-lint compliant.
    existing = re.sub(r"(?<!\n)\n(## \[)", r"\n\n\1", existing)
    existing = _trim_to_recent_operations(existing.rstrip("\n") + "\n\n")
    entry = format_operations_log_entry(operation_type, title, summary, timestamp)
    line_inserted = len(existing.splitlines()) + 1
    log_path.parent.mkdir(parents=True, exist_ok=True)
    content = _trim_to_recent_operations(f"{existing}{entry}".rstrip("\n") + "\n")
    _ = log_path.write_text(content, encoding="utf-8")
    return line_inserted


def _trim_to_recent_operations(content: str) -> str:
    """Keep canonical header and only the most recent operations entries."""
    if not content.startswith("# Cortex Operations Log"):
        return content

    matches = list(re.finditer(r"^## \[", content, flags=re.MULTILINE))
    if len(matches) <= OPERATIONS_LOG_MAX_ENTRIES:
        return content

    keep_from = matches[-OPERATIONS_LOG_MAX_ENTRIES].start()
    return (
        f"# Cortex Operations Log\n\n{content[keep_from:].lstrip()}".rstrip("\n") + "\n"
    )
