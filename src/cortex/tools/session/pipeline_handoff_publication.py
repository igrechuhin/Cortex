"""Exact-request publication evidence using the existing handoff files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

from . import pipeline_handoff_io as io
from .phase_result_receipt import PhaseResultReceipt
from .phase_result_status import PhaseResultStatus
from .phase_result_verification import PhaseResultVerification
from .pipeline_handoff_lock import PipelineClaimLockTimeout, pipeline_claim_lock
from .pipeline_handoff_session import passive_session_id

RECEIPT_KEY = "_publication"


def publication_digest(value: object) -> str:
    """Hash canonical JSON values, preserving types and array order."""
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def publication_receipt(
    pdir: Path,
    pipeline: str,
    phase: str,
    incoming: dict[str, object],
    payload: dict[str, object],
) -> PhaseResultReceipt:
    """Bind request (before defaults/config separation) and generated payload."""
    return PhaseResultReceipt(
        run_id=pdir.parent.name,
        pipeline=pipeline,
        phase=phase,
        request_digest=publication_digest(incoming),
        result_digest=publication_digest(payload),
    )


def _read_object(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path.name}")
    return cast(dict[str, object], value)


def _read_history(pdir: Path, phase: str) -> list[io.EventLogEntry]:
    path = io.event_log_path(pdir)
    if not path.exists():
        return []
    entries = [
        io.EventLogEntry.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [entry for entry in entries if entry.phase == phase]


def _matching_config(
    state: dict[str, object],
    incoming: dict[str, object],
    *,
    allow_new: bool = False,
) -> bool:
    expected = {key: incoming[key] for key in io.PHASE_CONFIG_KEYS if key in incoming}
    config = state.get("config", {})
    if not isinstance(config, dict):
        raise ValueError("Malformed separated configuration")
    values = cast(dict[str, object], config)
    return all(
        (allow_new and key not in values)
        or (
            key in values
            and publication_digest(values[key]) == publication_digest(value)
        )
        for key, value in expected.items()
    )


def _verify_evidence(
    pdir: Path,
    pipeline: str,
    phase: str,
    incoming: dict[str, object],
) -> PhaseResultVerification:
    result = _read_object(io.result_path(pdir, phase))
    state = _read_object(io.state_path(pdir))
    history = _read_history(pdir, phase)
    phases = state.get("phases", {})
    if not isinstance(phases, dict):
        raise ValueError("Malformed manifest phases")
    projected = cast(dict[str, object], phases).get(phase)
    if not io.result_path(pdir, phase).exists() and projected is None and not history:
        return _verify_missing(pdir, pipeline, state, incoming)
    if not result or projected is None or not history:
        return PhaseResultVerification(
            status=PhaseResultStatus.UNCERTAIN, reason="Partial publication evidence"
        )
    return _verify_complete(pdir, pipeline, phase, incoming, result, state, history[-1])


def _verdict(status: PhaseResultStatus, reason: str) -> PhaseResultVerification:
    return PhaseResultVerification(status=status, reason=reason)


def _verify_missing(
    pdir: Path,
    pipeline: str,
    state: dict[str, object],
    incoming: dict[str, object],
) -> PhaseResultVerification:
    if io.state_path(pdir).exists():
        if (
            state.get("session_id") != pdir.parent.name
            or state.get("pipeline") != pipeline
        ):
            return _verdict(
                PhaseResultStatus.CONFLICTING, "Manifest run identity differs"
            )
        # AI: Initial publication may add config, but cannot replace existing values.
        if not _matching_config(state, incoming, allow_new=True):
            return _verdict(
                PhaseResultStatus.CONFLICTING, "Separated configuration differs"
            )
    return _verdict(PhaseResultStatus.MISSING, "No phase publication evidence")


def _verify_complete(
    pdir: Path,
    pipeline: str,
    phase: str,
    incoming: dict[str, object],
    result: dict[str, object],
    state: dict[str, object],
    latest: io.EventLogEntry,
) -> PhaseResultVerification:
    receipt = PhaseResultReceipt.model_validate(result.get(RECEIPT_KEY))
    payload = {key: value for key, value in result.items() if key != RECEIPT_KEY}
    if receipt != publication_receipt(pdir, pipeline, phase, incoming, payload):
        return _verdict(
            PhaseResultStatus.CONFLICTING, "Request or result identity differs"
        )
    # BELIEF: _verify_evidence validated this phase's manifest projection.
    phases = cast(dict[str, object], state["phases"])
    if not _matching_history(result, phases[phase], latest, incoming, receipt):
        return _verdict(
            PhaseResultStatus.UNCERTAIN, "Result, manifest and history disagree"
        )
    return _verify_manifest(state, receipt, incoming)


def _matching_history(
    result: dict[str, object],
    projected: object,
    latest: io.EventLogEntry,
    incoming: dict[str, object],
    receipt: PhaseResultReceipt,
) -> bool:
    return (
        publication_digest(projected) == publication_digest(result)
        and latest.receipt == receipt
        and latest.operation == "write"
        and latest.data_keys == sorted(incoming)
        and latest.status is not None
        and latest.status.value == result.get("phase_status")
    )


def _verify_manifest(
    state: dict[str, object],
    receipt: PhaseResultReceipt,
    incoming: dict[str, object],
) -> PhaseResultVerification:
    if (
        state.get("session_id") != receipt.run_id
        or state.get("pipeline") != receipt.pipeline
    ):
        return _verdict(PhaseResultStatus.CONFLICTING, "Manifest run identity differs")
    if not _matching_config(state, incoming):
        return _verdict(
            PhaseResultStatus.CONFLICTING, "Separated configuration differs"
        )
    return PhaseResultVerification(
        status=PhaseResultStatus.EXACT,
        reason="Exact publication persisted",
        receipt=receipt,
    )


def validate_publication_request(incoming: dict[str, object]) -> None:
    """Reject ambiguous identity values before touching publication evidence."""
    if RECEIPT_KEY in incoming:
        raise ValueError(f"{RECEIPT_KEY} is reserved publication metadata")
    _ = publication_digest(incoming)


def verify_publication(
    pdir: Path,
    pipeline: str,
    phase: str,
    incoming: dict[str, object],
) -> PhaseResultVerification:
    """Classify all persisted evidence; the caller holds the publication lock."""
    try:
        validate_publication_request(incoming)
        return _verify_evidence(pdir, pipeline, phase, incoming)
    except (OSError, ValueError) as exc:
        return PhaseResultVerification(
            status=PhaseResultStatus.UNCERTAIN,
            reason=f"Unreadable publication evidence: {exc}",
        )


def publication_directory(root: Path, pipeline: str) -> Path | None:
    """Resolve only a latched current run; never adopt an unbound candidate."""
    run_id = passive_session_id(root)
    if not run_id:
        return None
    return get_cortex_path(root, CortexResourceType.SESSION) / run_id / pipeline


def op_verify_result(root: Path, pipeline: str, phase: str, data: str | None) -> str:
    """Passively verify this connection's publication, without claiming a run."""
    pdir = publication_directory(root, pipeline)
    if pdir is None:
        return PhaseResultVerification(
            status=PhaseResultStatus.UNCERTAIN, reason="No current run identity"
        ).model_dump_json()
    incoming = io.parse_result_data(data)
    try:
        if not pdir.exists():
            return verify_publication(pdir, pipeline, phase, incoming).model_dump_json()
        with pipeline_claim_lock(pdir.with_name(f".{pdir.name}-publication")):
            return verify_publication(pdir, pipeline, phase, incoming).model_dump_json()
    except (OSError, PipelineClaimLockTimeout) as exc:
        return PhaseResultVerification(
            status=PhaseResultStatus.UNCERTAIN, reason=str(exc)
        ).model_dump_json()
