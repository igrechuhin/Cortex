"""Non-expiring checkout lease covering worker startup and process lifetime."""

# cspell:words pgid getpgrp RDWR

from __future__ import annotations

import logging
import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from cortex.tools.execution.pre_commit_ownership import current_owner
from cortex.tools.execution.session_paths import session_dir

logger = logging.getLogger(__name__)

LEASE_FD_ENV = "CORTEX_QUALITY_LEASE_FD"
LEASE_OWNER_ENV = "CORTEX_QUALITY_LEASE_OWNER"
LEASE_REQUEST_ENV = "CORTEX_QUALITY_LEASE_REQUEST"
_LOCK_NAME = "quality-worker.lock"
_RECORD_NAME = "quality-worker-lease.json"


class LeaseState(str, Enum):
    """A running lease needs positive completion evidence before reuse."""

    STARTING = "starting"
    RUNNING = "running"
    TERMINAL = "terminal"


class WorkspaceLease(BaseModel):
    """Private durable ownership metadata, never returned to another caller."""

    model_config = ConfigDict(extra="forbid")
    version: int = Field(default=1, ge=1, le=2)
    owner: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    attempt_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    state: LeaseState = LeaseState.STARTING
    pgid: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_process_group(self) -> WorkspaceLease:
        if self.state != LeaseState.STARTING and self.pgid is None:
            raise ValueError("A worker lease requires its process group")
        if (self.version == 2) != (self.attempt_id is not None):
            raise ValueError("Only a version 2 workspace lease has an attempt ID")
        return self


class _CompletionReceipt(BaseModel):
    """Only the identity and completion fields are relevant to the lease."""

    owner: str
    pid: int = Field(gt=0, strict=True)
    status: str
    completed_at: float = Field(gt=0, allow_inf_nan=False)
    workspace_completion_attempt: str


class WorkspaceBusy(RuntimeError):
    """A caller must wait rather than adopt or launch another workspace job."""


class _HeldLease(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    root: Path
    fd: int
    record: WorkspaceLease


_HELD: ContextVar[_HeldLease | None] = ContextVar(
    "quality_workspace_lease", default=None
)
_WORKER_LEASE: ContextVar[WorkspaceLease | None] = ContextVar(
    "quality_worker_record", default=None
)
_WORKER_UNCERTAIN: ContextVar[bool] = ContextVar(
    "quality_worker_uncertain", default=False
)


def busy_response() -> dict[str, object]:
    """A foreign occupant's identifiers and result paths are never disclosed."""
    return {
        "status": "running",
        "busy": True,
        "reason": "workspace_occupied",
        "preflight_passed": False,
        "message": "Workspace checks or fixes are occupied. Retry after they finish. An interrupted run with unconfirmed completion requires owner review.",
    }


def _read_record(root: Path) -> WorkspaceLease | None:
    try:
        content = (session_dir(root) / _RECORD_NAME).read_text()
    except FileNotFoundError:
        return None
    try:
        return WorkspaceLease.model_validate_json(content)
    except ValidationError as exc:
        raise WorkspaceBusy("Workspace coordination state requires review") from exc


def _write_record(root: Path, record: WorkspaceLease) -> None:
    directory = session_dir(root)
    fd, name = tempfile.mkstemp(prefix=".quality-lease-", dir=directory)
    try:
        with os.fdopen(fd, "w") as stream:
            _ = stream.write(record.model_dump_json(exclude_none=True))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, directory / _RECORD_NAME)
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(name).unlink(missing_ok=True)


def process_group_alive(pgid: int | None) -> bool:
    if pgid is None:
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except (OSError, OverflowError):
        return True
    return True


def _has_completion_receipt(root: Path, record: WorkspaceLease) -> bool:
    from cortex.tools.execution.pre_commit_detached import fix_result_path
    from cortex.tools.execution.pre_commit_process import pre_commit_result_path

    if record.attempt_id is None:
        return False
    directory = session_dir(root)
    for result_path in (
        pre_commit_result_path(directory, record.request_id),
        fix_result_path(directory, record.request_id),
    ):
        try:
            receipt = _CompletionReceipt.model_validate_json(result_path.read_bytes())
        except (OSError, ValidationError):
            continue
        if (
            receipt.status == "completed"
            and receipt.owner == record.owner
            and receipt.pid == record.pgid
            and receipt.workspace_completion_attempt == record.attempt_id
        ):
            return True
    return False


def _record_occupied(root: Path, record: WorkspaceLease | None) -> bool:
    if record is None or record.state == LeaseState.STARTING:
        # AI: Acquiring flock proves every startup holder closed its descriptor;
        # no checks may start until the worker durably enters RUNNING.
        return False
    if process_group_alive(record.pgid):
        return True
    if record.state == LeaseState.TERMINAL:
        return False
    # AI: An empty group does not exclude escaped descendants. Require evidence
    # from the exact worker attempt, including when the same request and PID recur.
    if _has_completion_receipt(root, record):
        return False
    logger.debug("Unconfirmed quality worker completion: job_id=%s", record.request_id)
    return True


