"""Git-verified canonical main-worktree identity for cross-worktree reads.

A linked git worktree resolves its own project root correctly, but its
``.cortex/`` tree can be missing or stale relative to canonical main. This
module maps a legitimate listed worktree to the main working tree of the
same git repository and fails closed on every uncertain mapping. It is
read-only: resolving identity never writes to either root and never switches
the process's bound project root.

Provenance semantics: ``content_sha256`` identifies the exact working-tree
bytes captured once for parsing and provenance (these may include uncommitted
approved context); ``git_revision`` is canonical-root HEAD repository
context, not a claim that the bytes were committed at that revision.
"""

from __future__ import annotations

from enum import Enum
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.execution_env import ExecutionEnvironment, LocalExecutionEnvironment
from cortex.core.models import PlanReadSource
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.pydantic_extra import EXTRA_FORBID

# Closed artifact roots whose reports are referenced by approved results.
ARTIFACT_DIR_NAMES: tuple[str, ...] = ("reviews", "analyses", "queries")


class CanonicalRelation(str, Enum):
    """How the local root relates to the canonical main worktree."""

    LOCAL_IS_CANONICAL = "local_is_canonical"
    LINKED_WORKTREE = "linked_worktree"


class CanonicalLocalState(str, Enum):
    """Freshness of the local counterpart of a canonically read file."""

    MISSING = "missing"
    IDENTICAL = "identical"
    DIVERGED = "diverged"
    AMBIGUOUS = "ambiguous"
    UNSAFE = "unsafe"
    UNREADABLE = "unreadable"


class CanonicalReadFailure(str, Enum):
    """Typed fail-closed reasons for canonical identity resolution."""

    NOT_A_GIT_CHECKOUT = "not_a_git_checkout"
    GIT_FAILURE = "git_failure"
    LOCAL_ROOT_NOT_LISTED = "local_root_not_listed"
    AMBIGUOUS_MAIN_WORKTREE = "ambiguous_main_worktree"
    AMBIGUOUS_LOCAL_WORKTREE = "ambiguous_local_worktree"
    CANONICAL_UNREADABLE = "canonical_unreadable"
    CANONICAL_NOT_CORTEX_ROOT = "canonical_not_cortex_root"
    COMMON_DIR_MISMATCH = "common_dir_mismatch"
    TRAVERSAL_ESCAPE = "traversal_escape"
    REVISION_CHANGED_DURING_READ = "revision_changed_during_read"


class CanonicalProjectError(Exception):
    """Raised when canonical identity cannot be established fail-closed."""

    def __init__(self, failure: CanonicalReadFailure, detail: str) -> None:
        super().__init__(f"{failure.value}: {detail}")
        self.failure = failure
        self.detail = detail


class CanonicalProjectIdentity(BaseModel):
    """Verified identity of the canonical main worktree for a local root."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    local_root: Path
    canonical_root: Path
    relation: CanonicalRelation
    common_git_dir: Path
    git_revision: str


class CanonicalReadProvenance(BaseModel):
    """Provenance and local freshness for one explicit canonical read.

    ``content_sha256`` is the digest of the exact captured working-tree
    bytes; ``git_revision`` is repository context only. Attached only to
    canonical read results; local reads keep their prior result shape.
    """

    model_config = ConfigDict(extra=EXTRA_FORBID)

    source: PlanReadSource
    root: Path
    relation: CanonicalRelation
    git_revision: str | None = None
    content_sha256: str | None = Field(
        default=None, description="Digest of the exact captured file bytes"
    )
    local_state: CanonicalLocalState | None = None
    local_content_sha256: str | None = None
    local_missing: list[str] = Field(default_factory=list[str])
    local_unsafe: list[str] = Field(default_factory=list[str])
    local_stale: list[str] = Field(default_factory=list[str])
    local_ambiguous: list[str] = Field(default_factory=list[str])
    local_unreadable: list[str] = Field(default_factory=list[str])


def parse_read_source(raw: str | None) -> PlanReadSource | None:
    """Map a wire ``source`` string to :class:`PlanReadSource`; None default local."""
    if raw is None or raw == "":
        return PlanReadSource.LOCAL
    try:
        return PlanReadSource(raw)
    except ValueError:
        return None


def sha256_bytes(raw: bytes) -> str:
    """Return the sha256 hex digest of exact bytes."""
    return sha256(raw).hexdigest()


def decode_captured_bytes(raw: bytes) -> str:
    """Decode captured bytes with the same newline handling as ``read_text``."""
    return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


class CapturedSource:
    """One exact-byte capture of a canonical file plus its digest."""

    def __init__(self, path: Path, raw: bytes) -> None:
        self.path = path
        self.raw = raw
        self.sha256 = sha256_bytes(raw)

    def text(self) -> str:
        return decode_captured_bytes(self.raw)

    def unchanged(self) -> bool:
        """Re-read the file and check the exact bytes still match the capture."""
        try:
            return sha256_bytes(self.path.read_bytes()) == self.sha256
        except OSError:
            return False


def capture_file(path: Path) -> CapturedSource:
    """Capture one file's exact bytes once for parsing and provenance."""
    return CapturedSource(path, path.read_bytes())


