"""Exact revisions of inputs selected by the existing scoped context builder."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.tools.context.scoped_source_state import ScopedSourceState


class SourceRevision(BaseModel):
    """A source identity and the digest of the exact bytes used, not its mtime."""

    model_config = ConfigDict(extra=EXTRA_FORBID, frozen=True)

    identity: str
    kind: str
    reference: str
    provenance: str
    revision: str | None = None
    state: ScopedSourceState = ScopedSourceState.PRESENT
