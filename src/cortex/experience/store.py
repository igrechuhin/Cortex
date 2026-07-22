"""Async repository API over the experience store.

Thin async facade over :class:`ExperienceStoreCore`; every method offloads
the blocking SQLite call via ``asyncio.to_thread`` so MCP handlers never
block the event loop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from cortex.experience.analytics_models import (
    FitnessByTaskType,
    PreferencePair,
    RepeatedFailureCluster,
)
from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.query_models import FrontierView, IncompleteRun
from cortex.experience.rule_provenance_models import (
    PruningCandidate,
    RuleEvidenceLink,
    RuleProvenance,
)
from cortex.experience.store_core import ExperienceStoreCore


class ExperienceStore:
    """Async experience repository (create/read/append; no deletes)."""

    def __init__(self, core: ExperienceStoreCore) -> None:
        self._core = core

    @classmethod
    def from_db_path(cls, db_path: Path) -> ExperienceStore:
        return cls(core=ExperienceStoreCore(db_path))

    @property
    def core(self) -> ExperienceStoreCore:
        return self._core

    async def create_task(self, task: ExperienceTask) -> ExperienceTask:
        return await asyncio.to_thread(self._core.create_task, task)

    async def create_session(self, session: ExperienceSession) -> ExperienceSession:
        return await asyncio.to_thread(self._core.create_session, session)

    async def append_node(self, node: ExperienceNode) -> ExperienceNode:
        return await asyncio.to_thread(self._core.append_node, node)

    async def set_fitness(self, node_id: str, fitness: float) -> bool:
        return await asyncio.to_thread(self._core.set_fitness, node_id, fitness)

    async def link_artifact(self, node_id: str, artifact_ref: str) -> bool:
        return await asyncio.to_thread(self._core.link_artifact, node_id, artifact_ref)

    async def get_task(self, task_id: str) -> ExperienceTask | None:
        return await asyncio.to_thread(self._core.get_task, task_id)

    async def get_session(self, session_id: str) -> ExperienceSession | None:
        return await asyncio.to_thread(self._core.get_session, session_id)

    async def get_node(self, node_id: str) -> ExperienceNode | None:
        return await asyncio.to_thread(self._core.get_node, node_id)

    async def list_nodes(self, session_id: str) -> list[ExperienceNode]:
        return await asyncio.to_thread(self._core.list_nodes, session_id)

    async def latest_node(self, session_id: str) -> ExperienceNode | None:
        return await asyncio.to_thread(self._core.latest_node, session_id)

    async def list_sessions(self) -> list[ExperienceSession]:
        return await asyncio.to_thread(self._core.list_sessions)

    async def update_node_status(
        self, node_id: str, status: ExperienceNodeStatus
    ) -> bool:
        return await asyncio.to_thread(self._core.update_node_status, node_id, status)

    async def frontier(self, session_id: str) -> FrontierView | None:
        return await asyncio.to_thread(self._core.frontier, session_id)

    async def incomplete_runs(
        self, ttl_seconds: float, now: datetime | None = None
    ) -> list[IncompleteRun]:
        return await asyncio.to_thread(self._core.incomplete_runs, ttl_seconds, now)

    async def preference_pairs(self, session_id: str) -> list[PreferencePair]:
        return await asyncio.to_thread(self._core.preference_pairs, session_id)

    async def repeated_failures(self, session_id: str) -> list[RepeatedFailureCluster]:
        return await asyncio.to_thread(self._core.repeated_failures, session_id)

    async def fitness_by_task_type(self) -> list[FitnessByTaskType]:
        return await asyncio.to_thread(self._core.fitness_by_task_type)

    async def mark_abandoned_runs(
        self, ttl_seconds: float, now: datetime | None = None
    ) -> list[str]:
        return await asyncio.to_thread(self._core.mark_abandoned_runs, ttl_seconds, now)

    async def record_rule_provenance(
        self,
        rule_id: str,
        pairs: list[PreferencePair],
        failure_class: str,
        now: str | None = None,
    ) -> RuleProvenance | None:
        return await asyncio.to_thread(
            self._core.record_rule_provenance, rule_id, pairs, failure_class, now
        )

    async def refresh_rule_matches(
        self, pairs: list[PreferencePair], now: str | None = None
    ) -> list[str]:
        return await asyncio.to_thread(self._core.refresh_rule_matches, pairs, now)

    async def list_rule_provenance(
        self, rule_id: str | None = None
    ) -> list[RuleProvenance]:
        return await asyncio.to_thread(self._core.list_rule_provenance, rule_id)

    async def rule_evidence(self, rule_id: str) -> list[RuleEvidenceLink]:
        return await asyncio.to_thread(self._core.rule_evidence, rule_id)

    async def pruning_candidates(
        self, window_days: float, now: datetime | None = None
    ) -> list[PruningCandidate]:
        return await asyncio.to_thread(self._core.pruning_candidates, window_days, now)
