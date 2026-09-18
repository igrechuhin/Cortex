"""Canonical check-name lists and phase enum for the commit pipeline.

Shared by ``run_quality_gate()`` (Phase A) and the detached job/result
plumbing, which hashes job ids from these check-name lists.
"""

from __future__ import annotations

from enum import Enum


class PreCommitPhase(str, Enum):
    A = "A"
    B = "B"
    FULL = "full"


# Canonical check names for each phase, used to hash detached job ids.
# Phase A preflight uses the same detached runner as run_quality_gate; markdown_lint
# is listed for job hashing and executed inside the detached worker (CI rumdl parity).
_PHASE_A_CHECKS: tuple[str, ...] = (
    "fix_errors",
    "format",
    "synapse_format",
    "synapse_lint",
    "type_check",
    "quality",
    "spelling",
    "tests",
    "eval_fast",
    "markdown_lint",
)
# Phase B is handled inline by run_docs_and_memory_bank_sync_impl; expose a
# sentinel check name so callers can form a deterministic job_id hash.
_PHASE_B_CHECKS: tuple[str, ...] = ("docs_and_memory_sync",)

# Public aliases for tests and external callers that should not rely on
# underscored module internals.
PHASE_A_CHECKS: tuple[str, ...] = _PHASE_A_CHECKS
PHASE_B_CHECKS: tuple[str, ...] = _PHASE_B_CHECKS


def phase_to_checks(phase: PreCommitPhase) -> list[str]:
    """Return canonical check name list for a phase.

    Args:
        phase: Phase enum value (A, B, or FULL).

    Returns:
        List of check name strings for the given phase.
    """
    if phase is PreCommitPhase.A:
        return list(_PHASE_A_CHECKS)
    if phase is PreCommitPhase.B:
        return list(_PHASE_B_CHECKS)
    return list(_PHASE_A_CHECKS + _PHASE_B_CHECKS)
