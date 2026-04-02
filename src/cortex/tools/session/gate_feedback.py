"""Structured gate feedback models, extraction helpers, and handoff persistence."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Mapping, cast
from uuid import uuid4

from pydantic import BaseModel, Field

from cortex.core.context_logging import MCPContext

_log = logging.getLogger(__name__)


class GateName(str, Enum):
    """Supported gate kinds."""

    QUALITY = "quality"
    DOCS = "docs"


class GateError(BaseModel):
    """Single actionable gate failure."""

    file: str
    line: int | None = None
    check: str
    message: str
    fix_suggestion: str | None = None


class GateFeedback(BaseModel):
    """Structured summary of a gate failure."""

    gate: GateName
    run_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    errors: list[GateError]
    top_files: list[str]
    summary: str


def _status_is_failed(value: object) -> bool:
    status = str(value).strip().lower()
    return status in {"failed", "error"}


def _check_to_error(check: Mapping[str, object]) -> GateError | None:
    name = str(check.get("name", "check"))
    status = check.get("status")
    errors = check.get("errors")
    message = check.get("message")
    if not _status_is_failed(status):
        return None
    msg = str(message).strip() if isinstance(message, str) and message.strip() else name
    count_hint = f"errors={errors}" if isinstance(errors, int) else None
    return GateError(
        file=f"<{name}>",
        check=name,
        message=msg,
        fix_suggestion=count_hint,
    )


def _errors_from_checks(result: Mapping[str, object]) -> list[GateError]:
    checks_raw_obj = result.get("checks")
    if not isinstance(checks_raw_obj, list):
        return []
    checks_raw = cast(list[object], checks_raw_obj)
    errors: list[GateError] = []
    for item in checks_raw:
        if not isinstance(item, dict):
            continue
        err = _check_to_error(cast(dict[str, object], item))
        if err is not None:
            errors.append(err)
    return errors


def _top_files(errors: list[GateError]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for err in errors:
        if err.file in seen:
            continue
        seen.add(err.file)
        ordered.append(err.file)
    return ordered[:5]


def feedback_from_quality_result(result: Mapping[str, object]) -> GateFeedback | None:
    """Build feedback when run_quality_gate reports a failing run."""
    if bool(result.get("preflight_passed", True)):
        return None
    errors = _errors_from_checks(result)
    if not errors:
        # Preserve context even when checks payload is sparse.
        errors = [
            GateError(
                file="<quality>",
                check="quality-gate",
                message="Quality gate failed",
                fix_suggestion="Inspect gate checks and failing diagnostics.",
            )
        ]
    return GateFeedback(
        gate=GateName.QUALITY,
        errors=errors,
        top_files=_top_files(errors),
        summary=f"Quality gate failed with {len(errors)} issue group(s).",
    )


def feedback_from_docs_result(result: Mapping[str, object]) -> GateFeedback | None:
    """Build feedback when run_docs_gate reports a failing run."""
    if bool(result.get("docs_phase_passed", True)):
        return None
    errors = _errors_from_checks(result)
    if not errors:
        errors = [
            GateError(
                file="<docs>",
                check="docs-gate",
                message="Docs gate failed",
                fix_suggestion="Review timestamps and roadmap_sync checks.",
            )
        ]
    return GateFeedback(
        gate=GateName.DOCS,
        errors=errors,
        top_files=_top_files(errors),
        summary=f"Docs gate failed with {len(errors)} issue group(s).",
    )


async def persist_gate_feedback(
    feedback: GateFeedback | None,
    ctx: MCPContext | None,
) -> None:
    """Write failure feedback to handoff, or clear stale feedback on success."""
    from cortex.tools.session.pipeline_handoff import pipeline_handoff

    if feedback is None:
        result = await pipeline_handoff(
            operation="clear",
            pipeline="implement",
            phase="gate_feedback",
            ctx=ctx,
        )
    else:
        result = await pipeline_handoff(
            operation="write",
            pipeline="implement",
            phase="gate_feedback",
            data=feedback.model_dump(mode="json"),
            ctx=ctx,
        )
    if isinstance(result, dict):
        result_dict = cast(dict[str, object], result)
        if result_dict.get("status") == "error":
            error_value = result_dict.get("error")
            _log.warning(
                "persist_gate_feedback: handoff error: %s",
                str(error_value) if error_value is not None else "<unknown>",
            )
