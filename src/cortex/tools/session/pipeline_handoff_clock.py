"""UTC-aware timestamp helpers for pipeline_handoff staleness checks.

# AI: previously this module's now_iso() (and pipeline_handoff_session.py's
# own copy of it) emitted naive local-time timestamps (no tzinfo). Every
# staleness comparison in this codebase happened to compare naive-vs-naive
# so it never raised, but it was inconsistent with cortex.experience.*,
# which always uses datetime.now(UTC), and offered no protection if a
# timestamp from that store were ever compared against one of these. now_iso()
# now emits aware UTC timestamps; ensure_aware()/age_seconds() let code that
# still parses an old naive-local timestamp (written before this fix)
# interpret it correctly instead of raising TypeError on a naive/aware
# datetime subtraction.
"""

from __future__ import annotations

from datetime import UTC, datetime

# Mirrors cortex.experience.resume.DEFAULT_RESUME_TTL_SECONDS so the handoff
# file's own staleness policy and the experience-store frontier sweep agree.
PIPELINE_TTL_SECONDS = 4 * 3600  # 4 hours


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string with second precision."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def ensure_aware(value: datetime) -> datetime:
    """Attach the local timezone to a naive datetime; pass aware values through.

    Backward compatible with pipeline.json / session-marker files written
    before this fix, whose timestamps were naive local time.
    """
    if value.tzinfo is not None:
        return value
    return value.astimezone()


def parse_iso(raw: str) -> datetime:
    """Parse an ISO-8601 timestamp and ensure the result is timezone-aware."""
    return ensure_aware(datetime.fromisoformat(raw))


def age_seconds(started_raw: str, now: datetime | None = None) -> float:
    """Seconds elapsed since ``started_raw`` (naive/aware-safe)."""
    reference = ensure_aware(now) if now is not None else datetime.now(UTC)
    return (reference - parse_iso(started_raw)).total_seconds()
