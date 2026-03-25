"""Detached fix-quality worker.

Standalone script that applies formatting, linting, type-check, and quality
fixes in its own process, independent of the MCP server lifetime. Results are
written atomically to a JSON file that the MCP tool polls for.

Usage:
    python -m cortex.tools.execution.pre_commit_fix_worker \
        --result-file /path/to/result.json \
        --project-root /path/to/project \
        [--include-markdown-fix]
"""

# pyright: reportPrivateUsage=false
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

from cortex.tools.execution.pre_commit_helpers_models import PreCommitCheck
from cortex.tools.execution.pre_commit_worker import (
    _atomic_write,
    _resolve_adapter_worker,
    _resolve_rumdl_path,
    _write_status,
    collect_pre_commit_markdown_paths,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

_FIX_CHECKS = [
    PreCommitCheck.FIX_ERRORS.value,
    PreCommitCheck.FORMAT.value,
    PreCommitCheck.TYPE_CHECK.value,
    PreCommitCheck.QUALITY.value,
]


def _run_fix_checks(project_root: str) -> dict[str, object]:
    """Run fix checks synchronously and return result dict."""
    from cortex.tools.execution.pre_commit_helpers import determine_checks_to_perform
    from cortex.tools.execution.pre_commit_tools_run_helpers import (
        build_pre_commit_response,
        execute_all_checks,
    )

    resolved = _resolve_adapter_worker(project_root)
    if isinstance(resolved, dict):
        return resolved
    adapter, language_info = resolved
    checks_to_perform = determine_checks_to_perform(_FIX_CHECKS)
    results, stats = execute_all_checks(
        adapter,
        language_info.language,
        checks_to_perform,
        strict_mode=False,
        timeout=300,
        coverage_threshold=0.90,
    )
    return cast(
        dict[str, object],
        build_pre_commit_response(results, stats, language_info.language),
    )


def _run_markdown_fix(project_root: str) -> dict[str, object]:
    """Run rumdl --fix on all markdown files and return result dict."""
    root = Path(project_root)
    md_files = collect_pre_commit_markdown_paths(root)
    if not md_files:
        return {"success": True, "files_fixed": 0, "results": []}

    rumdl = _resolve_rumdl_path()
    cmd = [rumdl, "check", "--fix"] + md_files
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=120,
        )
        fixed = proc.returncode == 0
        files_fixed = len(md_files) if fixed else 0
        file_results = [{"file": Path(f).name, "fixed": fixed} for f in md_files]
        return {"success": fixed, "files_fixed": files_fixed, "results": file_results}
    except subprocess.TimeoutExpired:
        return {"success": False, "files_fixed": 0, "results": [], "error": "timeout"}
    except Exception as e:
        return {"success": False, "files_fixed": 0, "results": [], "error": str(e)}


def _write_success_result(
    result_path: Path,
    started: float,
    pid: int,
    checks_result: dict[str, object],
    markdown_result: dict[str, object] | None,
) -> None:
    """Write completed result atomically."""
    output: dict[str, object] = {
        "version": 1,
        "status": "completed",
        "started_at": started,
        "completed_at": time.time(),
        "pid": pid,
        "result": checks_result,
    }
    if markdown_result is not None:
        output["markdown_result"] = markdown_result
    _atomic_write(result_path, output)


def _run_worker_once(
    args: argparse.Namespace,
    result_path: Path,
    started: float,
    pid: int,
) -> None:
    """Run fix checks and write result; raises on failure."""
    checks_result = _run_fix_checks(args.project_root)
    markdown_result: dict[str, object] | None = None
    if args.include_markdown_fix:
        markdown_result = _run_markdown_fix(args.project_root)
    _write_success_result(result_path, started, pid, checks_result, markdown_result)
    logger.info("Fix worker completed in %.1fs", time.time() - started)


def _parse_fix_worker_args() -> argparse.Namespace:
    """Parse command-line arguments for the fix worker."""
    parser = argparse.ArgumentParser(description="Detached fix-quality worker")
    _ = parser.add_argument("--result-file", required=True)
    _ = parser.add_argument("--project-root", required=True)
    _ = parser.add_argument("--include-markdown-fix", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Entry point for detached fix worker."""
    args = _parse_fix_worker_args()
    result_path = Path(args.result_file)
    pid = os.getpid()
    _write_status(result_path, "running", pid)
    started = time.time()
    try:
        _run_worker_once(args, result_path, started, pid)
    except Exception as e:
        logger.exception("Fix worker failed: %s", e)
        _atomic_write(
            result_path,
            {
                "version": 1,
                "status": "error",
                "started_at": started,
                "completed_at": time.time(),
                "pid": pid,
                "error": str(e),
            },
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
