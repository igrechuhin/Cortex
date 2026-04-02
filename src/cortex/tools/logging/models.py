"""Structured log events for agent-oriented MCP tool observability."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LogLevel(StrEnum):
    """Severity for agent-facing log lines."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class LogEvent(BaseModel):
    """One structured log line (JSON on stderr) for agent traceability."""

    event: str = Field(..., description="Short event id, e.g. quality_gate.failed")
    level: LogLevel
    component: str = Field(..., description="Tool or module path")
    trace_id: str | None = None
    requirement_id: str | None = None
    commit_hash: str | None = None
    message: str
    details: dict[str, str | int | bool] | None = None
