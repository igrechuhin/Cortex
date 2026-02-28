"""Pydantic models for query_usage dispatch parameters."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import ResponseFormat


class QueryUsageParams(BaseModel):
    """Parameters for query_usage dispatch; all query types use a subset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_date: str | None = None
    end_date: str | None = None
    tool_name: str | None = None
    response_format: ResponseFormat = ResponseFormat.CONCISE
    days: int = 30
    min_usage_count: int = 0
    min_usage_threshold: int = 5
    ids: list[str] = Field(default_factory=list)
    observation_id: str | None = None
    around_id: str | None = None
    success: bool | None = None
    limit: int = 50
    query: str | None = None
    format: str = "markdown"
    include_recommendations: bool = True
    hours: int | None = None
    production_baseline_days: int = 7
    production_window_hours: int = 24
    days_baseline: int = 7
    current_window_hours: int = 24
