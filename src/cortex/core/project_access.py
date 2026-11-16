"""Environment-only orientation; never open a policy or enumerate its grants."""

import os
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict


class AccessState(str, Enum):
    """Configuration is observable; authorization still requires validation."""

    DISABLED = "disabled"
    CONFIGURED_UNVERIFIED = "configured_unverified"


class AccessReason(str, Enum):
    """Closed public reasons contain no operator policy information."""

    POLICY_PATH_MISSING = "policy_path_missing"
    POLICY_SHA_MISSING = "policy_sha_missing"
    POLICY_SHA_INVALID = "policy_sha_invalid"
    VALIDATION_REQUIRED = "validation_required"
    POLICY_PATH_UNSAFE = "policy_path_unsafe"
    POLICY_UNAVAILABLE = "policy_unavailable"
    POLICY_HASH_MISMATCH = "policy_hash_mismatch"
    POLICY_SCHEMA_INVALID = "policy_schema_invalid"
    POLICY_DISABLED_OR_WRONG_PROJECT = "policy_disabled_or_wrong_project"


class ProtectedOperation(str, Enum):
    """Bootstrap vocabulary is independent of tool registration and request types."""

    DISCOVER = "discover"
    READ = "read"
    QUERY = "query"
    START = "start"
    STATUS = "status"
    READ_OUTPUT = "read_output"


class AccessSummary(BaseModel):
    """Safe bootstrap guidance, never a listing of approved capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    state: AccessState
    reason: AccessReason
    protected_operations: tuple[ProtectedOperation, ...] = tuple(ProtectedOperation)
    planning_requires_policy: bool = False
    guidance: str


POLICY_ENV = "CORTEX_PROJECT_ACCESS_POLICY"
HASH_ENV = "CORTEX_PROJECT_ACCESS_POLICY_SHA256"

_GUIDANCE = {
    AccessReason.POLICY_PATH_MISSING: "An operator must configure an approved policy path before protected project access.",
    AccessReason.POLICY_SHA_MISSING: "An operator must configure the reviewed policy SHA-256 before protected project access.",
    AccessReason.POLICY_SHA_INVALID: "An operator must correct the policy SHA-256 format before protected project access.",
    AccessReason.VALIDATION_REQUIRED: "Policy configuration is present but unverified; each protected operation validates it.",
}


def access_summary() -> AccessSummary:
    """Return fixed configuration guidance without reading protected resources."""
    raw_path = os.environ.get(POLICY_ENV, "")
    digest = os.environ.get(HASH_ENV, "")
    reason = configuration_reason(raw_path, digest)
    return AccessSummary(
        state=(
            AccessState.CONFIGURED_UNVERIFIED
            if reason == AccessReason.VALIDATION_REQUIRED
            else AccessState.DISABLED
        ),
        reason=reason,
        guidance=configuration_guidance(reason),
    )


def configuration_reason(raw_path: str, digest: str) -> AccessReason:
    """Validate a single configuration snapshot without filesystem access."""
    if not raw_path:
        return AccessReason.POLICY_PATH_MISSING
    if not digest:
        return AccessReason.POLICY_SHA_MISSING
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        return AccessReason.POLICY_SHA_INVALID
    return AccessReason.VALIDATION_REQUIRED


def configuration_guidance(reason: AccessReason) -> str:
    """Only fixed public text can reach bootstrap or configuration denials."""
    return (
        _GUIDANCE[reason]
        + " Planning and unrelated workflows do not require this policy."
    )
