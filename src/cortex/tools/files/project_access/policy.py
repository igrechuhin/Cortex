"""Operator approval is outside every MCP mutation surface."""

import hashlib
import os
import re
from pathlib import Path

from cortex.tools.files.project_access.models import ApprovedAccess, DataRoot, Policy
from cortex.tools.files.project_access.paths import (
    canonical_directory,
    directory,
    physically_contains,
    read_bytes,
    relative_parts,
)

POLICY_ENV = "CORTEX_PROJECT_ACCESS_POLICY"
HASH_ENV = "CORTEX_PROJECT_ACCESS_POLICY_SHA256"


def load_access(root: Path) -> ApprovedAccess:
    """No defaults, project discovery or request argument can grant access."""
    root = canonical_directory(str(root))
    raw_path, digest = os.environ.get(POLICY_ENV, ""), os.environ.get(HASH_ENV, "")
    if not raw_path or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError(
            "Project access disabled: operator-approved policy and hash required"
        )
    path = Path(raw_path)
    if (
        not path.is_absolute()
        or path.resolve() != path
        or physically_contains(root, path.parent)
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
    validate_project_paths(policy)
    data_root = validate_data_root(root, path, policy.data_root)
    return ApprovedAccess(
        root=root,
        policy=policy,
        policy_path=path,
        policy_hash=digest,
        data_root=data_root,
    )


def validate_project_paths(policy: Policy) -> None:
    """Validate legacy paths without changing the original grant semantics."""
    for name in (
        policy.files
        + [d.path for d in policy.datasets.values()]
        + [policy.output_directory]
    ):
        _ = relative_parts(name)


def validate_data_root(
    project: Path, policy_path: Path, grant: DataRoot | None
) -> Path | None:
    """A separate approval cannot widen the project or expose writable inputs."""
    if grant is None or not grant.enabled:
        return None
    root = canonical_directory(grant.root)
    if (
        physically_contains(root, project)
        or physically_contains(project, root)
        or physically_contains(root, policy_path.parent)
    ):
        raise ValueError("Data root must be disjoint from project and approval policy")
    validate_data_paths(root, grant)
    return root


def validate_data_paths(root: Path, grant: DataRoot) -> None:
    """Separate exact reads from write bases, including physical case aliases."""
    reads = [
        Path(*relative_parts(p))
        for p in grant.files + [d.path for d in grant.datasets.values()]
    ]
    outputs = [Path(*relative_parts(p)) for p in grant.output_bases.values()]
    if len(set(outputs)) != len(outputs):
        raise ValueError("Output bases must be distinct")
    for output in outputs:
        if any(p.is_relative_to(output) or output.is_relative_to(p) for p in reads):
            raise ValueError("Data read and write allowlists overlap")
        if any(
            p != output and (p.is_relative_to(output) or output.is_relative_to(p))
            for p in outputs
        ):
            raise ValueError("Output bases must not overlap")
        with directory(root, output.parts):
            pass
        if any(physically_contains(root / output, (root / p).parent) for p in reads):
            raise ValueError("Data read and write allowlists physically overlap")
        if any(
            p != output and physically_contains(root / output, root / p)
            for p in outputs
        ):
            raise ValueError("Output bases physically overlap")


def read_policy(path: Path) -> bytes:
    """Read only a small regular operator policy, without following aliases."""
    import stat

    with directory(path.parent) as parent:
        fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        with os.fdopen(fd, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
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
