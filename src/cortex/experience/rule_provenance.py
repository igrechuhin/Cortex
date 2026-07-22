"""Pure aggregation and staleness computations over rule-provenance rows.

Mirrors ``analytics.py``'s style: functions over
``list[RuleProvenanceRecord]`` / ``list[PreferencePair]`` with no I/O, wired
into ``ExperienceStoreCore``/``ExperienceStore`` exactly like
``preference_pairs()``/``fitness_by_task_type()``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from cortex.experience.analytics_models import PreferencePair
from cortex.experience.frontier import age_seconds
from cortex.experience.rule_provenance_models import (
    PruningCandidate,
    RuleProvenance,
    RuleProvenanceRecord,
)

_SECONDS_PER_DAY = 86400.0


def group_provenance(records: list[RuleProvenanceRecord]) -> list[RuleProvenance]:
    """Aggregate per-``(rule_id, pair_id)`` rows into one entry per rule."""
    groups: dict[str, list[RuleProvenanceRecord]] = defaultdict(list)
    for record in records:
        groups[record.rule_id].append(record)
    return [
        RuleProvenance(
            rule_id=rule_id,
            pair_ids=[row.pair_id for row in rows],
            failure_class=rows[0].failure_class,
            created=min(row.created_at for row in rows),
            last_matched=max(row.last_matched_at for row in rows),
        )
        for rule_id, rows in groups.items()
    ]


def pruning_candidates(
    provenance: list[RuleProvenance],
    window_days: float,
    now: datetime | None = None,
) -> list[PruningCandidate]:
    """Rules whose cited failure class has had zero matches within ``window_days``.

    # AI: strict ``>`` boundary keeps a match exactly at the window edge
    # "still fresh" (not stale) — see plan Testing Strategy: boundary dates.
    """
    candidates = [
        PruningCandidate(
            rule_id=entry.rule_id,
            failure_class=entry.failure_class,
            last_matched=entry.last_matched,
            days_since_match=days,
        )
        for entry in provenance
        if (days := age_seconds(entry.last_matched, now) / _SECONDS_PER_DAY)
        > window_days
    ]
    return sorted(candidates, key=lambda c: c.days_since_match, reverse=True)


def failure_classes_from_pairs(pairs: list[PreferencePair]) -> set[str]:
    """Failure classes (failed-node labels) present in a batch of preference pairs."""
    return {pair.failed_node.label for pair in pairs if pair.failed_node.label}
