"""Strict policy and request types for approved project capabilities."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Action(str, Enum):
    """Closed dispatch vocabulary; no execution inferred from file names."""

    DISCOVER = "discover"
    READ = "read"
    QUERY = "query"
    START = "start"
    STATUS = "status"
    READ_OUTPUT = "read_output"


class Dataset(BaseModel):
    """Approved base table and exported columns of a SQLite snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True)
    path: str
    table: str
    columns: list[str] = Field(min_length=1, max_length=32)
    max_bytes: int = Field(default=134217728, ge=4096, le=536870912)


class Job(BaseModel):
    """Reviewed existing script and finite approved command arguments."""

    model_config = ConfigDict(extra="forbid", strict=True)
    interpreter: str
    script: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    arguments: list[str] = Field(max_length=32)
    parameters: dict[str, list[str]] = Field(default_factory=dict, max_length=8)
    timeout: int = Field(default=60, ge=1, le=7200)


class Policy(BaseModel):
    """Operator-approved policy, pinned outside the MCP request channel."""

    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = False
    project_root: str
    files: list[str] = Field(default_factory=list, max_length=64)
    datasets: dict[str, Dataset] = Field(default_factory=dict, max_length=16)
    jobs: dict[str, Job] = Field(default_factory=dict, max_length=16)
    output_directory: str


class Request(BaseModel):
    """Bounded, structured client input; raw SQL and argv have no fields."""

    model_config = ConfigDict(extra="forbid", strict=True)
    action: Action = Action.DISCOVER
    path: str = Field(default="", max_length=512)
    dataset: str = Field(default="", max_length=64)
    filters: dict[str, str | int | float | None] = Field(
        default_factory=dict, max_length=8
    )
    limit: int = Field(default=50, ge=1, le=200, strict=True)
    offset: int = Field(default=0, ge=0, le=16777216, strict=True)
    length: int = Field(default=8192, ge=1, le=8192, strict=True)
    job: str = Field(default="", max_length=64)
    parameters: dict[str, str] = Field(default_factory=dict, max_length=8)


class ApprovedAccess(BaseModel):
    """Bound policy and root resolved by Cortex, never by client arguments."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    root: Path
    policy: Policy
    policy_path: Path
    policy_hash: str


class Outcome(str, Enum):
    """No arbitrary child output can enter a status response."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REFUSED = "refused_or_failed"
    LAUNCH_FAILED = "launch_failed"


class Terminal(BaseModel):
    """Closed durable status publication."""

    model_config = ConfigDict(extra="forbid")
    outcome: Outcome
    exit_code: int | None = None
