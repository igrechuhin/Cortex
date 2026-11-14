"""Durable exclusive reservations for reviewed project calculations."""

import hashlib
import json
import re
import subprocess
import sys

from cortex.tools.files.project_access.models import (
    ApprovedAccess,
    Job,
    Request,
    Terminal,
)
from cortex.tools.files.project_access.paths import (
    create_directory,
    directory,
    read_bytes,
    read_text,
    relative_parts,
    remove_directory,
    write_new,
)
from cortex.tools.files.project_access.policy import (
    HASH_ENV,
    POLICY_ENV,
    approved_script,
)

_WORKERS: list[subprocess.Popen[bytes]] = []


def reap_workers() -> None:
    """Retain and reap child handles instead of abandoning live Popen objects."""
    _WORKERS[:] = [worker for worker in _WORKERS if worker.poll() is None]


def validate_parameters(job: Job, request: Request) -> None:
    """Only finite operator-approved choices become argv values."""
    if set(job.parameters) != set(request.parameters):
        raise ValueError("Parameters must match the approved job exactly")
    for name, choices in job.parameters.items():
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name)
            or name == "output_directory"
            or not choices
            or len(choices) > 32
        ):
            raise ValueError("Invalid approved parameter definition")
        if request.parameters[name] not in choices or any(
            len(c) > 128 for c in choices
        ):
            raise ValueError("Parameter is not an approved bounded choice")
    replacements = {"{output_directory}"} | {"{" + n + "}" for n in job.parameters}
    if "{output_directory}" not in job.arguments:
        raise ValueError("Approved job must accept an explicit fresh output directory")
    if any(
        len(a) > 512 or ("{" in a or "}" in a) and a not in replacements
        for a in job.arguments
    ):
        raise ValueError("Only whole-argument approved placeholders are supported")


def task_directory(access: ApprovedAccess, request: Request) -> str:
    """Same job and parameters always identify the same reservation, across sessions."""
    if request.job not in access.policy.jobs:
        raise ValueError("Job is not approved")
    validate_parameters(access.policy.jobs[request.job], request)
    payload = json.dumps([request.job, request.parameters], sort_keys=True).encode()
    key = hashlib.sha256(payload).hexdigest()
    return access.policy.output_directory + "/" + key


def status(access: ApprovedAccess, request: Request) -> dict[str, object]:
    """Missing terminal publication remains uncertain and never authorizes rerun."""
    reap_workers()
    task = task_directory(access, request)
    try:
        state = Terminal.model_validate_json(
            read_bytes(access.root, task + "/terminal.json", 4096)
        )
    except FileNotFoundError:
        try:
            with directory(access.root, relative_parts(task)):
                pass
        except FileNotFoundError:
            return {"state": "not_started", "task": task}
        return {
            "state": "reserved_or_running",
            "task": task,
            "note": "No terminal result; do not retry execution or delete the reservation",
        }
    return {
        "state": state.model_dump(mode="json"),
        "task": task,
        "output_directory": task + "/output",
    }


def worker_environment(access: ApprovedAccess) -> dict[str, str]:
    """No inherited credentials, PYTHONPATH, proxy or shell environment."""
    return {
        POLICY_ENV: str(access.policy_path),
        HASH_ENV: access.policy_hash,
        "PATH": "/usr/bin:/bin",
        "LANG": "en_US.UTF-8",
    }


def start(access: ApprovedAccess, request: Request) -> dict[str, object]:
    """Reserve before spawn; interrupted launch can never be blindly repeated."""
    task = task_directory(access, request)
    existing = status(access, request)
    if existing.get("state") != "not_started":
        return {"duplicate": True, **existing}
    _ = approved_script(access, request.job)
    if not create_directory(access.root, access.policy.output_directory, "active"):
        return {"state": "busy", "note": "One job already reserved; inspect its status"}
    parent, name = task.rsplit("/", 1)
    if not create_directory(access.root, parent, name):
        remove_directory(access.root, access.policy.output_directory, "active")
        return {"duplicate": True, **status(access, request)}
    write_new(access.root, task + "/request.json", request.model_dump_json().encode())
    _ = create_directory(access.root, task, "output")
    launch_worker(access, task)
    return {"state": "reserved_or_running", "task": task, "duplicate": False}


def launch_worker(access: ApprovedAccess, task: str) -> None:
    """Spawn only the fixed Cortex worker with validated reserved state."""
    command = [
        sys.executable,
        "-m",
        "cortex.tools.files.project_access.worker",
        str(access.root),
        task,
    ]
    try:
        worker = subprocess.Popen(
            command,
            cwd=access.root,
            env=worker_environment(access),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _WORKERS.append(worker)
    except OSError:
        write_new(access.root, task + "/terminal.json", b'{"outcome":"launch_failed"}')
        remove_directory(access.root, access.policy.output_directory, "active")
        raise ValueError("Worker launch failed; reservation retained") from None


def read_output(access: ApprovedAccess, request: Request) -> dict[str, object]:
    """Output text is read by exact relative path with the same secret checks."""
    task = task_directory(access, request)
    _ = relative_parts(request.path)
    _ = read_bytes(access.root, task + "/terminal.json", 4096)
    return read_text(
        access.root, task + "/output/" + request.path, request.offset, request.length
    )