def _run_git(env: ExecutionEnvironment, cwd: Path, *args: str) -> tuple[int, str]:
    result = env.execute("git", list(args), cwd)
    return (result.returncode, result.stdout.strip())


def _run_git_absolute(env: ExecutionEnvironment, cwd: Path, *args: str) -> Path:
    code, out = _run_git(env, cwd, *args)
    if code != 0 or not out:
        raise CanonicalProjectError(
            CanonicalReadFailure.GIT_FAILURE,
            f"git {' '.join(args)} failed in {cwd}",
        )
    path = Path(out)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def parse_worktree_records(porcelain_stdout: str) -> list[dict[str, str]]:
    """Parse ``git worktree list --porcelain`` into ordered records.

    Spaceless flag lines (``bare``, ``detached``) are recorded as keys with
    an empty value so callers can actually see them.
    """

    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in porcelain_stdout.splitlines():
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        if " " in line:
            key, value = line.split(" ", 1)
            current[key] = value
        else:
            current[line] = ""
    if current:
        records.append(current)
    return records


def _select_main_record(records: list[dict[str, str]]) -> dict[str, str]:
    """Return the main working tree record (git lists it first), bare rejected."""
    if not records:
        raise CanonicalProjectError(
            CanonicalReadFailure.AMBIGUOUS_MAIN_WORKTREE,
            "empty worktree list output",
        )
    main = records[0]
    if "worktree" not in main or "bare" in main:
        raise CanonicalProjectError(
            CanonicalReadFailure.AMBIGUOUS_MAIN_WORKTREE,
            "no non-bare main working tree in worktree list",
        )
    return main


def _require_local_listed(records: list[dict[str, str]], local_root: Path) -> None:
    """Fail closed unless the local root is exactly one listed worktree."""
    matches = [
        record
        for record in records
        if "worktree" in record
        and "bare" not in record
        and Path(record["worktree"]).resolve() == local_root
    ]
    if not matches:
        raise CanonicalProjectError(
            CanonicalReadFailure.LOCAL_ROOT_NOT_LISTED,
            f"local root is not a listed git worktree: {local_root}",
        )
    if len(matches) > 1:
        raise CanonicalProjectError(
            CanonicalReadFailure.AMBIGUOUS_LOCAL_WORKTREE,
            f"local root appears as multiple listed worktrees: {local_root}",
        )


def _require_within(target: Path, directory: Path, failure_detail: str) -> None:
    """Fail closed unless *target* is a real path inside the real *directory*.

    Rejects symlink indirection on either side: an allowed directory that is
    itself a symlink (even pointing elsewhere inside the canonical root) and
    a target that symlinks out of the directory both fail closed.
    """

    if directory.is_symlink():
        raise CanonicalProjectError(
            CanonicalReadFailure.TRAVERSAL_ESCAPE,
            f"allowed directory is a symlink: {directory}",
        )
    if target.is_symlink():
        raise CanonicalProjectError(
            CanonicalReadFailure.TRAVERSAL_ESCAPE,
            f"target is a symlink: {target}",
        )
    resolved = target.resolve()
    directory_resolved = directory.resolve()
    if resolved != directory_resolved and not resolved.is_relative_to(
        directory_resolved
    ):
        raise CanonicalProjectError(
            CanonicalReadFailure.TRAVERSAL_ESCAPE, failure_detail
        )


