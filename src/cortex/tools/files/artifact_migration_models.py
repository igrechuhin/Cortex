"""Byte-preserving state for the narrowly scoped artifact relocation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID


class MigrationPhase(StrEnum):
    PREPARED = "prepared"
    FILES_COMMITTED = "files_committed"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    RECOVERY_REQUIRED = "recovery_required"


class Relocation(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)

    source: str
    destination: str
    before_hash: str
    after_hash: str


class MigrationEdit(BaseModel):
    model_config = ConfigDict(
        extra=EXTRA_FORBID, ser_json_bytes="base64", val_json_bytes="base64"
    )

    path: str
    before: bytes | None
    after: bytes | None


class MigrationPlan(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)

    digest: str
    project_root: str
    snapshot: dict[str, str]
    relocations: list[Relocation]
    edits: list[MigrationEdit]
    remove_directories: list[str]


class MigrationRecord(BaseModel):
    model_config = ConfigDict(
        extra=EXTRA_FORBID, ser_json_bytes="base64", val_json_bytes="base64"
    )

    schema_version: int = Field(default=1, ge=1, le=1)
    phase: MigrationPhase
    plan: MigrationPlan
    created_at: str
    error: str | None = None
    created_directories: list[str] = Field(default_factory=list)
    writes_started: bool = False
