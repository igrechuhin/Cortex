"""SQL query helpers for the ``rule_provenance`` table.

Mirrors ``store_core.py``'s conventions (parameterized queries,
short-lived transactions per call); kept separate from
``ExperienceStoreCore`` so that file stays under the size budget while this
module owns the SQL for the rule-provenance evidence-citation feature (plan
``synapse-rule-provenance.md``).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from cortex.experience.analytics_models import PreferencePair
from cortex.experience.rule_provenance_models import RuleProvenanceRecord


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _insert_or_touch_pair(
    connection: sqlite3.Connection,
    rule_id: str,
    pair: PreferencePair,
    failure_class: str,
    now: str,
) -> None:
    query = """
    INSERT INTO rule_provenance (
        rule_id, pair_id, session_id, parent_id, failed_node_id,
        passed_node_id, failure_class, created_at, last_matched_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (rule_id, pair_id) DO UPDATE SET last_matched_at = excluded.last_matched_at
    """
    _ = connection.execute(
        query,
        (
            rule_id,
            pair.failed_node.id,
            pair.session_id,
            pair.parent_id,
            pair.failed_node.id,
            pair.passed_node.id,
            failure_class,
            now,
            now,
        ),
    )


def record_rule_provenance(
    connection: sqlite3.Connection,
    rule_id: str,
    pairs: list[PreferencePair],
    failure_class: str,
    now: str | None = None,
) -> None:
    """Insert (or bump ``last_matched_at`` for) one row per cited pair."""
    stamp = now or _utc_now_iso()
    for pair in pairs:
        _insert_or_touch_pair(connection, rule_id, pair, failure_class, stamp)
    connection.commit()


def refresh_matching_rules(
    connection: sqlite3.Connection,
    failure_classes: set[str],
    now: str | None = None,
) -> list[str]:
    """Bump ``last_matched_at`` for every rule citing one of ``failure_classes``.

    Returns the sorted list of distinct ``rule_id`` values updated.
    """
    if not failure_classes:
        return []
    stamp = now or _utc_now_iso()
    classes = tuple(failure_classes)
    placeholders = ",".join("?" for _ in classes)
    rows = connection.execute(
        f"SELECT DISTINCT rule_id FROM rule_provenance WHERE failure_class IN ({placeholders})",
        classes,
    ).fetchall()
    rule_ids = sorted({row[0] for row in rows})
    if rule_ids:
        _ = connection.execute(
            f"UPDATE rule_provenance SET last_matched_at = ? WHERE failure_class IN ({placeholders})",
            (stamp, *classes),
        )
        connection.commit()
    return rule_ids


def list_provenance_rows(
    connection: sqlite3.Connection, rule_id: str | None = None
) -> list[RuleProvenanceRecord]:
    """All provenance rows, optionally filtered to one ``rule_id``."""
    if rule_id is None:
        rows = connection.execute(
            "SELECT * FROM rule_provenance ORDER BY rule_id, created_at"
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT * FROM rule_provenance WHERE rule_id = ? ORDER BY created_at",
            (rule_id,),
        ).fetchall()
    return [RuleProvenanceRecord.model_validate(dict(row)) for row in rows]
