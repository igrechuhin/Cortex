"""Synchronous SQLite core for the experience store.

Mirrors the ``TemporalMemoryStore`` access conventions (short-lived
``sqlite3`` connections, parameterized queries). The async public API in
``cortex.experience.store`` offloads these calls via ``asyncio.to_thread``;
best-effort recording hooks that already run inside worker threads use this
core directly.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from cortex.experience.analytics import (
    fitness_by_task_type,
    preference_pairs,
    repeated_failures,
)
from cortex.experience.analytics_models import (
    FitnessByTaskType,
    PreferencePair,
    RepeatedFailureCluster,
)
from cortex.experience.frontier import (
    age_seconds,
    frontier_phase,
    frontier_view,
    run_window,
)
from cortex.experience.lifecycle import (
    RUN_ABANDONED_LABEL,
    can_transition,
)
from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.query_models import FrontierView, IncompleteRun
from cortex.experience.rule_provenance import (
    failure_classes_from_pairs,
    group_provenance,
)
from cortex.experience.rule_provenance import (
    pruning_candidates as _compute_pruning_candidates,
)
from cortex.experience.rule_provenance_models import (
    PruningCandidate,
    RuleEvidenceLink,
    RuleProvenance,
)
from cortex.experience.rule_provenance_queries import (
    list_provenance_rows,
    refresh_matching_rules,
)
from cortex.experience.rule_provenance_queries import (
    record_rule_provenance as _record_rule_provenance,
)
from cortex.experience.schema import migrate

# AI: 5s busy timeout absorbs short lock contention from concurrent sessions
# without stalling the (best-effort) recording path indefinitely.
_BUSY_TIMEOUT_SECONDS = 5.0


class ExperienceStoreCore:
    """Sync repository over ``experience.db`` (create/read/append; no deletes)."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            migrate(connection)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=_BUSY_TIMEOUT_SECONDS)
        connection.row_factory = sqlite3.Row
        return connection

    # -- create -----------------------------------------------------------

    def create_task(self, task: ExperienceTask) -> ExperienceTask:
        query = """
        INSERT OR IGNORE INTO tasks (id, spec, success_metric, created_at)
        VALUES (?, ?, ?, ?)
        """
        with self._connect() as connection:
            _ = connection.execute(
                query, (task.id, task.spec, task.success_metric, task.created_at)
            )
            connection.commit()
        return task

    def create_session(self, session: ExperienceSession) -> ExperienceSession:
        query = """
        INSERT OR IGNORE INTO sessions (
            id, task_id, algorithm, owner, progress, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        with self._connect() as connection:
            _ = connection.execute(
                query,
                (
                    session.id,
                    session.task_id,
                    session.algorithm,
                    session.owner,
                    session.progress,
                    session.created_at,
                ),
            )
            connection.commit()
        return session

    def append_node(self, node: ExperienceNode) -> ExperienceNode:
        query = """
        INSERT INTO nodes (
            id, parent_id, session_id, artifact_ref, fitness,
            status, step_number, label, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as connection:
            _ = connection.execute(
                query,
                (
                    node.id,
                    node.parent_id,
                    node.session_id,
                    node.artifact_ref,
                    node.fitness,
                    node.status.value,
                    node.step_number,
                    node.label,
                    node.created_at,
                ),
            )
            connection.commit()
        return node

    def set_fitness(self, node_id: str, fitness: float) -> bool:
        query = "UPDATE nodes SET fitness = ? WHERE id = ?"
        with self._connect() as connection:
            cursor = connection.execute(query, (fitness, node_id))
            connection.commit()
        return cursor.rowcount > 0

    def link_artifact(self, node_id: str, artifact_ref: str) -> bool:
        query = "UPDATE nodes SET artifact_ref = ? WHERE id = ?"
        with self._connect() as connection:
            cursor = connection.execute(query, (artifact_ref, node_id))
            connection.commit()
        return cursor.rowcount > 0

    # -- read -------------------------------------------------------------

    def get_task(self, task_id: str) -> ExperienceTask | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return ExperienceTask.model_validate(dict(row)) if row else None

    def get_session(self, session_id: str) -> ExperienceSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return ExperienceSession.model_validate(dict(row)) if row else None

    def get_node(self, node_id: str) -> ExperienceNode | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
        return ExperienceNode.model_validate(dict(row)) if row else None

    def list_nodes(self, session_id: str) -> list[ExperienceNode]:
        query = """
        SELECT * FROM nodes WHERE session_id = ?
        ORDER BY step_number ASC, created_at ASC
        """
        with self._connect() as connection:
            rows = connection.execute(query, (session_id,)).fetchall()
        return [ExperienceNode.model_validate(dict(row)) for row in rows]

    def latest_node(self, session_id: str) -> ExperienceNode | None:
        query = """
        SELECT * FROM nodes WHERE session_id = ?
        ORDER BY step_number DESC, created_at DESC LIMIT 1
        """
        with self._connect() as connection:
            row = connection.execute(query, (session_id,)).fetchone()
        return ExperienceNode.model_validate(dict(row)) if row else None

    def list_sessions(self) -> list[ExperienceSession]:
        query = "SELECT * FROM sessions ORDER BY created_at ASC"
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        return [ExperienceSession.model_validate(dict(row)) for row in rows]

    # -- lifecycle ---------------------------------------------------------

    def update_node_status(self, node_id: str, status: ExperienceNodeStatus) -> bool:
        """Apply a status transition; reject invalid lifecycle moves.

        Enforces ``pending -> running -> completed | failed``; terminal
        states are immutable. Returns False for missing nodes or invalid
        transitions.
        """
        node = self.get_node(node_id)
        if node is None or not can_transition(node.status, status):
            return False
        query = "UPDATE nodes SET status = ? WHERE id = ?"
        with self._connect() as connection:
            cursor = connection.execute(query, (status.value, node_id))
            connection.commit()
        return cursor.rowcount > 0

    # -- frontier / resume queries ----------------------------------------

    def frontier(self, session_id: str) -> FrontierView | None:
        """Frontier of the current run window (None when no active window)."""
        return frontier_view(session_id, self.list_nodes(session_id))

    def _incomplete_run(
        self, session: ExperienceSession, ttl_seconds: float, now: datetime | None
    ) -> IncompleteRun | None:
        window = run_window(self.list_nodes(session.id))
        if not window:
            return None
        latest = window[-1]
        age = age_seconds(latest.created_at, now)
        if age > ttl_seconds:
            return None
        return IncompleteRun(
            session_id=session.id,
            owner=session.owner,
            pipeline=session.algorithm,
            frontier_phase=frontier_phase(window),
            frontier_status=latest.status,
            last_activity_at=latest.created_at,
            age_seconds=age,
        )

    def incomplete_runs(
        self, ttl_seconds: float, now: datetime | None = None
    ) -> list[IncompleteRun]:
        """Fresh runs whose window has not ended, most recent activity first."""
        runs = [
            run
            for session in self.list_sessions()
            if (run := self._incomplete_run(session, ttl_seconds, now)) is not None
        ]
        return sorted(runs, key=lambda run: run.last_activity_at, reverse=True)

    # -- analytics (preference pairs / repeated failures / fitness) -------

    def preference_pairs(self, session_id: str) -> list[PreferencePair]:
        """Sibling pass/fail node pairs within one session's node graph."""
        return preference_pairs(self.list_nodes(session_id))

    def repeated_failures(self, session_id: str) -> list[RepeatedFailureCluster]:
        """Labels that recurred as FAILED nodes >=2x within one session."""
        return repeated_failures(self.list_nodes(session_id))

    def fitness_by_task_type(self) -> list[FitnessByTaskType]:
        """Fitness statistics aggregated per pipeline across all sessions."""
        sessions = self.list_sessions()
        nodes_by_session = {
            session.id: self.list_nodes(session.id) for session in sessions
        }
        return fitness_by_task_type(sessions, nodes_by_session)

    def mark_abandoned_runs(
        self, ttl_seconds: float, now: datetime | None = None
    ) -> list[str]:
        """Close run windows stale past the TTL with an abandoned marker."""
        abandoned: list[str] = []
        for session in self.list_sessions():
            window = run_window(self.list_nodes(session.id))
            if not window:
                continue
            latest = window[-1]
            if age_seconds(latest.created_at, now) <= ttl_seconds:
                continue
            _ = self.append_node(
                ExperienceNode(
                    parent_id=latest.id,
                    session_id=session.id,
                    status=ExperienceNodeStatus.FAILED,
                    step_number=latest.step_number + 1,
                    label=RUN_ABANDONED_LABEL,
                )
            )
            abandoned.append(session.id)
        return abandoned

    # -- rule provenance (evidence citations for Synapse rules) -----------

    def record_rule_provenance(
        self,
        rule_id: str,
        pairs: list[PreferencePair],
        failure_class: str,
        now: str | None = None,
    ) -> RuleProvenance | None:
        """Persist evidence citations for a rule recommendation.

        Idempotent per ``(rule_id, pair_id)``: re-citing an already-recorded
        pair bumps its ``last_matched_at`` instead of duplicating rows.
        Returns the aggregated provenance for ``rule_id``, or ``None`` when
        ``pairs`` is empty.
        """
        if not pairs:
            return None
        with self._connect() as connection:
            _record_rule_provenance(connection, rule_id, pairs, failure_class, now)
        aggregates = self.list_rule_provenance(rule_id)
        return aggregates[0] if aggregates else None

    def refresh_rule_matches(
        self, pairs: list[PreferencePair], now: str | None = None
    ) -> list[str]:
        """Bump ``last_matched`` for rules whose cited failure class recurs.

        Returns the ids of rules refreshed.
        """
        classes = failure_classes_from_pairs(pairs)
        with self._connect() as connection:
            return refresh_matching_rules(connection, classes, now)

    def list_rule_provenance(self, rule_id: str | None = None) -> list[RuleProvenance]:
        """All rule-provenance aggregates, optionally filtered to one rule."""
        with self._connect() as connection:
            rows = list_provenance_rows(connection, rule_id)
        return group_provenance(rows)

    def rule_evidence(self, rule_id: str) -> list[RuleEvidenceLink]:
        """Cited pairs with artifact refs for "why does this rule exist".

        Dangling node ids (pruned/missing nodes) resolve to a ``None``
        artifact ref rather than raising.
        """
        with self._connect() as connection:
            rows = list_provenance_rows(connection, rule_id)
        links: list[RuleEvidenceLink] = []
        for row in rows:
            failed = self.get_node(row.failed_node_id)
            passed = self.get_node(row.passed_node_id)
            links.append(
                RuleEvidenceLink(
                    pair_id=row.pair_id,
                    session_id=row.session_id,
                    parent_id=row.parent_id,
                    failed_node_id=row.failed_node_id,
                    failed_artifact_ref=failed.artifact_ref if failed else None,
                    passed_node_id=row.passed_node_id,
                    passed_artifact_ref=passed.artifact_ref if passed else None,
                    failure_class=row.failure_class,
                    last_matched=row.last_matched_at,
                )
            )
        return links

    def pruning_candidates(
        self, window_days: float, now: datetime | None = None
    ) -> list[PruningCandidate]:
        """Rules whose cited failure class has had zero matches within the window."""
        return _compute_pruning_candidates(
            self.list_rule_provenance(), window_days, now
        )
