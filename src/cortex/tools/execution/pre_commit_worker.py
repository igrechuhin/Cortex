"""Detached pre-commit pipeline worker.

Standalone script that runs pre-commit checks in its own process,
independent of the MCP server lifetime. Results are written atomically
to a JSON file that the MCP tool polls for.

Usage:
    python -m cortex.tools.execution.pre_commit_worker \
        --checks format type_check tests \
        --result-file /path/to/result.json \
        --project-root /path/to/project
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import augmented_environ_with_project_venv_bins
from cortex.services.framework_adapters.base import (
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
from cortex.services.language_detector import LanguageInfo
from cortex.services.language_quality_router import LanguageQualityRouter
from cortex.tools.execution.pre_commit_helpers_models import (
    CheckStats,
    PreCommitCheck,
    QualityCheckResult,
)
from cortex.tools.execution.pre_commit_rumdl_resolve import (
    markdown_rumdl_argv,
    uv_executable,
)
from cortex.tools.execution.pre_commit_submodule_guard import precommit_block_response
from cortex.tools.execution.pre_commit_tools_run_helpers import (
    build_pre_commit_response,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def write_status(result_path: Path, status: str, pid: int) -> None:
    """Write a running/error status marker atomically."""
    data: dict[str, object] = {
        "version": 1,
        "status": status,
        "started_at": time.time(),
        "pid": pid,
    }
    atomic_write(result_path, data)


def atomic_write(result_path: Path, data: dict[str, object]) -> None:
    """Write JSON atomically via tmp file + rename."""
    result_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(result_path.parent), suffix=".tmp", prefix=".worker_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(tmp, str(result_path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def resolve_adapter_worker(
    project_root: str,
) -> dict[str, object] | tuple[FrameworkAdapter, LanguageInfo]:
    """Resolve language and adapter in worker. Returns error dict or (adapter, language_info)."""
    from cortex.tools.execution.pre_commit_helpers_language import (
        detect_or_use_language,
    )

    lang_result = detect_or_use_language(None, project_root)
    if isinstance(lang_result, str):
        return {"status": "error", "error": lang_result}
    language_info, root_to_use = lang_result
    adapter = LanguageQualityRouter.get_adapter(language_info.language, root_to_use)
    if adapter is None:
        return {
            "status": "error",
            "error": f"Unsupported language: {language_info.language}",
        }
    return (adapter, language_info)


def _build_response_dict(
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    language: str,
) -> dict[str, object]:
    """Build pre-commit response dict from results and stats."""
    return cast(
        dict[str, object],
        build_pre_commit_response(results, stats, language),
    )


def _execute_checks_and_build_response(
    adapter: FrameworkAdapter,
    language_info: LanguageInfo,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    timeout: int,
    coverage_threshold: float,
) -> dict[str, object]:
    """Run execute_all_checks and build_pre_commit_response; return result dict."""
    from cortex.tools.execution.pre_commit_tools_run_helpers import (
        execute_all_checks,
    )

    results: dict[str, CheckResult | TestResult | QualityCheckResult]
    results, stats = execute_all_checks(
        adapter,
        language_info.language,
        checks_to_perform,
        strict_mode,
        timeout,
        coverage_threshold,
    )
    return _build_response_dict(results, stats, language_info.language)


def _run_checks_core(
    adapter: FrameworkAdapter,
    language_info: LanguageInfo,
    checks: list[str],
    strict_mode: bool,
    timeout: int,
    coverage_threshold: float,
) -> dict[str, object]:
    """Execute checks and build response dict."""
    from cortex.tools.execution.pre_commit_helpers import (
        determine_checks_to_perform,
    )

    checks_to_perform = determine_checks_to_perform(checks)
    return _execute_checks_and_build_response(
        adapter,
        language_info,
        checks_to_perform,
        strict_mode,
        timeout,
        coverage_threshold,
    )


def _run_checks(
    project_root: str,
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
) -> dict[str, object]:
    """Run pre-commit checks synchronously, return result dict."""
    resolved = resolve_adapter_worker(project_root)
    if isinstance(resolved, dict):
        return resolved
    adapter, language_info = resolved
    return _run_checks_core(
        adapter, language_info, checks, strict_mode, timeout, coverage_threshold
    )


_MD_EXCLUDE_DIRS = frozenset(
    {"node_modules", ".venv", "venv", "__pycache__", ".git", ".build"}
)
_MD_EXCLUDE_PREFIXES = (".cortex/plans/archive", ".cortex/history/", ".cortex/.cache/")


def _is_collectable_markdown(path: Path, root: Path) -> bool:
    """Return True when path is a markdown file that should be linted."""
    if not path.is_file() or path.suffix not in (".md", ".mdc"):
        return False
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    if any(d in rel.parts for d in _MD_EXCLUDE_DIRS):
        return False
    rel_str = str(rel).replace("\\", "/")
    return not any(rel_str.startswith(p) for p in _MD_EXCLUDE_PREFIXES)


def collect_pre_commit_markdown_paths(root: Path, max_files: int = 500) -> list[str]:
    """Collect markdown file paths under root, excluding common dirs and archive.

    Versioned memory-bank snapshots under ``.cortex/history/`` and session cache
    markdown under ``.cortex/.cache/`` are excluded: they are not hand-edited
    sources of truth and contain sibling-relative links invalid from those paths.
    """
    md_files: list[str] = []
    for path in sorted(root.rglob("*")):
        if len(md_files) >= max_files:
            break
        if _is_collectable_markdown(path, root):
            md_files.append(str(path))
    return md_files


def _run_subprocess_attempt(
    attempt: list[str],
    env: dict[str, str],
    root: Path,
) -> dict[str, object] | None:
    """Run one rumdl invocation; return result dict or None on FileNotFoundError."""
    try:
        proc = subprocess.run(
            attempt,
            capture_output=True,
            text=True,
            cwd=str(root),
            env=env,
            timeout=120,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return {"files_with_errors": 1, "status": "error", "error": "timeout"}
    except OSError as e:
        return {"files_with_errors": 0, "status": "error", "error": str(e)}
    if proc.returncode == 0:
        return {"files_with_errors": 0, "status": "success"}
    return {
        "files_with_errors": 1,
        "status": "error",
        "output": (proc.stdout + "\n" + proc.stderr)[:2000],
    }


def _build_rumdl_attempts(
    root: Path, cmd: list[str], md_files: list[str]
) -> list[list[str]]:
    """Build ordered list of rumdl invocation attempts from most to least specific."""
    tail = list(cmd[1:]) + md_files
    attempts: list[list[str]] = [cmd + md_files]
    argv0 = cmd[0] if cmd else ""
    p0 = Path(argv0)
    # Only add venv fallbacks when argv0 is bare "rumdl" or a bin-sibling path
    # (not when it is already a `uv run` invocation — that would double the prefix).
    if argv0 == "rumdl" or (p0.name == "rumdl" and p0.parent.name == "bin"):
        for rel in (".venv/bin/rumdl", "venv/bin/rumdl"):
            explicit = str((root / rel).resolve())
            if explicit != argv0:
                attempts.append([explicit, *tail])
    return attempts


def _run_markdownlint_subprocess(
    root: Path, cmd: list[str], md_files: list[str]
) -> dict[str, object]:
    """Run rumdl markdown lint and return result dict.

    The detached worker only needs a coarse signal for the commit pipeline:
    whether any Markdown files have lint errors. We therefore treat any
    non-zero rumdl exit code as at least one file with errors.
    """
    if not md_files:
        return {"files_with_errors": 0}
    env = augmented_environ_with_project_venv_bins(root)
    for attempt in _build_rumdl_attempts(root, cmd, md_files):
        result = _run_subprocess_attempt(attempt, env, root)
        if result is not None:
            return result
    # All attempts raised FileNotFoundError — try `uv run rumdl` as a last resort.
    # Only do this when cmd does NOT already start with uv (avoid doubled prefix).
    uv_bin = uv_executable()
    is_uv_cmd = bool(cmd) and Path(cmd[0]).name == "uv"
    if uv_bin and not is_uv_cmd:
        uv_result = _run_subprocess_attempt(
            [uv_bin, "run", "rumdl", "check", *md_files], env, root
        )
        if uv_result is not None:
            return uv_result
    return {"files_with_errors": 0, "status": "error", "error": "rumdl not found"}


def _run_markdown_lint(project_root: str) -> dict[str, object]:
    """Run rumdl in check-only mode, return result dict."""
    root = Path(project_root).resolve()
    cmd = markdown_rumdl_argv(root, with_fix=False)
    md_files = collect_pre_commit_markdown_paths(root)
    logger.info("markdown lint rumdl argv=%s md_files=%d", cmd, len(md_files))
    return _run_markdownlint_subprocess(root, cmd, md_files)


def _parse_worker_args() -> argparse.Namespace:
    """Parse command-line arguments for the detached worker."""
    parser = argparse.ArgumentParser(description="Detached pre-commit worker")
    _ = parser.add_argument("--checks", nargs="*", default=[])
    _ = parser.add_argument("--phase", choices=["A", "B", "full"], default=None)
    _ = parser.add_argument("--timeout", type=int, default=300)
    _ = parser.add_argument("--coverage-threshold", type=float, default=0.9)
    _ = parser.add_argument("--strict", action="store_true")
    _ = parser.add_argument("--include-markdown-lint", action="store_true")
    _ = parser.add_argument("--result-file", required=True)
    _ = parser.add_argument("--project-root", required=True)
    return parser.parse_args()


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
    atomic_write(result_path, output)


def _run_worker_once(
    args: argparse.Namespace,
    result_path: Path,
    started: float,
    pid: int,
) -> None:
    """Run checks and write success result; raises on failure."""
    blocked = precommit_block_response(Path(args.project_root))
    if blocked is not None:
        _write_success_result(
            result_path, started, pid, cast(dict[str, object], blocked), None
        )
        logger.info("Worker stopped early: submodule hygiene check failed")
        return
    checks_result = _run_checks(
        args.project_root,
        args.checks,
        args.timeout,
        args.coverage_threshold,
        args.strict,
    )
    markdown_result = (
        _run_markdown_lint(args.project_root) if args.include_markdown_lint else None
    )
    _write_success_result(result_path, started, pid, checks_result, markdown_result)
    logger.info("Worker completed in %.1fs", time.time() - started)


def main() -> None:
    """Entry point for detached worker."""
    args = _parse_worker_args()
    result_path = Path(args.result_file)
    pid = os.getpid()
    write_status(result_path, "running", pid)
    started = time.time()
    try:
        _run_worker_once(args, result_path, started, pid)
    except Exception as e:
        logger.exception("Worker failed: %s", e)
        atomic_write(
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
