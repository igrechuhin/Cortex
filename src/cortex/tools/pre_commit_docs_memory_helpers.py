"""Helpers for Phase B docs and memory bank validations in the commit pipeline.

This module contains the pure business logic for `run_docs_and_memory_bank_sync`.
Keeping helpers in a separate module allows the MCP tool registration module
to stay small and within line-count limits while preserving testability and
type safety.
"""

from __future__ import annotations

import json
from typing import cast

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import JsonDict, JsonValue, ModelDict
from cortex.tools.models import (
    DocsAndMemoryBankSyncErrorResult,
    DocsAndMemoryBankSyncResult,
    PreflightCheckSummary,
)
from cortex.tools.validation_operations import ValidateCheckTypeName, validate


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


async def _run_single_validation(
    check_type_name: ValidateCheckTypeName,
    ctx: MCPContext | None,
) -> JsonDict | None:
    """Run validate() for a single check_type and decode JSON result."""
    raw = await validate(
        check_type=check_type_name,
        file_name=None,
        strict_mode=False,
        similarity_threshold=None,
        suggest_fixes=True,
        check_commit_ci_alignment=True,
        check_code_quality_consistency=True,
        check_documentation_consistency=True,
        check_config_consistency=True,
        ctx=ctx,
    )
    return await _decode_validation_result(raw, check_type_name, ctx)


async def _run_docs_and_memory_bank_phase_tools(
    ctx: MCPContext | None,
) -> tuple[JsonDict | None, JsonDict | None]:
    """Run validate() for timestamps and roadmap_sync once for docs/memory phase."""
    timestamps_result = await _run_single_validation("timestamps", ctx)
    roadmap_result = await _run_single_validation("roadmap_sync", ctx)
    return timestamps_result, roadmap_result


def _docs_memory_bank_has_tool_error(result: JsonDict | None) -> bool:
    """Return True when a validation result reports a tool-level error."""
    if result is None:
        return False
    status_value: JsonValue | None = result.get("status")
    return str(status_value) == "error"


def _compute_docs_memory_bank_passed(
    timestamps_result: JsonDict | None,
    roadmap_result: JsonDict | None,
) -> bool:
    """Determine whether docs/memory validations passed with zero errors."""
    ts_valid = True
    if timestamps_result is not None:
        ts_valid = bool(timestamps_result.get("valid", False))
    roadmap_valid = True
    if roadmap_result is not None:
        roadmap_valid = bool(roadmap_result.get("valid", False))
    return ts_valid and roadmap_valid


def _build_timestamps_summary(
    timestamps_result: JsonDict | None,
) -> PreflightCheckSummary | None:
    """Build summary entry for timestamps validation."""
    if timestamps_result is None:
        return None
    valid_flag = bool(timestamps_result.get("valid", False))
    status = "success" if valid_flag else "error"
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


def _build_roadmap_sync_summary(
    roadmap_result: JsonDict | None,
) -> PreflightCheckSummary | None:
    """Build summary entry for roadmap_sync validation."""
    if roadmap_result is None:
        return None
    valid_flag = bool(roadmap_result.get("valid", False))
    status = "success" if valid_flag else "error"
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


def _build_docs_memory_bank_summaries(
    timestamps_result: JsonDict | None,
    roadmap_result: JsonDict | None,
) -> list[PreflightCheckSummary]:
    """Build summaries for docs/memory validations."""
    summaries: list[PreflightCheckSummary] = []
    ts_summary = _build_timestamps_summary(timestamps_result)
    if ts_summary is not None:
        summaries.append(ts_summary)
    roadmap_summary = _build_roadmap_sync_summary(roadmap_result)
    if roadmap_summary is not None:
        summaries.append(roadmap_summary)
    return summaries


def _build_docs_memory_bank_model(
    timestamps_result: JsonDict | None,
    roadmap_result: JsonDict | None,
) -> ModelDict:
    """Build success or error model for run_docs_and_memory_bank_sync."""
    if _docs_memory_bank_has_tool_error(timestamps_result) or (
        _docs_memory_bank_has_tool_error(roadmap_result)
    ):
        error_model = DocsAndMemoryBankSyncErrorResult(
            error=(
                "run_docs_and_memory_bank_sync: underlying validation error during "
                "docs/memory bank phase"
            ),
            error_type="DocsMemoryBankToolError",
            timestamps_result=timestamps_result,
            roadmap_sync_result=roadmap_result,
        )
        return cast(ModelDict, error_model.model_dump(mode="json"))

    docs_phase_passed = _compute_docs_memory_bank_passed(
        timestamps_result,
        roadmap_result,
    )
    summaries = _build_docs_memory_bank_summaries(timestamps_result, roadmap_result)
    result_model = DocsAndMemoryBankSyncResult(
        docs_phase_passed=docs_phase_passed,
        checks=summaries,
        timestamps_result=timestamps_result,
        roadmap_sync_result=roadmap_result,
    )
    return cast(ModelDict, result_model.model_dump(mode="json"))


async def run_docs_and_memory_bank_sync_impl(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Core implementation for run_docs_and_memory_bank_sync (no logging wrapper)."""
    timestamps_result, roadmap_result = await _run_docs_and_memory_bank_phase_tools(
        ctx,
    )
    return _build_docs_memory_bank_model(timestamps_result, roadmap_result)


__all__ = ["run_docs_and_memory_bank_sync_impl"]
