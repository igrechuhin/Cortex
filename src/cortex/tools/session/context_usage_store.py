"""Project-scoped snapshot store for live harness context occupancy.

The MCP server cannot observe the harness context window on its own; the
only verified source is the harness statusline payload, which the producer
script ``scripts/cortex-context-usage-statusline.sh`` tees into this store
on every statusline tick. ``calculate_health_summary()`` reads the
attributed snapshot back to surface occupancy in ``session()`` health
output.

Snapshots are keyed by the harness ``session_id`` (one file per host
session) because the producer process cannot reach the MCP server's
``CORTEX_SESSION_ID``. Attribution is structural, not guessed: when
TTL-fresh snapshots from MORE THAN ONE host session exist, the read
reports ``ambiguous`` and callers must render UNAVAILABLE — two concurrent
windows make "whose context is this" unknowable, and warn-only telemetry
fails closed instead of reporting the latest writer as the local session.
All Python access goes through ``core.cache_json_access`` per that
module's mandate, whose locked writes satisfy the atomic-write
requirement; the bash producer writes the same files via temp+rename.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import cast

from pydantic import Field, ValidationError

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.core.constants import (
    CONTEXT_USAGE_STALE_AFTER_SECONDS,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
)
from cortex.core.path_resolver import get_cache_path
from cortex.tools.models_base import StrictBaseModel

# Directory (cache key prefix) holding per-session snapshot files.
CONTEXT_USAGE_DIR_KEY = "session"

# Filename prefix shared with the bash producer: context-usage-<sid>.json.
SNAPSHOT_FILENAME_PREFIX = "context-usage-"

# Producer identifier recorded in each snapshot's `source` field.
STATUSLINE_SOURCE = "statusline"

# Session ids are UUIDs; this only guards hostile/broken ids from
# becoming path components.
_UNSAFE_SID_CHARS = re.compile(r"[^A-Za-z0-9._-]")


class ContextUsageSnapshot(StrictBaseModel):
    """On-disk schema for one host session's context-usage snapshot."""

    session_id: str = Field(
        description="Harness session_id from the statusline payload"
    )
    used_tokens: int = Field(
        ge=0,
        description="total_input_tokens + total_output_tokens from the payload",
    )
    limit_tokens: int = Field(
        ge=0,
        description="Context-window size; DEFAULT_CONTEXT_WINDOW_TOKENS fallback",
    )
    used_percentage: float | None = Field(
        None,
        description="Computed used/limit percentage; None when limit is unknown",
    )
    as_of: float = Field(
        ge=0,
        description="Epoch seconds stamped at write time (payload carries no clock)",
    )
    source: str = Field(
        description="Producer that wrote the snapshot, e.g. 'statusline'"
    )


class ContextUsageRead(StrictBaseModel):
    """Attributed read result: the snapshot, or why there is none.

    ``ambiguous=True`` means TTL-fresh snapshots from two or more distinct
    host sessions exist; attribution is unknown and callers must fail
    closed (UNAVAILABLE) instead of guessing the latest writer.
    """

    snapshot: ContextUsageSnapshot | None = None
    ambiguous: bool = False


def session_cache_key(session_id: str) -> str:
    """Cache key for one host session's latest-wins snapshot."""
    safe = _UNSAFE_SID_CHARS.sub("-", session_id)[:64]
    # AI: an unusable id collapses to "unknown" rather than a project-global
    # filename the reader could mistake for an attributed session.
    suffix = safe if safe else "unknown"
    return f"{CONTEXT_USAGE_DIR_KEY}/{SNAPSHOT_FILENAME_PREFIX}{suffix}.json"


