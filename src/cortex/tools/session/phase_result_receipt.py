"""Identity and integrity evidence for one phase-result publication."""

from pydantic import BaseModel, ConfigDict, Field


class PhaseResultReceipt(BaseModel):
    """Bind the exact caller request and persisted result to the current run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(default=1, ge=1, le=1)
    run_id: str = Field(min_length=1)
    pipeline: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
