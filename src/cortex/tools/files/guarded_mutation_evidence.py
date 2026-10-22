"""Observed evidence shared by the two existing guarded mutation boundaries."""

import hashlib
from pathlib import Path

from pydantic import BaseModel

from cortex.tools.files.guarded_operation_refusal import GuardedOperationRefusal


class GuardedMutationEvidence(BaseModel):
    """Only validated reads and successful replacement establish file evidence."""

    target: str | None = None
    before_sha256: str | None = None
    after_sha256: str | None = None
    mutation_performed: bool = False

    def observe(self, root: Path, target: Path) -> bytes:
        """Record the exact bytes read after the caller validates its target."""
        before = target.read_bytes()
        self.target = target.relative_to(root).as_posix()
        self.before_sha256 = hashlib.sha256(before).hexdigest()
        return before

    def replaced(self, after: bytes) -> None:
        """Record replacement before cleanup or lock release can fail."""
        self.mutation_performed = True
        self.after_sha256 = hashlib.sha256(after).hexdigest()

    def error_fields(self, exc: Exception) -> dict[str, object]:
        """Never turn a post-replacement error into a no-mutation assertion."""
        return {
            **self.model_dump(exclude_none=True),
            "target": self.target,
            "status": "error",
            "error": str(exc),
            "error_type": type(exc).__name__,
            **(
                {"code": exc.code.value}
                if isinstance(exc, GuardedOperationRefusal)
                else {}
            ),
        }
