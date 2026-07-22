"""Pipeline and phase token validation for pipeline_handoff."""

from __future__ import annotations

import json
import re

from cortex.core.models import OperationStatus

_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Allowlisted names only — derived from Synapse prompts and orchestrators.
_VALID_PIPELINES: frozenset[str] = frozenset(
    {"commit", "implement", "fix", "review", "analyze", "default"}
)
_VALID_PHASES: frozenset[str] = frozenset(
    {
        "preflight",
        "checks",
        "docs",
        "validate",
        "final-gate",
        "select",
        "code",
        "review",
        "finalize",
        "verify",
        "fix",
        "coverage",
        "quality",
        "tests",
        "gate_feedback",
        "gate_iterations",
    }
)


def validate_pipeline(pipeline: str) -> str | None:
    """Validate pipeline token shape and allowlist before any path use."""

    if not pipeline or not _SAFE_TOKEN_RE.fullmatch(pipeline):
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": "Invalid pipeline token. Allowed characters: A-Za-z0-9_-",
            },
            indent=2,
        )
    if pipeline not in _VALID_PIPELINES:
        allowed = ", ".join(sorted(_VALID_PIPELINES))
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": (f"Unknown pipeline '{pipeline}'. Allowed values: {allowed}."),
            },
            indent=2,
        )
    return None


def validate_phase(phase: str) -> str | None:
    """Validate phase token shape and allowlist before any path use."""

    if not phase or not _SAFE_TOKEN_RE.fullmatch(phase):
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": "Invalid phase token. Allowed characters: A-Za-z0-9_-",
            },
            indent=2,
        )
    if phase not in _VALID_PHASES:
        allowed = ", ".join(sorted(_VALID_PHASES))
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": f"Unknown phase '{phase}'. Allowed values: {allowed}.",
            },
            indent=2,
        )
    return None
