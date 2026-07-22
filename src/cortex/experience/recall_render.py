"""Render a :class:`RecallResult` into a compact, budget-capped text block."""

from __future__ import annotations

from cortex.experience.recall_models import RecallResult, TaskRecallMatch

_HEADER = "Prior experience (goal-similar tasks):"


def _match_line(match: TaskRecallMatch) -> str:
    parts = [f"- {match.spec} (similarity {match.similarity:.2f})"]
    if match.best_fitness is not None:
        label = f" [{match.best_fitness_label}]" if match.best_fitness_label else ""
        parts.append(f"best outcome fitness={match.best_fitness:.2f}{label}")
    if match.dead_end_label:
        parts.append(f"dead end: {match.dead_end_label}")
    return "; ".join(parts)


def render_recall_summary(result: RecallResult, budget_chars: int) -> str | None:
    """Return a compact multi-line summary truncated to ``budget_chars``.

    Returns None when there is nothing to show (no matches or a zero budget)
    so callers can skip attaching an empty block.
    """
    if not result.matches or budget_chars <= 0:
        return None
    lines = [_HEADER, *[_match_line(match) for match in result.matches]]
    text = "\n".join(lines)
    if len(text) <= budget_chars:
        return text
    # AI: truncate whole lines rather than mid-line so the block never ends
    # on a cut-off sentence fragment inside a session() JSON payload.
    truncated: list[str] = []
    used = 0
    for line in lines:
        addition = len(line) + (1 if truncated else 0)
        if used + addition > budget_chars:
            break
        truncated.append(line)
        used += addition
    if len(truncated) <= 1:
        return text[: max(budget_chars - 1, 0)] + "…"
    return "\n".join(truncated) + "…"
