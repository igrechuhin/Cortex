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

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

from cortex.core.models import ModelDict, OperationStatus
from cortex.core.path_resolver import augmented_environ_with_project_venv_bins
from cortex.tools.execution.pre_commit_fix_quality import (
    finalize_autofix_result,
    get_tracked_git_changes,
)
from cortex.tools.execution.pre_commit_helpers_models import PreCommitCheck
from cortex.tools.execution.pre_commit_rumdl_resolve import (
    coerce_rumdl_argv0,
    markdown_rumdl_argv,
)
from cortex.tools.execution.pre_commit_worker import (
    atomic_write,
    collect_pre_commit_markdown_paths,
    resolve_adapter_worker,
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

    resolved = resolve_adapter_worker(project_root)
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
    root = Path(project_root).resolve()
    md_files = collect_pre_commit_markdown_paths(root)
    if not md_files:
        return {"success": True, "files_fixed": 0, "results": []}

    cmd = markdown_rumdl_argv(root, with_fix=True)
    if cmd and cmd[0] == "rumdl":
        cmd = coerce_rumdl_argv0(root, cmd)
    cmd = cmd + md_files
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            env=augmented_environ_with_project_venv_bins(root),
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


def _complete_fix_result(args: argparse.Namespace, output: dict[str, object]) -> None:
    """Collect raw evidence and finalize every fix before publishing success."""
    root = Path(args.project_root).resolve()
    tracked_before = get_tracked_git_changes(root)
    output["result"] = _run_fix_checks(args.project_root)
    if args.include_markdown_fix:
        output["markdown_result"] = _run_markdown_fix(args.project_root)
    output["autofix_result"] = finalize_autofix_result(
        root, cast(ModelDict, output), tracked_before
    )
    output["status"] = "completed"


def _run_worker_once(
    args: argparse.Namespace,
    result_path: Path,
    started: float,
    pid: int,
) -> None:
    """Run all fixes, preserving raw evidence on completion or failure."""
    output: dict[str, object] = {
        "version": 1,
        "status": "running",
        "started_at": started,
        "pid": pid,
        "autofix_pending": True,
    }
    atomic_write(result_path, output)
    try:
        _complete_fix_result(args, output)
    except Exception as e:
        output["status"] = OperationStatus.ERROR.value
        output["error"] = str(e)
        raise
    finally:
        output["completed_at"] = time.time()
        atomic_write(result_path, output)
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
    started = time.time()
    try:
        _run_worker_once(args, result_path, started, pid)
    except Exception as e:
        logger.exception("Fix worker failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
