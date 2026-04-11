"""Task graph nodes for parallel execution markers in plan markdown.

Section headings use ``###`` (or deeper) with a step label. Supported markers:

- **Sequential (default)** — e.g. ``### Step 1: Do thing`` — not parallelized.
- **Parallel** — ``### [P] Step 2: Independent work`` — may run concurrently when
  its ``depends_on`` steps are complete.
- **Parallel with explicit deps** — ``### [P:after=1,3] Step 4: Follow-up`` —
  parallel only after steps 1 and 3; those ids populate ``depends_on``.

Parsing and validation (cycles, missing step refs) live in ``plan_utils`` (see
parallel task markers plan).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def _empty_step_dependencies() -> list[int]:
    return []


class TaskNode(BaseModel):
    """One implementation step extracted from a plan document."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    step_id: int = Field(
        ...,
        ge=1,
        description="1-based step index derived from heading order in the plan.",
    )
    title: str = Field(
        ...,
        description="Display title for the step (marker tokens stripped by the parser).",
    )
    parallel: bool = Field(
        ...,
        description="True when the heading carried a [P] parallel marker.",
    )
    depends_on: list[int] = Field(
        default_factory=_empty_step_dependencies,
        description="Step ids that must finish before this step may run in parallel.",
    )
    content: str = Field(
        default="",
        description="Markdown body under the heading until the next peer heading.",
    )
