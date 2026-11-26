"""Typed state for recoverable multi-file plan completion."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

from cortex.core.pydantic_extra import EXTRA_FORBID


class CompletionPhase(str, Enum):
    """Persisted completion transaction phase."""

    PREPARED = "prepared"
    PLAN_WRITTEN = "plan_written"
    ROADMAP_WRITTEN = "roadmap_written"
    ACTIVE_WRITTEN = "active_written"
    PROGRESS_WRITTEN = "progress_written"
    ARCHIVED = "archived"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    RECOVERY_REQUIRED = "recovery_required"


class CompletionFileKey(str, Enum):
    """Files owned by one completion transaction."""

    PLAN = "plan"
    ROADMAP = "roadmap"
    ACTIVE_CONTEXT = "active_context"
    PROGRESS = "progress"


class CompletionRequest(BaseModel):
    """Normalized caller request used for retry identity."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    plan_title: str
    summary: str
    completion_date: str
    progress_entry: str | None
    plan_file_name: str | None


class CancellationInput(BaseModel):
    """Explicit operator intent and raw-byte guard supplied to archive_cancelled."""

    model_config = ConfigDict(extra=EXTRA_FORBID, strict=True)

    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=1000)
    dry_run: StrictBool

    @field_validator("reason")
    @classmethod
    def validated_reason(cls, value: str) -> str:
        """Keep the request reason meaningful and suitable for a receipt."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("Cancellation reason must be nonempty")
        return stripped


class CancellationRequest(BaseModel):
    """Persisted identity of an approved cancellation, independent of preview."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    plan_file_name: str
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=1000)


PlanArchiveRequest = CompletionRequest | CancellationRequest


class CompletionFileRecord(BaseModel):
    """Hashes and payload references for one transaction-owned file."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    key: CompletionFileKey
    relative_path: str
    before_exists: bool
    before_hash: str
    after_hash: str
    before_payload: str
    after_payload: str


class PreparedCompletionFile(BaseModel):
    """Fully read before/after content held in memory before persistence."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    key: CompletionFileKey
    path: Path
    before: str
    after: str


class CompletionOperationRecord(BaseModel):
    """Bounded persisted record for retry and restart recovery."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    schema_version: int = Field(default=1, ge=1, le=1)
    operation_id: str
    request_fingerprint: str
    request: PlanArchiveRequest
    phase: CompletionPhase
    files: list[CompletionFileRecord] = Field(max_length=4)
    archive_source: str | None = None
    archive_destination: str | None = None
    roadmap_line_removed: int | None = Field(default=None, ge=1)
    active_context_line_inserted: int | None = Field(default=None, ge=1)
    progress_line_inserted: int | None = Field(default=None, ge=1)
    created_at: str
    updated_at: str
    error: str | None = None

    @model_validator(mode="after")
    def validate_archive_shape(self) -> "CompletionOperationRecord":
        """Reject malformed/tampered archive records before filesystem use."""
        keys = [item.key for item in self.files]
        if len(keys) != len(set(keys)):
            raise ValueError("Completion operation contains duplicate file keys")
        has_source = self.archive_source is not None
        has_destination = self.archive_destination is not None
        if has_source != has_destination:
            raise ValueError("Completion archive paths must be present together")
        if has_source and CompletionFileKey.PLAN not in keys:
            raise ValueError("Completion archive record is missing plan state")
        if isinstance(self.request, CancellationRequest) and not has_source:
            raise ValueError("Cancellation record is missing archive paths")
        return self
