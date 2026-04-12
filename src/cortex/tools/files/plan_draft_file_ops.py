"""List and discard step-by-step plan drafts under ``.cortex/plans/``."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cortex.core.models import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.files.operation_helpers import (
    FileOperation,
    build_invalid_operation_error,
)
from cortex.tools.response_builder import error_response

_STALE_DRAFT_HOURS = 48


def validate_discard_draft_content(content: str | None) -> str | None:
    """Return error JSON if ``content`` is not valid discard payload; else ``None``."""
    if content is None or not str(content).strip():
        return json.dumps(
            error_response(
                error='content is required for discard_draft (JSON: {"plan_slug": "<stem>"})',
                error_type="ValueError",
            ),
            indent=2,
        )
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return json.dumps(
            error_response(
                error="content must be JSON with plan_slug",
                error_type="ValueError",
            ),
            indent=2,
        )
    slug = data.get("plan_slug")
    if not isinstance(slug, str) or not slug.strip():
        return json.dumps(
            error_response(
                error="plan_slug is required and must be a non-empty string",
                error_type="ValueError",
            ),
            indent=2,
        )
    return None


def count_stale_plan_drafts(root: Path, stale_hours: int = _STALE_DRAFT_HOURS) -> int:
    """Count ``draft-*.md`` files in the plans directory older than ``stale_hours``."""
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    if not plans_dir.is_dir():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
    stale = 0
    for path in plans_dir.glob("draft-*.md"):
        if not path.is_file():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            stale += 1
    return stale


def _collect_plan_draft_rows(
    plans_dir: Path, root: Path, cutoff: datetime
) -> tuple[list[dict[str, object]], int]:
    drafts: list[dict[str, object]] = []
    stale_count = 0
    for path in sorted(plans_dir.glob("draft-*.md")):
        if not path.is_file():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        is_stale = mtime < cutoff
        if is_stale:
            stale_count += 1
        drafts.append(
            {
                "path": str(path.relative_to(root)),
                "modified_utc": mtime.isoformat(),
                "stale": is_stale,
            }
        )
    return drafts, stale_count


def list_plan_drafts(root: Path) -> str:
    """Return JSON listing ``draft-*.md`` with modification time and stale flag."""
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    if not plans_dir.is_dir():
        return json.dumps(
            {
                "status": OperationStatus.SUCCESS.value,
                "drafts": [],
                "count": 0,
                "stale_count": 0,
            },
            indent=2,
        )
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_STALE_DRAFT_HOURS)
    drafts, stale_count = _collect_plan_draft_rows(plans_dir, root, cutoff)
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "drafts": drafts,
            "count": len(drafts),
            "stale_count": stale_count,
        },
        indent=2,
    )


def discard_plan_draft(root: Path, content: str | None) -> str:
    """Delete ``draft-<slug>.md`` after validating JSON with a ``plan_slug`` field."""
    err = validate_discard_draft_content(content)
    if err is not None:
        return err
    assert content is not None
    data = json.loads(content)
    slug = data.get("plan_slug")
    assert isinstance(slug, str)
    base = slug.strip().removeprefix("draft-").removesuffix(".md")
    path = get_cortex_path(root, CortexResourceType.PLANS) / f"draft-{base}.md"
    if not path.is_file():
        return json.dumps(
            error_response(
                error=f"draft not found: {path.name}",
                error_type="FileNotFoundError",
            ),
            indent=2,
        )
    rel = str(path.relative_to(root))
    path.unlink()
    return json.dumps(
        {"status": OperationStatus.SUCCESS.value, "deleted": rel}, indent=2
    )


def execute_plan_draft_operation(
    root: Path, operation: FileOperation, content: str | None
) -> str:
    """Run ``list_drafts`` or ``discard_draft``."""
    if operation == FileOperation.LIST_DRAFTS:
        return list_plan_drafts(root)
    if operation == FileOperation.DISCARD_DRAFT:
        return discard_plan_draft(root, content)
    return build_invalid_operation_error(operation.value)
