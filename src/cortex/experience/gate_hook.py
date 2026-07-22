"""Quality-gate result -> experience-store fitness attachment (best-effort)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from cortex.core.models import ModelDict
from cortex.experience.recorder import record_gate_fitness

_SUMMARY_KEYS: tuple[str, ...] = (
    "preflight_passed",
    "summary",
    "total_errors",
    "total_warnings",
)


def gate_summary(result: ModelDict) -> str:
    """Compact JSON score summary (pass/fail + error counts) for the artifact."""
    return json.dumps({key: result.get(key) for key in _SUMMARY_KEYS if key in result})


async def record_gate_result(
    root: Path, result: ModelDict, pipeline: str = "commit"
) -> str | None:
    """Attach the gate outcome as node fitness. Never raises past the recorder."""
    # AI: imported lazily to keep experience/ free of session-tool import cycles.
    from cortex.tools.session.pipeline_handoff_io import get_session_id

    passed = result.get("preflight_passed") is True
    return await asyncio.to_thread(
        record_gate_fitness,
        root,
        get_session_id(root),
        pipeline,
        passed,
        gate_summary(result),
    )
