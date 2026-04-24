"""Comprehensive on-disk logging of ``swift test`` invocations.

Each time the Swift adapter runs the test suite via ``run_quality_gate()``,
this module writes a fully self-contained transcript to
``.cortex/.session/logs/swift-test-<timestamp>.log`` inside the project so
users can attach it verbatim when asking for help. The log includes:

- wall-clock timing + environment summary
- exact argv + cwd + extra env overrides applied
- subprocess returncode (including negative signal codes)
- full stdout and full stderr (byte-accurate decode with replacement)
- the interpreted :class:`SwiftTestOutcome` that the gate will act on
- a summary of ``codecov/`` artifacts after the run (profraw / profdata /
  JSON) so coverage collection failures are reproducible from the log alone

The log is best-effort: any I/O failure while writing it is swallowed — we
never let logging break the gate. Log writes are rotated by truncating the
directory to the most recent 20 files to cap disk use.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .swift_test_diagnostics import SwiftTestOutcome

logger = logging.getLogger(__name__)

_LOG_SUBDIR = ".cortex/.session/logs"
_LOG_RETENTION = 20


@dataclass(frozen=True)
class SwiftTestLogRecord:
    """Bundle of a single ``swift test`` invocation for log emission."""

    argv: list[str]
    cwd: Path
    extra_env: dict[str, str] | None
    returncode: int
    stdout: str
    stderr: str
    outcome: SwiftTestOutcome
    elapsed_seconds: float
    codecov_dir: Path | None


def write_swift_test_log(project_root: Path, record: SwiftTestLogRecord) -> Path | None:
    """Write a swift-test transcript to disk; return the log path or ``None``.

    Callers MUST NOT depend on a log being written — any exception is
    logged at DEBUG level and the function returns ``None``. The gate must
    never be blocked by log I/O.
    """
    try:
        log_dir = project_root / _LOG_SUBDIR
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        log_path = log_dir / f"swift-test-{timestamp}.log"
        _ = log_path.write_text(_render_log(record), encoding="utf-8")
        _rotate_logs(log_dir)
        return log_path
    except Exception:
        logger.debug("swift-test log write failed", exc_info=True)
        return None


def _render_log(r: SwiftTestLogRecord) -> str:
    """Compose the textual log body. Kept deterministic for reproducibility."""
    header = _render_header(r)
    codecov_summary = _render_codecov_summary(r.codecov_dir)
    return (
        header
        + "\n===== CODECOV ARTIFACTS =====\n"
        + codecov_summary
        + "\n===== STDERR (full) =====\n"
        + r.stderr
        + "\n===== STDOUT (full) =====\n"
        + r.stdout
        + "\n"
    )


def _render_header(r: SwiftTestLogRecord) -> str:
    lines = [
        "===== CORTEX SWIFT TEST TRANSCRIPT =====",
        f"timestamp:   {datetime.now().isoformat(timespec='seconds')}",
        f"platform:    {sys.platform}",
        f"python:      {sys.version.split()[0]}",
        f"cwd:         {r.cwd}",
        f"argv:        {' '.join(r.argv)}",
        f"extra_env:   {r.extra_env or {}}",
        f"elapsed:     {r.elapsed_seconds:.1f}s",
        f"returncode:  {r.returncode}",
        f"outcome:     {r.outcome.status.value}",
        f"diagnostic:  {r.outcome.diagnostic}",
        f"teardown:    {r.outcome.teardown_signal}",
        f"tests:       {r.outcome.tests_reported}",
    ]
    return "\n".join(lines) + "\n"


def _render_codecov_summary(codecov_dir: Path | None) -> str:
    if codecov_dir is None:
        return "(no bin path resolved — swift build --show-bin-path failed)\n"
    if not codecov_dir.exists():
        return f"(codecov directory missing: {codecov_dir})\n"
    entries: list[str] = []
    for child in sorted(codecov_dir.iterdir()):
        try:
            size = child.stat().st_size
        except OSError:
            size = -1
        entries.append(f"{child.name}: {size} bytes")
    if not entries:
        return f"(codecov directory empty: {codecov_dir})\n"
    return f"{codecov_dir}:\n" + "\n".join(f"  - {e}" for e in entries) + "\n"


def _rotate_logs(log_dir: Path) -> None:
    """Keep only the newest :data:`_LOG_RETENTION` ``swift-test-*.log`` files."""
    try:
        logs = sorted(
            log_dir.glob("swift-test-*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in logs[_LOG_RETENTION:]:
            try:
                stale.unlink()
            except OSError:
                pass
    except Exception:
        logger.debug("swift-test log rotation failed", exc_info=True)
