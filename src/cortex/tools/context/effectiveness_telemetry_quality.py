"""
Classification of context-usage telemetry for optimization rollups.

Synthetic or inconsistent records are persisted for audit but excluded from
aggregates that drive recommendations.
"""

from __future__ import annotations

import logging

from cortex.core.session_logger import LoadContextLogEntry
from cortex.tools.context.effectiveness_models import ContextTelemetryRecordQuality

logger = logging.getLogger(__name__)

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


def classify_context_telemetry_log_entry(
    entry: LoadContextLogEntry,
) -> tuple[ContextTelemetryRecordQuality, str | None]:
    """Classify a logged load_context row for rollup eligibility.

    Synthetic markers take precedence so test fixtures are never treated as
    production invalidity signals.
    """
    if is_synthetic_telemetry_task(entry.task_description):
        return ContextTelemetryRecordQuality.SYNTHETIC, "synthetic_or_test_task_marker"
    if entry.token_budget == 0 and _has_context_payload(entry):
        return (
            ContextTelemetryRecordQuality.INVALID_DATA,
            "zero_token_budget_with_context_payload",
        )
    return ContextTelemetryRecordQuality.PRODUCTION, None


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
