"""Pure graph-pattern queries over experience nodes and sessions.

Mirrors ``frontier.py``'s style: functions over ``list[ExperienceNode]``
with no I/O, wired into ``ExperienceStoreCore``/``ExperienceStore`` exactly
like ``frontier()``/``incomplete_runs()``.
"""

from __future__ import annotations

from collections import defaultdict

from cortex.experience.analytics_models import (
    FitnessByTaskType,
    PreferencePair,
    RepeatedFailureCluster,
)
from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
)

_MIN_CLUSTER_COUNT = 2


def _group_by_parent(nodes: list[ExperienceNode]) -> dict[str, list[ExperienceNode]]:
    groups: dict[str, list[ExperienceNode]] = defaultdict(list)
    for node in nodes:
        if node.parent_id is not None:
            groups[node.parent_id].append(node)
    return groups


def _best_passed_sibling(siblings: list[ExperienceNode]) -> ExperienceNode | None:
    passed = [n for n in siblings if n.status is ExperienceNodeStatus.COMPLETED]
    if not passed:
        return None
    # AI: pick the highest-fitness passed sibling per parent so each failed
    # sibling pairs with exactly one "best" counterexample, bounding output
    # to one pair per failed node rather than a full cross-product.
    return max(
        passed, key=lambda n: n.fitness if n.fitness is not None else float("-inf")
    )


def preference_pairs(nodes: list[ExperienceNode]) -> list[PreferencePair]:
    """Sibling pairs (same parent) with strict passed/failed divergence.

    # AI: pairing signal is ``status`` divergence (COMPLETED vs FAILED), not
    # fitness comparison alone — fitness may be None and tied fitness must
    # not produce spurious pairs (see plan risk: "Require strict gate
    # pass/fail divergence; exclude ties").
    """
    pairs: list[PreferencePair] = []
    for parent_id, siblings in _group_by_parent(nodes).items():
        best_passed = _best_passed_sibling(siblings)
        if best_passed is None:
            continue
        failed_siblings = [
            n for n in siblings if n.status is ExperienceNodeStatus.FAILED
        ]
        for failed in failed_siblings:
            pairs.append(
                PreferencePair(
                    parent_id=parent_id,
                    session_id=failed.session_id,
                    passed_node=best_passed,
                    failed_node=failed,
                )
            )
    return pairs


def repeated_failures(nodes: list[ExperienceNode]) -> list[RepeatedFailureCluster]:
    """Labels that recurred as FAILED nodes >=2x within the same session."""
    clusters: dict[tuple[str, str], list[str]] = defaultdict(list)
    for node in nodes:
        if node.status is not ExperienceNodeStatus.FAILED or node.label is None:
            continue
        clusters[(node.session_id, node.label)].append(node.id)
    return [
        RepeatedFailureCluster(
            session_id=session_id,
            label=label,
            node_ids=node_ids,
            count=len(node_ids),
        )
        for (session_id, label), node_ids in clusters.items()
        if len(node_ids) >= _MIN_CLUSTER_COUNT
    ]


def _stats_for_group(
    nodes: list[ExperienceNode],
) -> tuple[int, float, float, float] | None:
    values = [n.fitness for n in nodes if n.fitness is not None]
    if not values:
        return None
    return len(values), sum(values) / len(values), min(values), max(values)


def fitness_by_task_type(
    sessions: list[ExperienceSession],
    nodes_by_session: dict[str, list[ExperienceNode]],
) -> list[FitnessByTaskType]:
    """Aggregate fitness across sessions grouped by ``algorithm``.

    # AI: ``ExperienceSession.algorithm`` (the pipeline name, e.g. "commit")
    # stands in for "task type" — the schema has no dedicated task-type
    # field, and algorithm is the only categorical grouping dimension
    # available on the session row.
    """
    nodes_by_algorithm: dict[str, list[ExperienceNode]] = defaultdict(list)
    for session in sessions:
        nodes_by_algorithm[session.algorithm].extend(
            nodes_by_session.get(session.id, [])
        )
    results: list[FitnessByTaskType] = []
    for task_type, nodes in nodes_by_algorithm.items():
        stats = _stats_for_group(nodes)
        if stats is None:
            continue
        sample_count, avg_fitness, min_fitness, max_fitness = stats
        results.append(
            FitnessByTaskType(
                task_type=task_type,
                sample_count=sample_count,
                avg_fitness=avg_fitness,
                min_fitness=min_fitness,
                max_fitness=max_fitness,
            )
        )
    return results
