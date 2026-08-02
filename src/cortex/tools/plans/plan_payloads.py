"""
Pydantic payload models and argument builders for the plan MCP tool.

Enables callers (orchestrators, tests) to build full JSON payloads for
plan(operation="create"|"complete"|"register") instead of relying on
tool-side defaults or name-only invocations.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from cortex.tools.models_base import StrictBaseModel


class PlanOperation(str, Enum):
    """Allowed operations for the plan MCP tool."""

    CREATE = "create"
    LIST = "list"
    GET = "get"
    COMPLETE = "complete"
    REGISTER = "register"


class PlanCreatePayload(StrictBaseModel):
    """Payload for plan(operation='create')."""

    operation: PlanOperation = Field(default=PlanOperation.CREATE)
    title: str = Field(..., min_length=1, description="Plan title")
    content: str = Field(..., min_length=1, description="Plan markdown content")
    slug: str | None = Field(None, description="Filename slug (no .md)")
    explore_log_path: str | None = Field(
        None,
        description=(
            "Optional explore decision log path (for example "
            "`.cortex/plans/explore/decision-log-foo.md`) used to build "
            "`## Decision Basis` in created plans"
        ),
    )
    shape_log_path: str | None = Field(
        None,
        description=(
            "Optional shaping record path (for example "
            "`.cortex/plans/shape/shape-foo.md`) whose resolved decisions become "
            "`## Shaping Constraints` in created plans"
        ),
    )
    include_archive: bool = Field(False, description="Include archive when listing")
    response_format: str = Field("content", description="Response format")


class PlanCompletePayload(StrictBaseModel):
    """Payload for plan(operation='complete')."""

    operation: PlanOperation = Field(default=PlanOperation.COMPLETE)
    plan_title: str = Field(
        ..., min_length=1, description="Title of the plan to complete"
    )
    summary: str = Field(..., min_length=1, description="Completion summary")
    completion_date: str | None = Field(None, description="ISO completion date")
    progress_entry: str | None = Field(
        None, description="Entry to append to progress.md"
    )
    plan_file_name: str | None = Field(None, description="Plan filename to archive")


class PlanRegisterPayload(StrictBaseModel):
    """Payload for plan(operation='register')."""

    operation: PlanOperation = Field(default=PlanOperation.REGISTER)
    plan_title: str = Field(..., min_length=1, description="Plan title for roadmap")
    description: str = Field(..., min_length=1, description="Roadmap entry description")
    status: str = Field("PENDING", description="Roadmap status")
    section: str = Field("pending", description="Roadmap section")
    plan_file_name: str | None = Field(
        None,
        description="Optional plan filename to append as `Plan: .cortex/plans/<file>.md`",
    )
    plan_relative_path: str | None = Field(
        None,
        description=(
            "Optional canonical plan path (for example `.cortex/plans/foo.md`) "
            "to append as `Plan: ...`; takes precedence over plan_file_name"
        ),
    )


PlanPayload = PlanCreatePayload | PlanCompletePayload | PlanRegisterPayload


def to_plan_arguments(payload: PlanPayload) -> dict[str, object]:
    """Convert a plan payload model to the dict expected by the plan MCP tool.

    Returns a JSON-serializable dict with only non-None optional fields,
    suitable for MCP tool arguments or plan(**kwargs) in tests.
    """
    return payload.model_dump(exclude_none=True, by_alias=False)


def build_plan_complete_arguments(
    plan_title: str,
    summary: str,
    *,
    completion_date: str | None = None,
    progress_entry: str | None = None,
    plan_file_name: str | None = None,
) -> dict[str, object]:
    """Build the arguments dict for plan(operation='complete', ...)."""
    return to_plan_arguments(
        PlanCompletePayload(
            plan_title=plan_title,
            summary=summary,
            completion_date=completion_date,
            progress_entry=progress_entry,
            plan_file_name=plan_file_name,
        )
    )


def build_plan_register_arguments(
    plan_title: str,
    description: str,
    *,
    status: str = "PENDING",
    section: str = "pending",
    plan_file_name: str | None = None,
    plan_relative_path: str | None = None,
) -> dict[str, object]:
    """Build the arguments dict for plan(operation='register', ...)."""
    return to_plan_arguments(
        PlanRegisterPayload(
            plan_title=plan_title,
            description=description,
            status=status,
            section=section,
            plan_file_name=plan_file_name,
            plan_relative_path=plan_relative_path,
        )
    )


def build_plan_create_arguments(
    title: str,
    content: str,
    *,
    slug: str | None = None,
    explore_log_path: str | None = None,
    shape_log_path: str | None = None,
    include_archive: bool = False,
    response_format: str = "content",
) -> dict[str, object]:
    """Build the arguments dict for plan(operation='create', ...)."""
    return to_plan_arguments(
        PlanCreatePayload(
            title=title,
            content=content,
            slug=slug,
            explore_log_path=explore_log_path,
            shape_log_path=shape_log_path,
            include_archive=include_archive,
            response_format=response_format,
        )
    )
