"""Validated native host lifecycle input; no transcript content is ingested."""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PluginHookEvent(BaseModel):
    """Literal values mirror the external hosts' wire protocol, not internal state."""

    model_config = ConfigDict(extra="forbid", strict=True)

    host: Literal["claude", "codex"]
    event: Literal["SessionStart", "PreCompact"]
    cwd: str = Field(min_length=1, max_length=4096)
    session_id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.:-]+$")
    source: Literal["startup", "resume"] | None = None
    trigger: Literal["manual", "auto"] | None = None
    transcript_path: str | None = Field(default=None, max_length=4096)
    turn_id: str | None = Field(
        default=None, min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.:-]+$"
    )

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if not Path(self.cwd).is_absolute():
            raise ValueError("Hook cwd must be absolute")
        if self.event == "SessionStart" and self.source is None:
            raise ValueError("SessionStart requires startup/resume source")
        if self.event == "PreCompact" and self.trigger is None:
            raise ValueError("PreCompact requires manual/auto trigger")
        return self
