"""Detached bounded worker; executes existing approved code without a shell."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from cortex.tools.files.project_access.jobs import task_directory, worker_environment
from cortex.tools.files.project_access.models import ApprovedAccess, Request
from cortex.tools.files.project_access.paths import (
    read_bytes,
    remove_directory,
    write_new,
)
from cortex.tools.files.project_access.policy import approved_script, load_access

# AI: Preserve the original script's __file__, argv and import locations while executing pinned bytes.
_BOOTSTRAP = """import pathlib, sys, types
snapshot, original, root, *args = sys.argv[1:]
source = pathlib.Path(snapshot).read_bytes()
sys.path[:0] = [str(pathlib.Path(original).parent), root]
sys.argv = [original, *args]
module = types.ModuleType('__main__')
module.__file__ = original
module.__package__ = None
module.__spec__ = None
module.__cached__ = None
sys.modules['__main__'] = module
exec(compile(source, original, 'exec'), module.__dict__)
"""


def execute(access: ApprovedAccess, request: Request, task: str) -> dict[str, object]:
    """Reviewed scripts are trusted code; this wrapper is not an OS sandbox."""
    job = access.policy.jobs[request.job]
    script = approved_script(access, request.job)
    # AI: Execute the exact approved bytes; a source-path swap after validation cannot change them.
    script_path = task + "/approved.py"
    write_new(access.root, script_path, script)
    output = str(access.root / task / "output")
    substitutions = {"{output_directory}": output}
    substitutions.update({"{" + k + "}": v for k, v in request.parameters.items()})
    arguments = [substitutions.get(a, a) for a in job.arguments]
    command = [
        job.interpreter,
        "-I",
        "-c",
        _BOOTSTRAP,
        str(access.root / script_path),
        str(access.root / job.script),
        str(access.root),
        *arguments,
    ]
    return execute_command(access, command, job.timeout)


def execute_command(
    access: ApprovedAccess, command: list[str], timeout: int
) -> dict[str, object]:
    """Wait within the approved budget and terminate the process group on timeout."""
    process = subprocess.Popen(
        command,
        cwd=access.root,
        env=worker_environment(access),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        _ = process.wait()
        return {"outcome": "timed_out"}
    return {"outcome": "succeeded" if code == 0 else "failed", "exit_code": code}


def run(root: Path, task: str) -> None:
    """Claim once even if a worker process is accidentally invoked twice."""
    access = load_access(root)
    request = Request.model_validate_json(
        read_bytes(root, task + "/request.json", 16384)
    )
    if task != task_directory(access, request):
        raise ValueError("Worker task does not match approved request")
    try:
        write_new(root, task + "/claimed", b"claimed")
    except FileExistsError:
        return
    try:
        result = execute(access, request, task)
    except (OSError, ValueError, KeyError):
        result = {"outcome": "refused_or_failed"}
    write_new(root, task + "/terminal.json", json.dumps(result).encode())
    remove_directory(root, access.policy.output_directory, "active")


if __name__ == "__main__":
    run(Path(sys.argv[1]), sys.argv[2])
