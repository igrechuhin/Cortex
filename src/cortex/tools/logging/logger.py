"""Emit structured LogEvent lines to stderr and format tables for tool responses."""

from __future__ import annotations

import json
import sys
from typing import TextIO

from cortex.tools.logging.models import LogEvent


def _md_cell(value: str) -> str:
    """Escape pipe characters for markdown table cells."""
    return value.replace("|", "\\|").replace("\n", " ")


def emit(event: LogEvent, stream: TextIO | None = None) -> None:
    """Write one JSON line for ``event`` to stderr (or ``stream`` for tests)."""
    out = stream if stream is not None else sys.stderr
    payload = event.model_dump(mode="json")
    line = json.dumps(payload, ensure_ascii=False)
    _ = out.write(line + "\n")
    _ = out.flush()


def format_for_agent(events: list[LogEvent]) -> str:
    """Return a markdown table summarizing ``events`` for MCP response text."""
    if not events:
        return ""
    header = "| event | level | component | message | details |"
    sep = "| --- | --- | --- | --- | --- |"
    rows: list[str] = [header, sep]
    for ev in events:
        det = (
            ""
            if ev.details is None
            else json.dumps(ev.details, ensure_ascii=False, sort_keys=True)
        )
        rows.append(
            "| "
            + " | ".join(
                [
                    _md_cell(ev.event),
                    _md_cell(str(ev.level.value)),
                    _md_cell(ev.component),
                    _md_cell(ev.message),
                    _md_cell(det),
                ]
            )
            + " |"
        )
    return "\n".join(rows)
