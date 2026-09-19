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


def _marker(dropped: int) -> str:
    return f"\n… {dropped} matches omitted (budget)"


# AI: derived from `_marker` itself, so the two can never drift; lets the fit
# loop size the marker without building a string per candidate line.
_MARKER_OVERHEAD = len(_marker(0)) - 1


def _marker_len(dropped: int) -> int:
    return _MARKER_OVERHEAD + len(str(dropped))


def render_recall_summary(result: RecallResult, budget_chars: int) -> str | None:
    """Return a compact multi-line summary that never exceeds ``budget_chars``.

    Returns None when there is nothing to show (no matches, a zero budget,
    or not even the pinned header plus an omission note fits).
    """
    if not result.matches or budget_chars <= 0:
        return None
    lines = [_HEADER, *[_match_line(match) for match in result.matches]]
    text = "\n".join(lines)
    if len(text) <= budget_chars:
        return text
    return _fit_with_marker(lines, len(result.matches), budget_chars)


def _fit_with_marker(
    lines: list[str], total_matches: int, budget_chars: int
) -> str | None:
    """Keep whole match lines, always reserving room for the omission marker.

    # AI: the marker is part of the budget, not appended after it. Sizing it
    # during allocation is what keeps the contract `len(output) <= budget`;
    # appending afterwards silently overran the caller's cap. The header is
    # pinned whole-or-nothing, and a match line is never cut mid-line -- this
    # data is re-derivable, a corrupted half-line is not.
    """
    kept = [lines[0]]
    used = len(lines[0])
    for line in lines[1:]:
        candidate = used + 1 + len(line)
        remaining = total_matches - len(kept)
        if candidate + _marker_len(remaining) > budget_chars:
            break
        kept.append(line)
        used = candidate
    output = "\n".join(kept) + _marker(total_matches - (len(kept) - 1))
    return output if len(output) <= budget_chars else None
