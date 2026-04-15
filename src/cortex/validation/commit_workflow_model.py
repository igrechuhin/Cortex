"""
Commit Workflow Model

Data-only model for commit procedure step metadata (ordering, parallelization).
Used by tests and tooling to assert invariants; commit execution is prompt-driven.
"""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID

_PARALLEL_GROUP_9_11 = "validation_parallel_block_9_11"

_STEP_NAMES: dict[int, str] = {
    0: "error-fixer",
    1: "code-formatter",
    2: "type-checker",
    3: "quality-checker",
    4: "test-executor",
    5: "memory-bank-updater",
    6: "memory-bank-updater",
    7: "plan-archiver",
    8: "plan-archiver",
    9: "timestamp-validator",
    10: "roadmap-sync-validator",
    11: "submodule-handling",
    12: "final-validation-gate",
    13: "commit-creation",
    14: "push-branch",
}


class CommitStepMetadata(BaseModel):
    """Metadata for a single commit workflow step."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    step_id: int = Field(description="Step number (0–14)")
    name: str = Field(description="Step name/slug")
    can_run_in_parallel: bool = Field(
        description="Whether this step may run in a parallel block"
    )
    group_id: str | None = Field(
        default=None,
        description="Id of parallel group if can_run_in_parallel else None",
    )


def get_commit_steps_metadata() -> list[CommitStepMetadata]:
    """Return metadata for all commit workflow steps in order.

    Returns:
        List of step metadata; steps 9–11 share group_id and can_run_in_parallel.
    """
    result: list[CommitStepMetadata] = []
    for step_id, name in _STEP_NAMES.items():
        can_parallel = step_id in (9, 10, 11)
        group_id = _PARALLEL_GROUP_9_11 if can_parallel else None
        result.append(
            CommitStepMetadata(
                step_id=step_id,
                name=name,
                can_run_in_parallel=can_parallel,
                group_id=group_id,
            )
        )
    return result


def get_parallel_block_step_ids() -> tuple[int, ...]:
    """Return step ids that form the parallel validation/submodule block.

    Returns:
        Tuple (9, 10, 11).
    """
    return (9, 10, 11)


def get_sequential_step_ranges() -> list[tuple[int, int]]:
    """Return (start, end) ranges that must run sequentially.

    Returns:
        [(0, 8), (12, 14)] meaning steps 0–8 and 12–14 are sequential.
    """
    return [(0, 8), (12, 14)]
