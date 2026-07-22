"""Typed results for graph-pattern analytics over the experience store.

Mirrors ``query_models.py``'s style: pure Pydantic 2 result shapes consumed
by ``analytics.py`` (pure functions) and wired through
``ExperienceStoreCore``/``ExperienceStore`` (see ``frontier()`` for the
existing wiring pattern this follows).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from cortex.experience.models import ExperienceNode


class PreferencePair(BaseModel):
    """Sibling nodes under one parent with divergent gate outcomes.

    The passed/failed divergence is a graph pattern match (same
    ``parent_id``, one ``COMPLETED`` and one ``FAILED``), not a scrape of
    session transcripts.
    """

    parent_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    passed_node: ExperienceNode
    failed_node: ExperienceNode


class RepeatedFailureCluster(BaseModel):
    """A label that recurred as a FAILED node >=2x within one session."""

    session_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    node_ids: list[str] = Field(default_factory=list)
    count: int = Field(ge=2)


class FitnessByTaskType(BaseModel):
    """Fitness statistics aggregated per pipeline ("task type")."""

    task_type: str = Field(min_length=1)
    sample_count: int = Field(ge=0)
    avg_fitness: float
    min_fitness: float
    max_fitness: float