def _int_or_none(value: object) -> int | None:
    """Return value as int; reject bools and non-integers."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def parse_statusline_payload(
    payload: dict[str, object], *, as_of: float | None = None
) -> ContextUsageSnapshot | None:
    """Map a statusline payload dict to a snapshot; None when unusable.

    BELIEF: the statusline JSON nests live usage under ``context_window``
    with integer ``total_input_tokens`` + ``total_output_tokens`` (tokens
    currently in the window; input includes cache reads/writes) and an
    optional integer ``context_window_size`` — payload wins,
    DEFAULT_CONTEXT_WINDOW_TOKENS is the fallback. BELIEF:
    ``used_percentage``/``current_usage`` may be null (real host captures
    are null at session start), so the stored percentage is computed, never
    copied from the payload. BELIEF: ``session_id`` sits at the payload top
    level and is REQUIRED — a snapshot without it cannot be attributed to
    a host session, so it is discarded (occupancy stays UNAVAILABLE —
    fail-visible, not fail-wrong).
    """
    context_window_raw = payload.get("context_window")
    if not isinstance(context_window_raw, dict):
        return None
    context_window = cast("dict[str, object]", context_window_raw)
    total_input = _int_or_none(context_window.get("total_input_tokens"))
    total_output = _int_or_none(context_window.get("total_output_tokens"))
    if total_input is None or total_output is None:
        return None
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    limit_raw = _int_or_none(context_window.get("context_window_size"))
    limit_tokens = (
        limit_raw
        if limit_raw is not None and limit_raw > 0
        else DEFAULT_CONTEXT_WINDOW_TOKENS
    )
    used_tokens = total_input + total_output
    return ContextUsageSnapshot(
        session_id=session_id,
        used_tokens=used_tokens,
        limit_tokens=limit_tokens,
        used_percentage=(
            (used_tokens / limit_tokens * 100) if limit_tokens > 0 else None
        ),
        as_of=time.time() if as_of is None else as_of,
        source=STATUSLINE_SOURCE,
    )


async def record_context_usage(
    project_root: Path, snapshot: ContextUsageSnapshot
) -> None:
    """Persist the session's latest-wins snapshot under the project cache.

    BELIEF: the external bash producer writes the same per-session file
    via temp+rename WITHOUT this module's lock (rename is atomic;
    per-session latest-wins is acceptable for warn-only telemetry).
    """
    await write_cache_json(
        project_root,
        session_cache_key(snapshot.session_id),
        snapshot.model_dump(mode="json"),
    )


def _valid_snapshots(data: object) -> list[ContextUsageSnapshot]:
    """Validate one decoded cache object into zero or one snapshots."""
    if not isinstance(data, dict):
        return []
    try:
        return [ContextUsageSnapshot.model_validate(data)]
    except ValidationError:
        return []


def _iter_snapshot_files(project_root: Path) -> list[Path]:
    """List per-session snapshot files (enumeration only; reads use the cache module)."""
    directory = get_cache_path(project_root, None) / CONTEXT_USAGE_DIR_KEY
    return sorted(directory.glob(f"{SNAPSHOT_FILENAME_PREFIX}*.json"))


def _select_attributed(
    snapshots: list[ContextUsageSnapshot], now: float
) -> ContextUsageRead:
    """Pick the attributed snapshot or report ambiguity; stale never counts."""
    fresh = [s for s in snapshots if now - s.as_of <= CONTEXT_USAGE_STALE_AFTER_SECONDS]
    session_ids = {s.session_id for s in fresh}
    if len(session_ids) > 1:
        return ContextUsageRead(snapshot=None, ambiguous=True)
    if not fresh:
        return ContextUsageRead()
    return ContextUsageRead(snapshot=max(fresh, key=lambda s: s.as_of))


async def read_context_usage(project_root: Path) -> ContextUsageRead:
    """Read snapshots and attribute them; corrupted files are skipped."""
    now = time.time()
    snapshots: list[ContextUsageSnapshot] = []
    for path in _iter_snapshot_files(project_root):
        data = await read_cache_json(
            project_root, f"{CONTEXT_USAGE_DIR_KEY}/{path.name}"
        )
        snapshots.extend(_valid_snapshots(data))
    return _select_attributed(snapshots, now)