def _validate_canonical_root(
    canonical_root: Path, common_git_dir: Path, env: ExecutionEnvironment
) -> None:
    if not canonical_root.is_dir():
        raise CanonicalProjectError(
            CanonicalReadFailure.CANONICAL_UNREADABLE,
            f"canonical main worktree missing: {canonical_root}",
        )
    memory_bank_dir = get_cortex_path(canonical_root, CortexResourceType.MEMORY_BANK)
    if not memory_bank_dir.is_dir():
        raise CanonicalProjectError(
            CanonicalReadFailure.CANONICAL_NOT_CORTEX_ROOT,
            f"canonical root has no .cortex/memory-bank: {canonical_root}",
        )
    canonical_common = _run_git_absolute(
        env,
        canonical_root,
        "rev-parse",
        "--path-format=absolute",
        "--git-common-dir",
    )
    if canonical_common != common_git_dir:
        raise CanonicalProjectError(
            CanonicalReadFailure.COMMON_DIR_MISMATCH,
            "canonical main worktree belongs to a different git repository",
        )


def _validate_containment(canonical_root: Path) -> None:
    """Fail closed when the canonical .cortex subtree uses symlink indirection."""
    for resource in (CortexResourceType.CORTEX_DIR, CortexResourceType.PLANS):
        _require_within(
            get_cortex_path(canonical_root, resource),
            canonical_root,
            f"canonical path escapes canonical root: {resource.value}",
        )


def canonical_plans_dir(identity: CanonicalProjectIdentity) -> Path:
    """Return the canonical plans directory, verified real and contained."""

    plans_dir = get_cortex_path(identity.canonical_root, CortexResourceType.PLANS)
    _require_within(
        plans_dir,
        identity.canonical_root,
        f"canonical plans directory escapes canonical root: {plans_dir}",
    )
    return plans_dir


def canonical_memory_bank_dir(identity: CanonicalProjectIdentity) -> Path:
    """Return the canonical memory-bank directory, verified real and contained."""

    memory_bank_dir = get_cortex_path(
        identity.canonical_root, CortexResourceType.MEMORY_BANK
    )
    _require_within(
        memory_bank_dir,
        identity.canonical_root,
        f"canonical memory-bank directory escapes canonical root: {memory_bank_dir}",
    )
    return memory_bank_dir


def canonical_memory_bank_file(
    identity: CanonicalProjectIdentity, file_name: str
) -> Path:
    """Return one memory-bank file path confined to the canonical memory-bank dir."""

    memory_bank_dir = canonical_memory_bank_dir(identity)
    if Path(file_name).name != file_name:
        raise CanonicalProjectError(
            CanonicalReadFailure.TRAVERSAL_ESCAPE,
            f"memory-bank file name must be a plain filename: {file_name}",
        )
    return _contained_file(memory_bank_dir, file_name, identity.canonical_root)


def canonical_artifact_file(
    identity: CanonicalProjectIdentity, relative_path: str
) -> Path:
    """Return one artifact report path confined to its closed artifact dir.

    Accepts only ``.cortex/<reviews|analyses|queries>/<name>.md`` so result
    references inside canonical approved summaries stay readable without
    granting arbitrary path access.
    """

    normalized = relative_path.strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    parts = Path(normalized).parts
    if (
        len(parts) != 3
        or parts[0] != CortexResourceType.CORTEX_DIR.value
        or parts[1] not in ARTIFACT_DIR_NAMES
        or Path(parts[2]).name != parts[2]
        or Path(normalized).suffix != ".md"
    ):
        raise CanonicalProjectError(
            CanonicalReadFailure.TRAVERSAL_ESCAPE,
            (
                f"not a closed artifact path "
                f"(.cortex/{'|'.join(ARTIFACT_DIR_NAMES)}/<name>.md): {relative_path}"
            ),
        )
    artifact_dir = identity.canonical_root / parts[0] / parts[1]
    return _contained_file(artifact_dir, parts[2], identity.canonical_root)


def _contained_file(directory: Path, name: str, canonical_root: Path) -> Path:
    """Return *directory*/*name* after real-path containment verification."""

    from cortex.core.file_system import FileSystemManager

    fs = FileSystemManager(canonical_root)
    try:
        path = fs.construct_safe_path(directory, name)
    except (ValueError, PermissionError) as exc:
        raise CanonicalProjectError(
            CanonicalReadFailure.TRAVERSAL_ESCAPE,
            f"invalid canonical file name: {exc}",
        ) from exc
    _require_within(
        path,
        directory,
        f"canonical file escapes its allowed directory: {path}",
    )
    return path