def _lock_fd(fd: int) -> None:
    try:
        import fcntl
    except ImportError as exc:
        raise WorkspaceBusy(
            "Process-lifetime workspace locking is unavailable"
        ) from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise WorkspaceBusy("Workspace lease is occupied") from exc


def _open_locked_fd(root: Path) -> int:
    if os.name != "posix":
        raise WorkspaceBusy("Process-lifetime workspace locking is unavailable")
    fd = os.open(
        session_dir(root) / _LOCK_NAME,
        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
        0o600,
    )
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise WorkspaceBusy("Workspace lock is unsafe")
        _lock_fd(fd)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _claim_record(root: Path, request_id: str) -> WorkspaceLease:
    """Check and replace the previous record while holding its mutex."""
    previous = _read_record(root)
    if _record_occupied(root, previous):
        raise WorkspaceBusy(
            "Workspace worker or descendants require completion or review"
        )
    record = WorkspaceLease(
        version=2, owner=current_owner(), request_id=request_id, attempt_id=uuid4().hex
    )
    _write_record(root, record)
    if previous is not None and previous.state == LeaseState.RUNNING:
        logger.info(
            "Recovered quality worker lease from completion receipt: job_id=%s pgid=%s",
            previous.request_id,
            previous.pgid,
        )
    return record


@contextmanager
def workspace_lease(root: Path, request_id: str) -> Iterator[None]:
    """Atomically inspect, replace and hold a lease until spawn transfers it."""
    root = root.resolve()
    held = _HELD.get()
    if held is not None:
        if held.root != root or held.record.request_id != request_id:
            raise WorkspaceBusy("A different request already holds this lease")
        yield
        return
    fd = _open_locked_fd(root)
    token = None
    try:
        record = _claim_record(root, request_id)
        token = _HELD.set(_HeldLease(root=root, fd=fd, record=record))
        yield
    finally:
        if token is not None:
            _HELD.reset(token)
        # AI: Never LOCK_UN here: the child shares this open description. Closing
        # only our descriptor preserves the inherited worker's flock protection.
        os.close(fd)


def inherited_lease(root: Path) -> tuple[tuple[int, ...], dict[str, str]]:
    """Supply only the current guarded spawn's private descriptor and identity."""
    held = _HELD.get()
    if held is None or held.root != root.resolve():
        raise WorkspaceBusy("Worker launch requires a workspace lease")
    return (held.fd,), {
        LEASE_FD_ENV: str(held.fd),
        LEASE_OWNER_ENV: held.record.owner,
        LEASE_REQUEST_ENV: held.record.request_id,
    }


def worker_owner() -> str | None:
    """Inherited environment alone must not label a server's result as worker-owned."""
    lease = _WORKER_LEASE.get()
    return lease.owner if lease is not None else None


def worker_completion_attempt() -> str | None:
    """Identify a worker attempt whose completed receipt can settle its lease."""
    lease = _WORKER_LEASE.get()
    if lease is None or _WORKER_UNCERTAIN.get():
        return None
    return lease.attempt_id


def mark_worker_uncertain() -> None:
    """A validated worker must retain its lease after an interrupted test command."""
    if _WORKER_LEASE.get() is not None:
        _ = _WORKER_UNCERTAIN.set(True)


def _adopt_worker_lease(root: Path, fd: int) -> WorkspaceLease:
    lock_stat = (session_dir(root) / _LOCK_NAME).stat(follow_symlinks=False)
    inherited_stat = os.fstat(fd)
    if (lock_stat.st_dev, lock_stat.st_ino) != (
        inherited_stat.st_dev,
        inherited_stat.st_ino,
    ):
        raise WorkspaceBusy("Inherited workspace lease does not match checkout")
    _lock_fd(fd)
    record = _read_record(root)
    if (
        record is None
        or record.owner != os.environ.get(LEASE_OWNER_ENV)
        or record.request_id != os.environ.get(LEASE_REQUEST_ENV)
    ):
        raise WorkspaceBusy("Inherited workspace ownership does not match")
    if os.getpgrp() != os.getpid() or record.state != LeaseState.STARTING:
        raise WorkspaceBusy("Worker must own a new process group and startup lease")
    record.state, record.pgid = LeaseState.RUNNING, os.getpgrp()
    _write_record(root, record)
    return record


@contextmanager
def worker_lease(root: Path) -> Iterator[None]:
    """Validate the inherited lease before checks, then retain crash evidence."""
    raw_fd = os.environ.get(LEASE_FD_ENV, "")
    if not raw_fd.isdecimal():
        raise WorkspaceBusy("Start workers through the guarded Cortex entry point")
    fd = int(raw_fd)
    record = _adopt_worker_lease(root, fd)
    token = _WORKER_LEASE.set(record)
    uncertain_token = _WORKER_UNCERTAIN.set(False)
    try:
        yield
    except BaseException:
        raise  # An abnormal exit intentionally leaves non-expiring RUNNING evidence.
    else:
        if not _WORKER_UNCERTAIN.get():
            record.state = LeaseState.TERMINAL
            _write_record(root, record)
    finally:
        _WORKER_UNCERTAIN.reset(uncertain_token)
        _WORKER_LEASE.reset(token)
        os.close(fd)
