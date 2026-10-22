"""Explicit outcomes for publication verification, never phase execution."""

from pydantic import BaseModel

from .phase_result_receipt import PhaseResultReceipt
from .phase_result_status import PhaseResultStatus


class PhaseResultVerification(BaseModel):
    """Missing is replayable; uncertain/conflicting evidence must not be changed."""

    status: PhaseResultStatus
    reason: str
    receipt: PhaseResultReceipt | None = None