def _resolve_git_context(
    execution: ExecutionEnvironment, local: Path
) -> tuple[Path, list[dict[str, str]]]:
    """Return (common git dir, worktree records) or raise fail-closed."""
    code, _ = _run_git(execution, local, "rev-parse", "--git-common-dir")
    if code != 0:
        raise CanonicalProjectError(
            CanonicalReadFailure.NOT_A_GIT_CHECKOUT,
            f"not inside a git worktree: {local}",
        )
    common_git_dir = _run_git_absolute(
        execution,
        local,
        "rev-parse",
        "--path-format=absolute",
        "--git-common-dir",
    )
    code, porcelain = _run_git(execution, local, "worktree", "list", "--porcelain")
    if code != 0:
        raise CanonicalProjectError(
            CanonicalReadFailure.GIT_FAILURE, "git worktree list failed"
        )
    return (common_git_dir, parse_worktree_records(porcelain))


def _canonical_head(execution: ExecutionEnvironment, canonical_root: Path) -> str:
    """Return the canonical root HEAD revision or raise fail-closed."""
    code, revision = _run_git(execution, canonical_root, "rev-parse", "HEAD")
    if code != 0 or not revision:
        raise CanonicalProjectError(
            CanonicalReadFailure.GIT_FAILURE,
            f"cannot resolve canonical HEAD revision: {canonical_root}",
        )
    return revision


def resolve_canonical_identity(
    local_root: Path, env: ExecutionEnvironment | None = None
) -> CanonicalProjectIdentity:
    """Resolve the git-verified canonical main worktree identity for a root.

    Fail-closed for non-git roots, git failures, roots that are not exactly
    one listed worktree, bare/absent main worktrees, non-Cortex canonical
    roots, cross-repository mappings, and symlink indirection. Never writes.
    """

    execution = env if env is not None else LocalExecutionEnvironment()
    local = local_root.resolve()
    common_git_dir, records = _resolve_git_context(execution, local)
    _require_local_listed(records, local)
    canonical_root = Path(_select_main_record(records)["worktree"]).resolve()
    relation = (
        CanonicalRelation.LOCAL_IS_CANONICAL
        if canonical_root == local
        else CanonicalRelation.LINKED_WORKTREE
    )
    _validate_canonical_root(canonical_root, common_git_dir, execution)
    _validate_containment(canonical_root)
    return CanonicalProjectIdentity(
        local_root=local,
        canonical_root=canonical_root,
        relation=relation,
        common_git_dir=common_git_dir,
        git_revision=_canonical_head(execution, canonical_root),
    )


def revalidate_revision(
    identity: CanonicalProjectIdentity,
    env: ExecutionEnvironment | None = None,
) -> bool:
    """Re-check canonical HEAD after assembly; False means re-read required.

    Guards against a branch switch or rebase between identity resolution and
    final assembly binding provenance to a stale repository context.
    """

    execution = env if env is not None else LocalExecutionEnvironment()
    code, revision = _run_git(execution, identity.canonical_root, "rev-parse", "HEAD")
    return code == 0 and revision == identity.git_revision


def local_context_unsafe(local_root: Path) -> bool:
    """True when the local .cortex/plans tree uses symlink indirection.

    Shared by plan and file freshness so a symlinked ``.cortex`` ancestor
    (redirecting even inside the local root) is never hashed through.
    """

    cortex_dir = local_root / CortexResourceType.CORTEX_DIR.value
    plans_dir = get_cortex_path(local_root, CortexResourceType.PLANS)
    if cortex_dir.is_symlink() or plans_dir.is_symlink():
        return True
    return not plans_dir.resolve().is_relative_to(local_root)


__all__ = [
    "ARTIFACT_DIR_NAMES",
    "CanonicalLocalState",
    "CanonicalProjectError",
    "CanonicalProjectIdentity",
    "CanonicalReadFailure",
    "CanonicalReadProvenance",
    "CanonicalRelation",
    "canonical_artifact_file",
    "canonical_memory_bank_dir",
    "canonical_memory_bank_file",
    "canonical_plans_dir",
    "capture_file",
    "local_context_unsafe",
    "parse_read_source",
    "parse_worktree_records",
    "resolve_canonical_identity",
    "revalidate_revision",
    "sha256_bytes",
]
