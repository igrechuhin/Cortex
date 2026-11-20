"""Process-bound challenge for the opt-in final-only detached Swift worker."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_ENV = "CORTEX_FINAL_GATE_CHALLENGE"
_WORKER: ContextVar[bool] = ContextVar("staged_gate_worker", default=False)
_CONTEXT: ContextVar[str | None] = ContextVar("staged_gate_challenge", default=None)


@contextmanager
def final_worker_challenge(
    value: str | None, *, worker: bool = False
) -> Iterator[None]:
    """Set the server-issued challenge for one detached request or worker."""
    token = _CONTEXT.set(value)
    worker_token = _WORKER.set(worker)
    try:
        yield
    finally:
        _WORKER.reset(worker_token)
        _CONTEXT.reset(token)


def receive_worker_challenge() -> str | None:
    """Consume the secret before launching checker or project subprocesses."""
    return os.environ.pop(_ENV, None)


def worker_challenge_env() -> dict[str, str]:
    """Pass the secret privately only to the outer worker."""
    value = _CONTEXT.get()
    return {_ENV: value} if value is not None else {}


def challenge_id() -> str | None:
    """Select a separate worker result identity per final test attempt."""
    value = _CONTEXT.get()
    return hashlib.sha256(value.encode()).hexdigest() if value else None


def authenticate_worker_payload(
    path: Path, payload: dict[str, object], challenge: str
) -> str:
    """Bind the immutable worker payload to its exact job and challenge."""
    stable = {k: v for k, v in payload.items() if k != "quality_gate_pending"}
    raw = json.dumps([path.name, stable], sort_keys=True, separators=(",", ":"))
    return hmac.digest(challenge.encode(), raw.encode(), "sha256").hex()


def attach_worker_proof(path: Path, payload: dict[str, object]) -> None:
    """Sign only terminal results produced by the real worker."""
    challenge = _CONTEXT.get()
    if _WORKER.get() and challenge is not None and payload.get("status") == "completed":
        payload["final_worker_proof"] = authenticate_worker_payload(
            path, payload, challenge
        )


def verify_worker_proof(path: Path, payload: dict[str, object], challenge: str) -> bool:
    """Reject missing, modified and stale worker results."""
    proof = payload.get("final_worker_proof")
    if not isinstance(proof, str) or not proof.isascii():
        return False
    unsigned = {k: v for k, v in payload.items() if k != "final_worker_proof"}
    expected = authenticate_worker_payload(path, unsigned, challenge)
    return hmac.compare_digest(expected, proof)
