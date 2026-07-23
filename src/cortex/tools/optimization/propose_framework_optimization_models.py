"""Pydantic models for the propose_framework_optimization MCP tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID


class ProposedFileChange(BaseModel):
    """One proposed file write, scoped to ``.cortex/synapse/`` or ``.cortex/rules/``.

    # AI: Full replacement content (not a unified diff) is required from the
    # caller. Parsing/validating arbitrary unified diffs is a much larger
    # attack surface (hunk offsets, fuzz matching) than comparing full
    # before/after content; the reviewable "diff" artifact is generated
    # internally from this content, not supplied by the caller.
    """

    model_config = ConfigDict(extra=EXTRA_FORBID)

    relative_path: str = Field(
        description=(
            "Project-root-relative path, e.g. '.cortex/rules/general/foo.mdc' "
            "or '.cortex/synapse/rules/bar.mdc'."
        )
    )
    new_content: str = Field(description="Full proposed file content (not a diff).")


class ProposeFrameworkOptimizationRequest(BaseModel):
    """Input for propose_framework_optimization: a batch of changes plus rationale."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    changes: list[ProposedFileChange] = Field(min_length=1)
    rationale: str = Field(
        min_length=1,
        description="Why this change addresses a specific observed edge case.",
    )


class ProposeFrameworkOptimizationResult(BaseModel):
    """Output: self-test outcome, formatted diff, rationale, or failure reason."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    self_test_passed: bool
    diff: str
    rationale: str
    failure_reason: str | None = None
    changed_paths: list[str] = Field(default_factory=list)
