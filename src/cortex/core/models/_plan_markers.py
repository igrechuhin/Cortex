"""Plan document models for inline ambiguity markers.

Marker formats (inline in markdown plan bodies):
- ``[NEEDS CLARIFICATION: <reason>]`` — non-blocking by default.
- ``[NEEDS CLARIFICATION(blocking): <reason>]`` — must be resolved before implementation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID


class ClarificationMarker(BaseModel):
    """One unresolved or resolved clarification marker extracted from plan text."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    reason: str = Field(
        ...,
        description="Human-readable ambiguity description from the marker body.",
    )
    blocking: bool = Field(
        default=False,
        description="True when the marker used the (blocking) attribute.",
    )
    location: str = Field(
        ...,
        description="Where the marker appeared (e.g. line number or section hint).",
    )
    resolved: bool = Field(
        default=False,
        description="False for markers still present in the document.",
    )
