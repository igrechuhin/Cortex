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


def _disambiguate_operations_log_title(
    existing: str,
    operation_type: OperationsLogType,
    ts_display: str,
    base_title: str,
) -> str:
    """Return ``base_title`` or ``base_title ·N`` so the heading stays unique (MD024)."""
    escaped_prefix = re.escape(f"## [{ts_display}] {operation_type.value} | ")
    escaped_title = re.escape(base_title)
    pattern = re.compile(
        "^" + escaped_prefix + escaped_title + r"( ·(\d+))?\s*$",
        flags=re.MULTILINE,
    )
    max_ordinal = 0
    for match in pattern.finditer(existing):
        suffix = match.group(2)
        max_ordinal = max(max_ordinal, int(suffix) if suffix is not None else 1)
    if max_ordinal == 0:
        return base_title
    return f"{base_title} ·{max_ordinal + 1}"


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
    ts_display = entry_time.strftime("%Y-%m-%dT%H:%M")
    heading = f"## [{ts_display}] {operation_type.value} | {title.strip()}"
    normalized_summary = (summary or "").strip()
    if not normalized_summary:
        return f"{heading}\n\n"
    return f"{heading}\n\n{normalized_summary}\n\n"


def _compose_append_entry(
    existing: str,
    operation_type: OperationsLogType,
    title: str,
    summary: str | None,
    timestamp: datetime | None,
) -> str:
    entry_time = timestamp or datetime.now()
    minute_dt = entry_time.replace(second=0, microsecond=0)
    ts_display = minute_dt.strftime("%Y-%m-%dT%H:%M")
    base = title.strip()
    display_title = (
        _disambiguate_operations_log_title(existing, operation_type, ts_display, base)
        if timestamp is None
        else base
    )
    format_ts = minute_dt if timestamp is None else timestamp
    return format_operations_log_entry(
        operation_type, display_title, summary, format_ts
    )


def _wal_append_operations_log(
    project_root: Path,
    log_path: Path,
    before_exists: bool,
    before_text: str,
    content: str,
) -> None:
    from cortex.memory.wal import WalOperation
    from cortex.memory.wal_hooks import try_wal_record_text_mutation

    try_wal_record_text_mutation(
        project_root,
        log_path,
        WalOperation.APPEND,
        before_exists,
        before_text,
        content,
        True,
        None,
    )


def append_operations_log_entry(
    log_path: Path,
    operation_type: OperationsLogType,
    title: str,
    summary: str | None = None,
    timestamp: datetime | None = None,
    *,
    project_root: Path | None = None,
) -> int:
    """Append one operations-log entry and return the heading line number."""
    header = "# Cortex Operations Log\n\n"
    before_exists = log_path.exists()
    before_text = log_path.read_text(encoding="utf-8") if before_exists else ""
    existing = before_text
    if not existing:
        existing = header
    elif not existing.startswith("# Cortex Operations Log"):
        existing = f"{header}{existing.lstrip()}"
    existing = re.sub(r"(?<!\n)\n(## \[)", r"\n\n\1", existing)
    existing = _trim_to_recent_operations(existing.rstrip("\n") + "\n\n")
    entry = _compose_append_entry(existing, operation_type, title, summary, timestamp)
    line_inserted = len(existing.splitlines()) + 1
    log_path.parent.mkdir(parents=True, exist_ok=True)
    content = _trim_to_recent_operations(f"{existing}{entry}".rstrip("\n") + "\n")
    _ = log_path.write_text(content, encoding="utf-8")
    if project_root is not None:
        _wal_append_operations_log(
            project_root, log_path, before_exists, before_text, content
        )
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
