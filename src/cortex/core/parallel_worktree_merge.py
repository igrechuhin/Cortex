"""Parallel worktree merge ordering and conflict detection for plan task graphs.

Used after a ``/cortex/do`` parallel batch: merge branches in dependency order and
surface overlapping edits as ``[NEEDS CLARIFICATION]`` data (see
:class:`~cortex.core.models.ClarificationMarker`).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence, Set

from cortex.core.models import ClarificationMarker, TaskNode
from cortex.core.plan_utils import PlanValidationError


def merge_order_for_parallel_batch(nodes: Sequence[TaskNode]) -> list[int]:
    """Return *nodes* step ids in merge-safe order within a single parallel batch.

    # AI: Only explicit ``depends_on`` edges between batch members constrain merge
    # order; missing edges mean concurrent work, so a stable tie-break uses
    # ascending ``step_id`` for zero-indegree picks (matches sequential spine).
    """
    if not nodes:
        return []
    batch_ids = {n.step_id for n in nodes}
    indegree: dict[int, int] = {sid: 0 for sid in batch_ids}
    adj: defaultdict[int, list[int]] = defaultdict(list)
    for n in nodes:
        for dep in n.depends_on:
            if dep in batch_ids:
                adj[dep].append(n.step_id)
                indegree[n.step_id] += 1
    order: list[int] = []
    ready = sorted((sid for sid, d in indegree.items() if d == 0), key=lambda x: x)
    while ready:
        u = ready.pop(0)
        order.append(u)
        for v in sorted(adj[u], key=lambda x: x):
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
                ready.sort()
    if len(order) != len(batch_ids):
        raise PlanValidationError("cyclic dependencies within parallel worktree batch")
    return order


def _normalized_path_token(raw: str) -> str | None:
    path = raw.strip().replace("\\", "/")
    return path if path else None


def _path_to_step_lists(
    batch_ids: set[int],
    changed_paths_by_step: Mapping[int, Set[str]],
) -> dict[str, list[int]]:
    path_to_steps: defaultdict[str, list[int]] = defaultdict(list)
    for sid in sorted(batch_ids):
        for raw in changed_paths_by_step.get(sid, set()):
            norm = _normalized_path_token(raw)
            if norm is not None:
                path_to_steps[norm].append(sid)
    return path_to_steps


def clarification_markers_for_shared_paths(
    batch: Sequence[TaskNode],
    changed_paths_by_step: Mapping[int, Set[str]],
    *,
    location: str = "parallel worktree merge",
) -> list[ClarificationMarker]:
    """When multiple batch steps touch the same path, emit blocking clarification markers."""
    batch_ids = {n.step_id for n in batch}
    path_to_steps = _path_to_step_lists(batch_ids, changed_paths_by_step)
    markers: list[ClarificationMarker] = []
    for path, steps in sorted(path_to_steps.items()):
        uniq = sorted(set(steps))
        if len(uniq) < 2:
            continue
        steps_label = ", ".join(str(s) for s in uniq)
        markers.append(
            ClarificationMarker(
                reason=(
                    f"Parallel worktree steps {steps_label} both modified {path}; "
                    "merge blocked — clarify ownership or serialize the steps"
                ),
                blocking=True,
                location=location,
                resolved=False,
            )
        )
    return markers
