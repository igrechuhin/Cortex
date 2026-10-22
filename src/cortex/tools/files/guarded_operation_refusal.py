"""Explicit domain refusals; ordinary validation and I/O errors stay unclassified."""

from pathlib import Path

from cortex.tools.files.guarded_operation_outcome import GuardedOperationOutcome
from cortex.tools.plans.completion_transaction_io import validate_contained_path


class GuardedOperationRefusal(ValueError):
    """Preserve guard diagnostics alongside a stable finite outcome."""

    def __init__(
        self,
        message: str,
        code: GuardedOperationOutcome = GuardedOperationOutcome.POLICY_BLOCKED,
    ) -> None:
        super().__init__(message)
        self.code = code


def validate_guarded_path(target: Path, root: Path) -> None:
    """Classify only the established containment/symlink policy seam."""
    try:
        validate_contained_path(target, root)
    except ValueError as exc:
        raise GuardedOperationRefusal(str(exc)) from exc
