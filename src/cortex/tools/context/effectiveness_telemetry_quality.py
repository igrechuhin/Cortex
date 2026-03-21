"""
Classification of context-usage telemetry for optimization rollups.

Synthetic or inconsistent records are persisted for audit but excluded from
aggregates that drive recommendations.
"""

from __future__ import annotations

import logging
import threading

from cortex.core.session_logger import LoadContextLogEntry
from cortex.tools.context.effectiveness_models import (
    ContextTelemetryExclusionBreakdown,
    ContextTelemetryExclusionCountersSnapshot,
    ContextTelemetryRecordQuality,
    ContextUsageEntry,
)

logger = logging.getLogger(__name__)

_exclusion_counter_lock = threading.Lock()
# Keys: (record_quality.value, reason or "")
_exclusion_counts: dict[tuple[str, str], int] = {}

# Normalized task titles that are almost always test/synthetic fixtures.
_SYNTHETIC_EXACT_TASKS: frozenset[str] = frozenset(
    {
        "test",
        "test task",
        "dummy",
        "dummy task",
        "fake task",
        "synthetic",
        "synthetic task",
    }
)

# Substrings that indicate pytest/unit-test style tasks.
_PYTEST_MARKERS: tuple[str, ...] = (
    "pytest",
    "unittest",
    "pytests",
)


def is_synthetic_telemetry_task(task_description: str) -> bool:
    """Return True when the task title matches known synthetic/test fixtures."""
    normalized = task_description.strip().lower()
    if normalized in _SYNTHETIC_EXACT_TASKS:
        return True
    if normalized.startswith("test_"):
        return True
    for marker in _PYTEST_MARKERS:
        if marker in normalized:
            return True
    return False


def _has_context_payload(entry: LoadContextLogEntry) -> bool:
    return bool(entry.selected_files) or entry.total_tokens > 0


def _non_synthetic_internal_inconsistency_log_entry(
    entry: LoadContextLogEntry,
) -> str | None:
    """Detect impossible or internally inconsistent non-synthetic log rows."""
    files_n = len(entry.selected_files)
    rel_n = len(entry.relevance_scores)
    if entry.token_budget == 0 and _has_context_payload(entry):
        return "zero_token_budget_with_context_payload"
    if entry.token_budget > 0 and entry.total_tokens > 0 and files_n == 0:
        return "positive_tokens_without_selected_files"
    if rel_n > 0 and files_n == 0:
        return "relevance_scores_without_selected_files"
    return None


def classify_context_telemetry_log_entry(
    entry: LoadContextLogEntry,
) -> tuple[ContextTelemetryRecordQuality, str | None]:
    """Classify a logged load_context row for rollup eligibility.

    Synthetic markers take precedence so test fixtures are never treated as
    production invalidity signals.
    """
    if is_synthetic_telemetry_task(entry.task_description):
        return ContextTelemetryRecordQuality.SYNTHETIC, "synthetic_or_test_task_marker"
    reason = _non_synthetic_internal_inconsistency_log_entry(entry)
    if reason is not None:
        return ContextTelemetryRecordQuality.INVALID_DATA, reason
    return ContextTelemetryRecordQuality.PRODUCTION, None


def classify_persisted_context_usage_entry(
    entry: ContextUsageEntry,
) -> tuple[ContextTelemetryRecordQuality, str | None]:
    """Re-classify a persisted statistics row (backfill / load-time validation).

    Uses the same eligibility rules as log ingestion, derived from stored fields.
    """
    if is_synthetic_telemetry_task(entry.task_description):
        return ContextTelemetryRecordQuality.SYNTHETIC, "synthetic_or_test_task_marker"
    files_n = entry.files_selected
    rel_n = len(entry.relevance_by_file or {})
    if entry.token_budget == 0 and (entry.total_tokens > 0 or files_n > 0):
        return (
            ContextTelemetryRecordQuality.INVALID_DATA,
            "zero_token_budget_with_context_payload",
        )
    if entry.token_budget > 0 and entry.total_tokens > 0 and files_n == 0:
        return (
            ContextTelemetryRecordQuality.INVALID_DATA,
            "positive_tokens_without_selected_files",
        )
    if rel_n > 0 and files_n == 0:
        return (
            ContextTelemetryRecordQuality.INVALID_DATA,
            "relevance_scores_without_selected_files",
        )
    return ContextTelemetryRecordQuality.PRODUCTION, None


def _increment_rollup_exclusion_counter(
    quality: ContextTelemetryRecordQuality,
    reason: str | None,
) -> None:
    key = (quality.value, reason or "")
    with _exclusion_counter_lock:
        _exclusion_counts[key] = _exclusion_counts.get(key, 0) + 1


def snapshot_context_telemetry_exclusion_counters() -> (
    ContextTelemetryExclusionCountersSnapshot
):
    """Return a copy of in-process rollup-exclusion counters (metrics-style observability)."""
    with _exclusion_counter_lock:
        items = sorted(
            _exclusion_counts.items(),
            key=lambda kv: (kv[0][0], kv[0][1]),
        )
    breakdown = [
        ContextTelemetryExclusionBreakdown(
            record_quality=quality,
            reason=reason,
            count=count,
        )
        for (quality, reason), count in items
    ]
    total = sum(b.count for b in breakdown)
    return ContextTelemetryExclusionCountersSnapshot(
        breakdown=breakdown,
        total_excluded=total,
    )


def reset_context_telemetry_exclusion_counters() -> None:
    """Clear in-process exclusion counters (intended for tests)."""
    with _exclusion_counter_lock:
        _exclusion_counts.clear()


def log_telemetry_rollup_exclusion(
    *,
    session_id: str,
    task_description: str,
    quality: ContextTelemetryRecordQuality,
    reason: str | None,
) -> None:
    """Emit a single structured log line when a record is excluded from rollups."""
    if quality == ContextTelemetryRecordQuality.PRODUCTION:
        return
    _increment_rollup_exclusion_counter(quality, reason)
    snippet = task_description.strip().replace("\n", " ")
    if len(snippet) > 120:
        snippet = snippet[:117] + "..."
    fmt = "Excluded context telemetry from optimization rollup: session_id=%s record_quality=%s reason=%s task_snippet=%r"
    logger.info(fmt, session_id, quality.value, reason, snippet)


def log_and_classify_context_telemetry_entry(
    session_id: str,
    entry: LoadContextLogEntry,
) -> tuple[ContextTelemetryRecordQuality, str | None]:
    """Classify a log row and emit rollup-exclusion logging when needed."""
    record_quality, quality_note = classify_context_telemetry_log_entry(entry)
    log_telemetry_rollup_exclusion(
        session_id=session_id,
        task_description=entry.task_description,
        quality=record_quality,
        reason=quality_note,
    )
    return record_quality, quality_note
