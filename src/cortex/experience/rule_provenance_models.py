"""Typed models for Synapse rule provenance (rule id -> evidence node pairs).

Mirrors ``analytics_models.py``'s style: pure Pydantic 2 result shapes,
persisted via ``rule_provenance_queries.py`` and wired through
``ExperienceStoreCore``/``ExperienceStore`` (see plan
``synapse-rule-provenance.md``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuleProvenanceRecord(BaseModel):
    """One persisted ``(rule_id, pair_id)`` evidence row in ``rule_provenance``.

    ``pair_id`` is the failed node's id — the stable identity of a
    :class:`~cortex.experience.analytics_models.PreferencePair` within the
    store (mirrors ``failure_evals.py``'s ``graph-{failed.id}`` convention).
    """

    rule_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    parent_id: str = Field(min_length=1)
    failed_node_id: str = Field(min_length=1)
    passed_node_id: str = Field(min_length=1)
    failure_class: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    last_matched_at: str = Field(min_length=1)


class RuleProvenance(BaseModel):
    """Aggregate provenance for one rule: cited pairs + created/last_matched bounds."""

    rule_id: str = Field(min_length=1)
    pair_ids: list[str] = Field(default_factory=list)
    failure_class: str = Field(min_length=1)
    created: str = Field(min_length=1)
    last_matched: str = Field(min_length=1)


class RuleEvidenceLink(BaseModel):
    """One cited node pair with artifact refs, for the ``rule_evidence`` read API."""

    pair_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    parent_id: str = Field(min_length=1)
    failed_node_id: str = Field(min_length=1)
    failed_artifact_ref: str | None = None
    passed_node_id: str = Field(min_length=1)
    passed_artifact_ref: str | None = None
    failure_class: str = Field(min_length=1)
    last_matched: str = Field(min_length=1)


class PruningCandidate(BaseModel):
    """A rule whose cited failure class has had zero matches within the window."""

    rule_id: str = Field(min_length=1)
    failure_class: str = Field(min_length=1)
    last_matched: str = Field(min_length=1)
    days_since_match: float = Field(ge=0)
