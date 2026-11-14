"""Operator approval is outside every MCP mutation surface."""

import hashlib
import os
import re
from pathlib import Path

from cortex.tools.files.project_access.models import ApprovedAccess, Policy
from cortex.tools.files.project_access.paths import read_bytes, relative_parts

POLICY_ENV = "CORTEX_PROJECT_ACCESS_POLICY"
HASH_ENV = "CORTEX_PROJECT_ACCESS_POLICY_SHA256"


def load_access(root: Path) -> ApprovedAccess:
    """No defaults, project discovery or request argument can grant access."""
    raw_path, digest = os.environ.get(POLICY_ENV, ""), os.environ.get(HASH_ENV, "")
    if not raw_path or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError(
            "Project access disabled: operator-approved policy and hash required"
        )
    path = Path(raw_path)
    if (
        not path.is_absolute()
        or path.resolve() != path
        or path.is_relative_to(root.resolve())
    ):
        raise ValueError(
            "Approval policy must be an absolute path without symlinks outside the project"
        )
    content = read_policy(path)
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("Approval policy hash mismatch")
    policy = Policy.model_validate_json(content)
    if not policy.enabled or policy.project_root != str(root.resolve()):
        raise ValueError("Project access disabled or policy belongs to another project")
    for name in policy.files + [policy.output_directory]:
        _ = relative_parts(name)
    return ApprovedAccess(
        root=root.resolve(), policy=policy, policy_path=path, policy_hash=digest
    )


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
