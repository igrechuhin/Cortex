"""Helpers for Phase B docs and memory bank validations in the commit pipeline.

This module contains the pure business logic for `run_docs_and_memory_bank_sync`.
Keeping helpers in a separate module allows the MCP tool registration module
to stay small and within line-count limits while preserving testability and
type safety.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import (
    JsonDict,
    JsonValue,
    ModelDict,
    OperationStatus,
    ResponseFormat,
)
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.models import (
    DocsAndMemoryBankSyncErrorResult,
    DocsAndMemoryBankSyncResult,
    PreflightCheckSummary,
)
from cortex.tools.validation.operations import (
    ValidateCheckTypeName,
    validate_from_parsed,
)
from cortex.validation.roadmap_progress_consistency import (
    check_roadmap_progress_consistency,
)


async def _decode_validation_result(
    raw: str,
    check_name: str,
    ctx: MCPContext | None,
) -> JsonDict | None:
    """Decode JSON string from validate() into a dict."""
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        await log_client(
            ctx,
            "error",
            f"run_docs_and_memory_bank_sync: failed to decode {check_name} result: {exc!s}",
            logger_name=__name__,
        )
        return None
    if not isinstance(decoded, dict):
        await log_client(
            ctx,
            "error",
            f"run_docs_and_memory_bank_sync: {check_name} result was not a JSON object",
            logger_name=__name__,
        )
        return None
    return cast(JsonDict, decoded)


async def run_single_validation(
    check_type_name: ValidateCheckTypeName,
    ctx: MCPContext | None,
) -> JsonDict | None:
    """Run validation for a single check_type and decode JSON result.

    Calls ``validate_from_parsed`` directly instead of the ``validate_impl``
    MCP tool wrapper to avoid nested semaphore acquisition.  ``run_docs_gate``
    already holds one tool-semaphore slot; calling ``validate_impl`` (which is
    wrapped with ``@mcp_tool_wrapper``) would acquire additional slots from the
    same 5-slot pool, creating a deadlock when two ``run_docs_gate`` calls run
    concurrently.
    """
    raw = await validate_from_parsed(
        check_type_name,
        file_name=None,
        similarity_threshold=None,
        suggest_fixes=True,
        check_commit_ci_alignment=True,
        check_code_quality_consistency=True,
        check_documentation_consistency=True,
        check_config_consistency=True,
        ctx=ctx,
        response_format=ResponseFormat.CONCISE,
    )
    return await _decode_validation_result(raw, check_type_name, ctx)


async def _read_utf8_if_exists(path: Path) -> str:
    """Read file as UTF-8 text, or empty string when missing."""
    if not path.exists():
        return ""
    return await asyncio.to_thread(path.read_text, encoding="utf-8")


async def _roadmap_progress_consistency_violations(ctx: MCPContext | None) -> list[str]:
    """Load memory-bank progress/roadmap and run backlog consistency rules."""
    root = await resolve_project_root_async(None, ctx)
    mb = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    progress_text, roadmap_text = await asyncio.gather(
        _read_utf8_if_exists(mb / MemoryBankFile.PROGRESS),
        _read_utf8_if_exists(mb / MemoryBankFile.ROADMAP),
    )
    return check_roadmap_progress_consistency(progress_text, roadmap_text)


async def _run_docs_and_memory_bank_phase_tools(
    ctx: MCPContext | None,
) -> tuple[JsonDict | None, JsonDict | None]:
    """Run validate() for timestamps and roadmap_sync once for docs/memory phase."""
    timestamps_result = await run_single_validation(
        ValidateCheckTypeName.TIMESTAMPS, ctx
    )
    roadmap_result = await run_single_validation(
        ValidateCheckTypeName.ROADMAP_SYNC, ctx
    )
    return timestamps_result, roadmap_result


def _docs_memory_bank_has_tool_error(result: JsonDict | None) -> bool:
    """Return True when a validation result reports a tool-level error."""
    if result is None:
        return False
    status_value: JsonValue | None = result.get("status")
    return str(status_value) == "error"


def compute_docs_memory_bank_passed(
    timestamps_result: JsonDict | None,
    roadmap_result: JsonDict | None,
    consistency_violations: list[str],
) -> bool:
    """Determine whether docs/memory validations passed.

    roadmap_progress_consistency violations are errors (zero-problems policy).
    """
    ts_valid = True
    if timestamps_result is not None:
        ts_valid = bool(timestamps_result.get("valid", False))
    roadmap_valid = True
    if roadmap_result is not None:
        roadmap_valid = bool(roadmap_result.get("valid", False))
    consistency_valid = len(consistency_violations) == 0
    return ts_valid and roadmap_valid and consistency_valid


def build_timestamps_summary(
    timestamps_result: JsonDict | None,
) -> PreflightCheckSummary | None:
    """Build summary entry for timestamps validation."""
    if timestamps_result is None:
        return None
    valid_flag = bool(timestamps_result.get("valid", False))
    status = OperationStatus.SUCCESS if valid_flag else OperationStatus.ERROR
    invalid_format = timestamps_result.get("total_invalid_format")
    invalid_with_time = timestamps_result.get("total_invalid_with_time")
    errors_count = 0
    if isinstance(invalid_format, int):
        errors_count += invalid_format
    if isinstance(invalid_with_time, int):
        errors_count += invalid_with_time
    message_obj = timestamps_result.get("message")
    message = str(message_obj) if message_obj else None
    return PreflightCheckSummary(
        name="timestamps",
        status=status,
        errors=errors_count or None,
        warnings=None,
        message=message,
    )


def build_roadmap_sync_summary(
    roadmap_result: JsonDict | None,
) -> PreflightCheckSummary | None:
    """Build summary entry for roadmap_sync validation."""
    if roadmap_result is None:
        return None
    valid_flag = bool(roadmap_result.get("valid", False))
    status = OperationStatus.SUCCESS if valid_flag else OperationStatus.ERROR
    summary_obj = roadmap_result.get("summary", {})
    errors_count: int | None = None
    warnings_count: int | None = None
    if isinstance(summary_obj, dict):
        missing = summary_obj.get("missing_entries_count")
        invalid = summary_obj.get("invalid_references_count")
        completed = summary_obj.get("completed_entries_count")
        warnings = summary_obj.get("warnings_count")
        total_errors = 0
        for value in (missing, invalid, completed):
            if isinstance(value, int):
                total_errors += value
        errors_count = total_errors or None
        warnings_count = warnings if isinstance(warnings, int) else None
    return PreflightCheckSummary(
        name="roadmap_sync",
        status=status,
        errors=errors_count,
        warnings=warnings_count,
        message=None,
    )


def _build_roadmap_progress_consistency_summary(
    violations: list[str],
) -> PreflightCheckSummary:
    """Summary for progress-vs-roadmap backlog invariant (error when violated)."""
    return PreflightCheckSummary(
        name="roadmap_progress_consistency",
        status=OperationStatus.ERROR if violations else OperationStatus.SUCCESS,
        errors=len(violations) if violations else None,
        warnings=None,
        message="; ".join(violations) if violations else None,
    )


def build_docs_memory_bank_summaries(
    timestamps_result: JsonDict | None,
    roadmap_result: JsonDict | None,
    consistency_violations: list[str],
) -> list[PreflightCheckSummary]:
    """Build summaries for docs/memory validations."""
    summaries: list[PreflightCheckSummary] = []
    ts_summary = build_timestamps_summary(timestamps_result)
    if ts_summary is not None:
        summaries.append(ts_summary)
    roadmap_summary = build_roadmap_sync_summary(roadmap_result)
    if roadmap_summary is not None:
        summaries.append(roadmap_summary)
    summaries.append(
        _build_roadmap_progress_consistency_summary(consistency_violations),
    )
    return summaries


def _build_docs_memory_bank_success_model(
    timestamps_result: JsonDict | None,
    roadmap_result: JsonDict | None,
    consistency_violations: list[str],
) -> ModelDict:
    """Assemble the success payload after validate() results are decoded."""
    passed = compute_docs_memory_bank_passed(
        timestamps_result,
        roadmap_result,
        consistency_violations,
    )
    summaries = build_docs_memory_bank_summaries(
        timestamps_result,
        roadmap_result,
        consistency_violations,
    )
    ok = DocsAndMemoryBankSyncResult(
        docs_phase_passed=passed,
        checks=summaries,
        timestamps_result=timestamps_result,
        roadmap_sync_result=roadmap_result,
    )
    return cast(ModelDict, ok.model_dump(mode="json"))


def build_docs_memory_bank_model(
    timestamps_result: JsonDict | None,
    roadmap_result: JsonDict | None,
    consistency_violations: list[str],
) -> ModelDict:
    """Build success or error model for run_docs_and_memory_bank_sync."""
    if _docs_memory_bank_has_tool_error(timestamps_result) or (
        _docs_memory_bank_has_tool_error(roadmap_result)
    ):
        err = DocsAndMemoryBankSyncErrorResult(
            error=(
                "run_docs_and_memory_bank_sync: underlying validation error during "
                "docs/memory bank phase"
            ),
            error_type="DocsMemoryBankToolError",
            timestamps_result=timestamps_result,
            roadmap_sync_result=roadmap_result,
        )
        return cast(ModelDict, err.model_dump(mode="json"))
    return _build_docs_memory_bank_success_model(
        timestamps_result,
        roadmap_result,
        consistency_violations,
    )


async def run_docs_and_memory_bank_sync_impl(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Core implementation for run_docs_and_memory_bank_sync (no logging wrapper)."""
    timestamps_result, roadmap_result = await _run_docs_and_memory_bank_phase_tools(
        ctx,
    )
    violations = await _roadmap_progress_consistency_violations(ctx)
    return build_docs_memory_bank_model(
        timestamps_result,
        roadmap_result,
        violations,
    )


__all__ = ["run_docs_and_memory_bank_sync_impl"]
