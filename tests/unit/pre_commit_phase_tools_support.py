"""Shared factories and helpers for pre-commit phase A/B tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

from cortex.core.models import JsonValue, ModelDict
from cortex.tools.execution.pre_commit_tools import execute_pre_commit_checks


def get_checks_list(result: ModelDict) -> list[dict[str, object]]:
    """Extract list of check dicts from phase result; safe for Pyright (JsonValue)."""
    raw = result.get("checks", [])
    if not isinstance(raw, list):
        return []
    return cast(list[dict[str, object]], [x for x in raw if isinstance(x, dict)])


def phase_b_timestamps_payload(
    *,
    valid: bool,
    total_invalid_format: int = 0,
    total_invalid_with_time: int = 0,
) -> dict[str, object]:
    return {
        "status": "success",
        "check_type": "timestamps",
        "valid": valid,
        "total_invalid_format": total_invalid_format,
        "total_invalid_with_time": total_invalid_with_time,
    }


def phase_b_roadmap_payload(
    *,
    valid: bool,
    warnings_count: int = 0,
    missing_entries_count: int = 0,
    invalid_references_count: int = 0,
) -> dict[str, object]:
    return {
        "status": "success",
        "check_type": "roadmap_sync",
        "valid": valid,
        "summary": {
            "missing_entries_count": missing_entries_count,
            "invalid_references_count": invalid_references_count,
            "completed_entries_count": 0,
            "warnings_count": warnings_count,
        },
    }


async def run_phase_b_with_validate_mocks(
    timestamps: dict[str, object],
    roadmap: dict[str, object],
) -> ModelDict:
    with patch(
        "cortex.tools.execution.pre_commit_docs_memory_helpers.validate_from_parsed",
        new_callable=AsyncMock,
    ) as mock_validate:
        mock_validate.side_effect = [json.dumps(timestamps), json.dumps(roadmap)]
        return await execute_pre_commit_checks(phase="B")


def make_pre_commit_result(
    status: str,
    language: str = "python",
    tests_success: bool = True,
    error_payload: bool = False,
) -> ModelDict:
    """Helper to build minimal execute_pre_commit_checks-like result."""
    base: ModelDict = {
        "status": status,
        "language": language,
        "results": {
            "tests": {
                "check_type": "tests",
                "success": tests_success,
                "output": "ok" if tests_success else "tests failed",
                "errors": [] if tests_success else ["failure"],
                "warnings": [],
            },
        },
        "total_errors": 0 if tests_success and status == "success" else 1,
        "total_warnings": 0,
        "files_modified": [],
    }
    if error_payload:
        base["error"] = "tool error"
        base["error_type"] = "RuntimeError"
    return base


def detached_phase_a_mock_payload(
    exec_payload: ModelDict,
    markdown_json: str | None,
) -> ModelDict:
    """Shape ``run_detached_phase_a_checks`` return value like a polled Phase A result."""
    if markdown_json is None:
        return dict(exec_payload)
    try:
        parsed: object = json.loads(markdown_json)
    except json.JSONDecodeError:
        return dict(exec_payload)
    if not isinstance(parsed, dict):
        return dict(exec_payload)
    nested = cast(dict[str, JsonValue], parsed)
    merged = dict(exec_payload)
    merged["markdown_result"] = nested
    return merged


def make_multi_check_exec_result() -> ModelDict:
    """Minimal execute payload with several checks for summary tests."""
    return {
        "status": "success",
        "language": "python",
        "results": {
            "format": {
                "success": True,
                "errors": [],
                "warnings": ["trailing ws"],
                "output": "formatted",
            },
            "quality": {
                "success": True,
                "errors": [],
                "warnings": [],
                "output": "ok",
            },
            "tests": {
                "success": True,
                "errors": [],
                "warnings": [],
                "output": "12 passed",
            },
        },
    }


def make_markdown_result(
    files_with_errors: int = 0,
    error_message: str | None = None,
    *,
    tool_error: bool = False,
) -> str:
    """Helper to build minimal markdown lint result JSON string.

    ``tool_error=True`` sets status to ``"error"`` to simulate CLI-level
    failures.  Otherwise status is always ``"success"`` (even when
    ``files_with_errors > 0``), matching markdown lint result shape
    where lint findings do not trigger a tool error.
    """
    status = "error" if tool_error else "success"
    return json.dumps(
        {
            "status": status,
            "files_processed": 1,
            "files_fixed": 0,
            "files_unchanged": 1,
            "files_with_errors": files_with_errors,
            "results": [],
            "error_message": error_message,
        }
    )


def make_phase_b_valid_payloads() -> tuple[dict[str, object], dict[str, object]]:
    """Return baseline-success payloads for timestamps and roadmap_sync checks."""
    timestamps_payload: dict[str, object] = {
        "status": "success",
        "check_type": "timestamps",
        "valid": True,
        "total_invalid_format": 0,
        "total_invalid_with_time": 0,
    }
    roadmap_payload: dict[str, object] = {
        "status": "success",
        "check_type": "roadmap_sync",
        "valid": True,
        "summary": {
            "missing_entries_count": 0,
            "invalid_references_count": 0,
            "completed_entries_count": 0,
            "warnings_count": 0,
        },
    }
    return timestamps_payload, roadmap_payload


async def run_phase_b_for_partial_without_pending(tmp_path: Path) -> ModelDict:
    """Execute Phase B with synthetic PARTIAL progress and no roadmap PENDING."""
    mb = tmp_path / ".cortex" / "memory-bank"
    mb.mkdir(parents=True)
    _ = (mb / "progress.md").write_text(
        "- **Orphan** - PARTIAL. Needs roadmap.\n",
        encoding="utf-8",
    )
    _ = (mb / "roadmap.md").write_text(
        "# Roadmap\n\n## Future\n\n(no pending bullets)\n",
        encoding="utf-8",
    )
    timestamps_payload, roadmap_payload = make_phase_b_valid_payloads()
    with (
        patch(
            "cortex.tools.execution.pre_commit_docs_memory_helpers.validate_from_parsed",
            new_callable=AsyncMock,
        ) as mock_validate,
        patch(
            "cortex.tools.execution.pre_commit_docs_memory_helpers.resolve_project_root_async",
            new_callable=AsyncMock,
        ) as mock_root,
    ):
        mock_root.return_value = tmp_path
        mock_validate.side_effect = [
            json.dumps(timestamps_payload),
            json.dumps(roadmap_payload),
        ]
        return await execute_pre_commit_checks(phase="B")
