"""Response payload model for run_tool_evaluation.

Split out of ``_models.py`` for file-size compliance (<400 lines).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import OperationStatus
from cortex.core.pydantic_extra import EXTRA_FORBID

from ._agentic_models import AgenticSummary
from ._models import ExecutionSummary


class RunToolEvaluationPayload(BaseModel):
    """JSON-serializable payload for run_tool_evaluation response."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    status: OperationStatus = OperationStatus.SUCCESS
    project_root: str = Field(description="Project root path")
    tasks_loaded: int = Field(ge=0, description="Number of tasks loaded")
    generated_at: str = Field(description="Suite generation timestamp")
    cache_file: str = Field(description="Path to last_suite.json")
    suite: dict[str, object] = Field(
        description="Suite result as JSON-serializable dict"
    )
    analysis: dict[str, object] = Field(
        description="Analysis result as JSON-serializable dict"
    )
    dashboard_path: str | None = Field(
        default=None, description="Relative path to dashboard.md"
    )
    execution_summary: ExecutionSummary | None = Field(
        default=None,
        description="Pass/fail summary for execution-based evals (when mode runs executions).",
    )
    agentic_summary: AgenticSummary | None = Field(
        default=None,
        description="Paired selection scorecard and model feedback (agentic mode only).",
    )
