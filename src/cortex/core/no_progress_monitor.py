"""Task-level no-progress loop detector for fix/implement subagents.

Distinct from the MCP-transport circuit breaker (``mcp_stability_retry.py``,
``MCPConnectionState``): that breaker trips on consecutive **connection**
failures at the transport level. This module trips on a subagent (e.g.
``fix-tests``, ``fix-quality``, ``implement-code``) repeating the same
unproductive fix attempt against the same target — every tool call succeeds
(no MCP error), but the underlying problem never changes. See
``.cortex/synapse/agents/shared-conventions.md`` for the shared
checkpoint/report/resume UX both signals reuse.

Attempt records are written by subagents into their own ``pipeline_handoff``
phase payload under a top-level ``attempt_history`` list (no new phase or
schema is required — ``pipeline_handoff`` already accepts arbitrary JSON
dict payloads per phase). This module only defines the record shape and the
comparison logic; it does not perform any I/O itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.pydantic_extra import EXTRA_FORBID

# AI: matches the existing MCP-transport circuit breaker's "3 consecutive
# failures" convention (shared-conventions.md) so agents reuse one threshold
# value instead of learning a second number for a second signal.
DEFAULT_NO_PROGRESS_THRESHOLD = 3


class AttemptRecord(BaseModel):
    """One subagent fix/implement attempt against a single target.

    ``target`` identifies what the agent was working on — e.g.
    ``"tests/test_foo.py::test_bar"`` or any other task-specific stable key
    (file path, file path + test name, etc). ``outcome_signature`` is a
    normalized description of the result — error type plus assertion-message
    *shape* — deliberately excluding volatile fields (line numbers,
    timestamps) so repeated runs of the same unresolved failure compare
    equal instead of spuriously differing on noise.
    """

    model_config = ConfigDict(extra=EXTRA_FORBID, frozen=True)

    target: str = Field(min_length=1, description="Stable identity of the fix target.")
    outcome_signature: str = Field(
        min_length=1,
        description=(
            "Normalized outcome (error type + message shape); must exclude "
            "volatile fields such as line numbers or timestamps."
        ),
    )
    attempt_number: int = Field(
        ge=1, description="1-based attempt count for this target."
    )


class NoProgressResult(BaseModel):
    """Result of evaluating a run of attempt records for a stuck loop."""

    model_config = ConfigDict(extra=EXTRA_FORBID, frozen=True)

    tripped: bool
    target: str | None = None
    outcome_signature: str | None = None
    consecutive_count: int = 0


def detect_no_progress(
    records: Sequence[AttemptRecord],
    threshold: int = DEFAULT_NO_PROGRESS_THRESHOLD,
) -> NoProgressResult:
    """Flag N consecutive identical-outcome attempts against the same target.

    Only the *tail* of ``records`` (the most recent ``threshold`` entries in
    call order) is considered "consecutive". This deliberately avoids two
    false-positive classes:

    - A target change resets the run: if the agent moved on to a different
      file/test, older attempts against a prior target never count toward
      the new target's streak.
    - An outcome change resets the run: if the outcome signature changes
      between attempts on the *same* target (the fix had some effect, even
      if not a full fix), that is progress, not a stuck loop.
    """
    if threshold < 1:
        raise ValueError("threshold must be >= 1")
    if len(records) < threshold:
        return NoProgressResult(tripped=False)
    tail = records[-threshold:]
    first = tail[0]
    all_match = all(
        record.target == first.target
        and record.outcome_signature == first.outcome_signature
        for record in tail[1:]
    )
    if not all_match:
        return NoProgressResult(tripped=False)
    return NoProgressResult(
        tripped=True,
        target=first.target,
        outcome_signature=first.outcome_signature,
        consecutive_count=threshold,
    )


def attempt_records_from_json(raw: object) -> list[AttemptRecord]:
    """Parse a JSON-decoded ``attempt_history`` list into ``AttemptRecord``s.

    Tolerant of malformed entries (skips them): this reads agent-authored
    session data, not a validated API boundary, and a single bad entry must
    not crash the detector or block the subagent's retry loop.
    """
    if not isinstance(raw, list):
        return []
    raw_items = cast(list[object], raw)
    records: list[AttemptRecord] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            records.append(AttemptRecord.model_validate(item))
        except ValidationError:
            continue
    return records


def extract_attempt_history(
    phase_payload: dict[str, object],
) -> list[AttemptRecord]:
    """Pull the ``attempt_history`` list out of a pipeline_handoff phase payload.

    # BELIEF: ``phase_payload`` is agent-authored JSON read back from
    # ``pipeline_handoff``; ``attempt_history`` may be absent (first
    # attempt for this phase) or malformed (agent bug). Both cases are
    # treated as "no history yet" rather than raised, since evaluating the
    # monitor must never itself become a source of pipeline failures.
    """
    raw = phase_payload.get("attempt_history")
    return attempt_records_from_json(raw)


def build_report_message(result: NoProgressResult, threshold: int) -> str:
    """Build the pause/report message for the orchestrator.

    Mirrors the wording style of the existing MCP circuit-breaker report
    (see ``shared-conventions.md`` Circuit-Breaker Pattern) while using
    distinct trigger language ("no-progress monitor" / "identical outcome on
    target") so agents do not conflate the two independent signals.
    """
    return (
        f"No-progress monitor tripped after {threshold} consecutive attempts "
        f"with identical outcome on target '{result.target}'. Pausing for "
        "orchestrator re-plan/human check-in. To resume: address the root "
        "cause manually, then re-run the fix step — it will pick up from "
        "the current phase. "
        f"Outcome signature: {result.outcome_signature!r}."
    )
