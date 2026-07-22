"""Vector-seeded similar-task recall over the experience store.

Embeds the goal, finds top-k similar prior tasks (candidate pool widened
then hybrid-reranked with BM25), and walks each match's node graph for its
highest-fitness outcome and any repeated-failure "dead end" pattern.
"""

from __future__ import annotations

from cortex.experience.embedding_index_core import EmbeddingIndexCore
from cortex.experience.encoder import EncoderProtocol
from cortex.experience.hybrid_rank import DEFAULT_VECTOR_WEIGHT, hybrid_scores
from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceTask,
)
from cortex.experience.recall_models import RecallResult, TaskRecallMatch
from cortex.experience.store_core import ExperienceStoreCore

# AI: widen the vector top-k pool before hybrid rerank so BM25 gets enough
# candidates to meaningfully reorder; small constant factor keeps the scan
# cheap at dev-tool scale (brute-force cosine index).
_CANDIDATE_POOL_FACTOR = 3


def _task_nodes(core: ExperienceStoreCore, task_id: str) -> list[ExperienceNode]:
    sessions = [s for s in core.list_sessions() if s.task_id == task_id]
    nodes: list[ExperienceNode] = []
    for session in sessions:
        nodes.extend(core.list_nodes(session.id))
    return nodes


def _best_fitness_node(nodes: list[ExperienceNode]) -> ExperienceNode | None:
    fit_nodes = [n for n in nodes if n.fitness is not None]
    if not fit_nodes:
        return None
    return max(fit_nodes, key=lambda n: n.fitness if n.fitness is not None else 0.0)


def _dead_end_label(nodes: list[ExperienceNode]) -> str | None:
    """Return a label that failed >=2x (a recurring dead end), if any."""
    counts: dict[str, int] = {}
    for node in nodes:
        if node.status is ExperienceNodeStatus.FAILED and node.label:
            counts[node.label] = counts.get(node.label, 0) + 1
    for label, count in counts.items():
        if count >= 2:
            return label
    return None


def _match_for_task(
    core: ExperienceStoreCore, task: ExperienceTask, similarity: float, hybrid: float
) -> TaskRecallMatch:
    nodes = _task_nodes(core, task.id)
    best = _best_fitness_node(nodes)
    return TaskRecallMatch(
        task_id=task.id,
        spec=task.spec,
        similarity=similarity,
        hybrid_score=hybrid,
        best_fitness=best.fitness if best else None,
        best_fitness_label=best.label if best else None,
        dead_end_label=_dead_end_label(nodes),
    )


def _candidate_tasks(
    core: ExperienceStoreCore,
    index: EmbeddingIndexCore,
    query_vector: list[float],
    k: int,
    similarity_threshold: float,
) -> tuple[dict[str, ExperienceTask], dict[str, float]]:
    """Vector top-k candidates above threshold, resolved to their task rows."""
    pool_size = max(k * _CANDIDATE_POOL_FACTOR, k)
    tasks_by_id: dict[str, ExperienceTask] = {}
    similarities: dict[str, float] = {}
    for candidate in index.top_k(query_vector, pool_size):
        if candidate.similarity < similarity_threshold:
            continue
        task = core.get_task(candidate.task_id)
        if task is None:
            continue
        tasks_by_id[task.id] = task
        similarities[task.id] = candidate.similarity
    return tasks_by_id, similarities


def recall_similar_tasks(
    core: ExperienceStoreCore,
    index: EmbeddingIndexCore,
    encoder: EncoderProtocol,
    goal: str,
    k: int,
    similarity_threshold: float,
    vector_weight: float = DEFAULT_VECTOR_WEIGHT,
) -> RecallResult:
    """Embed ``goal``, vector-search, hybrid-rerank, and attach node outcomes."""
    query_vector = encoder.encode(goal)
    tasks_by_id, similarities = _candidate_tasks(
        core, index, query_vector, k, similarity_threshold
    )
    if not tasks_by_id:
        return RecallResult(goal=goal, matches=[])
    hybrid = hybrid_scores(
        goal, list(tasks_by_id.values()), similarities, vector_weight
    )
    ranked_ids = sorted(hybrid, key=lambda tid: hybrid[tid], reverse=True)[:k]
    matches = [
        _match_for_task(core, tasks_by_id[tid], similarities[tid], hybrid[tid])
        for tid in ranked_ids
    ]
    return RecallResult(goal=goal, matches=matches)
