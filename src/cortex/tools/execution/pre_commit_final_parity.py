"""Execute the existing Synapse parity checks in the staged-final server."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

_CHANGED_CHECKS = ("check_file_sizes.py", "check_function_lengths.py", "build.py")


def _scripts(root: Path, name: str) -> tuple[Path, ...]:
    scripts = root / ".cortex" / "synapse" / "scripts"
    return tuple(sorted(scripts.glob(f"*/{name}")))


def _run(
    root: Path,
    args: list[str],
    *,
    files: str | None = None,
    full_scan: bool = False,
) -> bytes:
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in {"FILES", "ALLOW_FULL_SCAN"}
    }
    if files is not None:
        env["FILES"] = files
    if full_scan:
        env["ALLOW_FULL_SCAN"] = "1"
    try:
        return subprocess.check_output(
            args, cwd=root, env=env, stderr=subprocess.STDOUT, timeout=900
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.output.decode(errors="replace")[-2000:].strip()
        raise ValueError(f"Staged parity failed ({args[-1]}): {detail}") from exc


def _run_checks(root: Path) -> None:
    changed = _run(root, ["git", "diff", "--name-only", "HEAD"]).decode()
    changed += _run(root, ["git", "diff", "--name-only"]).decode()
    project_python = str(root / ".venv" / "bin" / "python")
    for name in _CHANGED_CHECKS:
        for script in _scripts(root, name):
            _ = _run(root, [project_python, str(script)], files=changed)
    for script in _scripts(root, "check_file_sizes.py"):
        _ = _run(root, [project_python, str(script)], full_scan=True)
    workflow = root / ".github" / "workflows" / "quality.yml"
    if workflow.exists() and "check_public_docs" in workflow.read_text():
        script = (
            root / ".cortex" / "synapse" / "scripts" / "swift" / "check_public_docs.py"
        )
        threshold = os.environ.get("DOCC_PUBLIC_THRESHOLD") or "439"
        _ = _run(
            root,
            ["python3", str(script), "Sources", "--threshold", threshold, "--quiet"],
        )


async def run_staged_final_parity(root: Path) -> None:
    """Run fixed Phase A paths, never an MCP-provided shell command."""
    await asyncio.to_thread(_run_checks, root)
