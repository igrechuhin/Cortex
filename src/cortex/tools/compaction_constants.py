"""Constants for session compaction workflow (Phase 56).

Compaction rules for activeContext.md and progress.md to keep memory bank
within token budget while preserving key decisions and progress.
"""

# activeContext.md compaction
RECENT_CHANGES_MAX_ENTRIES = 5
"""Keep at most this many entries in Recent Changes section."""

ACTIVECONTEXT_KEEP_CURRENT_DATE_ONLY = True
"""Completed Work: keep full entries for current date only; older dates summarized."""

# progress.md compaction
PROGRESS_DAYS_FULL = 7
"""Keep individual entries for last N days (Tier 1)."""

PROGRESS_DAYS_WEEKLY_SUMMARY = 30
"""Summarize entries older than 7 days into weekly summaries up to N days (Tier 2)."""

PROGRESS_MONTHLY_TIER_DAYS = 30
"""Entries older than this become monthly summaries (Tier 3)."""

PROGRESS_TOKEN_THRESHOLD_DEFAULT = 10_000
"""Auto-trigger summarization when progress.md exceeds this token count (configurable)."""

# Session handoff
SESSION_HANDOFF_FILENAME = "last_handoff.json"
"""Filename for session handoff under .cortex/.cache/session/."""

SESSION_PROGRESS_FILENAME = "progress.txt"
"""Filename for human-readable progress file under .cortex/.cache/session/."""

SESSION_HANDOFF_SCHEMA_VERSION = 1
"""Current schema version for SessionHandoff (for future compatibility)."""
