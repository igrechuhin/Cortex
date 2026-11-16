"""Operator approval is outside every MCP mutation surface."""

import hashlib
import os
from pathlib import Path

from pydantic import ValidationError

from cortex.core.project_access import (
    HASH_ENV,
    POLICY_ENV,
    AccessReason,
    configuration_guidance,
    configuration_reason,
)
from cortex.tools.files.project_access.models import ApprovedAccess, Policy
from cortex.tools.files.project_access.paths import read_bytes, relative_parts


class PolicyAccessError(ValueError):
    """Safe typed refusal; raw policy validation details stay outside responses."""

    def __init__(self, reason: AccessReason, message: str) -> None:
        self.reason = reason
        super().__init__(message)


def load_access(root: Path) -> ApprovedAccess:
    """No defaults, project discovery or request argument can grant access."""
    raw_path, digest = os.environ.get(POLICY_ENV, ""), os.environ.get(HASH_ENV, "")
    reason = configuration_reason(raw_path, digest)
    if reason != AccessReason.VALIDATION_REQUIRED:
        raise PolicyAccessError(
            reason, "Project access disabled: " + configuration_guidance(reason)
        )
    path = _validated_policy_path(root, raw_path)
    policy = _validated_policy(path, digest)
    _validate_policy_scope(root, policy)
    return ApprovedAccess(
        root=root.resolve(), policy=policy, policy_path=path, policy_hash=digest
    )


def _validated_policy_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    try:
        unsafe = (
            not path.is_absolute()
            or path.resolve() != path
            or path.is_relative_to(root.resolve())
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise PolicyAccessError(
            AccessReason.POLICY_PATH_UNSAFE, "Approval policy path is unsafe"
        ) from exc
    if unsafe:
        raise PolicyAccessError(
            AccessReason.POLICY_PATH_UNSAFE,
            "Approval policy must be an absolute path without symlinks outside the project",
        )
    return path


def _validated_policy(path: Path, digest: str) -> Policy:
    try:
        content = read_policy(path)
    except (OSError, ValueError) as exc:
        raise PolicyAccessError(
            AccessReason.POLICY_UNAVAILABLE, "Approval policy is unavailable or unsafe"
        ) from exc
    if hashlib.sha256(content).hexdigest() != digest:
        raise PolicyAccessError(
            AccessReason.POLICY_HASH_MISMATCH, "Approval policy hash mismatch"
        )
    try:
        return Policy.model_validate_json(content)
    except ValidationError as exc:
        raise PolicyAccessError(
            AccessReason.POLICY_SCHEMA_INVALID, "Invalid project-access policy schema"
        ) from exc


def _validate_policy_scope(root: Path, policy: Policy) -> None:
    if not policy.enabled or policy.project_root != str(root.resolve()):
        raise PolicyAccessError(
            AccessReason.POLICY_DISABLED_OR_WRONG_PROJECT,
            "Project access disabled or policy belongs to another project",
        )
    try:
        for name in policy.files + [policy.output_directory]:
            _ = relative_parts(name)
    except ValueError as exc:
        raise PolicyAccessError(
            AccessReason.POLICY_PATH_UNSAFE,
            "Approval policy contains an unsafe project path",
        ) from exc


def read_policy(path: Path) -> bytes:
    """Read only a small regular operator policy, without following aliases."""
    import stat

    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Approval policy must be a regular file")
        content = stream.read(65537)
    if len(content) > 65536:
        raise ValueError("Approval policy exceeds size limit")
    return content


def approved_script(access: ApprovedAccess, name: str) -> bytes:
    """Pin reviewed code so a later source edit cannot change approved execution."""
    job = access.policy.jobs[name]
    content = read_bytes(access.root, job.script, 1048576)
    if hashlib.sha256(content).hexdigest() != job.sha256:
        raise ValueError("Approved script hash mismatch; operator review required")
    interpreter = Path(job.interpreter)
    if not interpreter.is_absolute() or not interpreter.is_file():
        raise ValueError("Approved interpreter must be an existing absolute file")
    return content
