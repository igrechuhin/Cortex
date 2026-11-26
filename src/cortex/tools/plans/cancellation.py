"""Public cancellation operation for an explicitly approved active plan."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.context_logging import MCPContext
from cortex.core.models import OperationStatus, PlanStatus
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.tools.models_base import StrictBaseModel
from cortex.tools.plans.cancellation_prepare import prepare_cancellation
from cortex.tools.plans.completion_transaction import run_completion_transaction
from cortex.tools.plans.completion_transaction_io import (
    completion_operations_root,
    operation_id,
    record_path,
)
from cortex.tools.plans.completion_transaction_models import (
    CancellationInput,
    CancellationRequest,
)
from cortex.tools.plans.completion_transaction_prepare import validate_plan_file_name

_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class CancelPlanResult(StrictBaseModel):
    """Preview or transaction receipt for archiving a cancelled plan."""

    status: OperationStatus
    message: str
    project_root: str
    dry_run: bool | None = None
    archive_path: str | None = None
    plan_status: PlanStatus | None = None
    before_sha256: str | None = None
    reason: str | None = None
    operation_id: str | None = None
    roadmap_line_removed: int | None = None
    idempotent_replay: bool = False
    recovery_required: bool = False
    error: str | None = None


def _request(slug: str | None, inputs: CancellationInput) -> CancellationRequest:
    if (
        slug is None
        or _SLUG.fullmatch(slug) is None
        or ".." in slug
        or slug.casefold().endswith(".md")
    ):
        raise ValueError("An exact root active plan slug without .md is required")
    name = validate_plan_file_name(f"{slug}.md")
    assert name is not None
    return CancellationRequest(
        plan_file_name=name,
        expected_sha256=inputs.expected_sha256,
        reason=inputs.reason,
    )


def _preview(root: Path, request: CancellationRequest) -> CancelPlanResult:
    receipt = record_path(completion_operations_root(root), operation_id(request))
    if receipt.exists() or receipt.is_symlink():
        raise ValueError("A transaction receipt already exists for this plan")
    prepared = prepare_cancellation(root, request)
    return CancelPlanResult(
        status=OperationStatus.SUCCESS,
        message="Plan cancellation preview.",
        project_root=str(root),
        dry_run=True,
        archive_path=str(prepared.destination),
        plan_status=PlanStatus.CANCELLED,
        before_sha256=request.expected_sha256,
        reason=request.reason,
        roadmap_line_removed=prepared.roadmap_line_removed,
    )


async def _apply(root: Path, request: CancellationRequest) -> CancelPlanResult:
    result = await run_completion_transaction(root, request)
    return CancelPlanResult(
        status=result.status,
        message=result.message,
        project_root=str(root),
        dry_run=False,
        archive_path=result.archive_path,
        plan_status=(
            PlanStatus.CANCELLED if result.status == OperationStatus.SUCCESS else None
        ),
        before_sha256=request.expected_sha256,
        reason=request.reason,
        operation_id=result.operation_id,
        roadmap_line_removed=result.roadmap_line_removed,
        idempotent_replay=result.idempotent_replay,
        recovery_required=result.recovery_required,
        error=result.error,
    )


async def archive_cancelled_plan(
    slug: str | None, content: str | None, ctx: MCPContext | None
) -> str:
    """Preview or archive one active plan without completing its work."""
    root = Path(await get_or_resolve_project_root(ctx)).absolute()
    try:
        if root != root.resolve():
            raise ValueError("Plan project root cannot traverse symlinks")
        inputs = CancellationInput.model_validate_json(content or "{}")
        request = _request(slug, inputs)
        result = (
            _preview(root, request) if inputs.dry_run else await _apply(root, request)
        )
    except (OSError, ValueError) as exc:
        result = CancelPlanResult(
            status=OperationStatus.ERROR,
            message="Plan cancellation rejected",
            project_root=str(root),
            error=str(exc),
        )
    return result.model_dump_json()
