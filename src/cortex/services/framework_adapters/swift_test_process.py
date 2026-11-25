"""Bounded SwiftPM timeout teardown independent of test outcome parsing."""

import logging
import signal
import subprocess
import time
from pathlib import Path

from .darwin_process_lineage import DarwinProcessLineage

logger = logging.getLogger(__name__)

# SwiftPM gives its registered cancellation handlers up to 30 seconds.
_INTERRUPT_GRACE_SECONDS = 32
_KILL_GRACE_SECONDS = 2
_LINEAGE_GRACE_SECONDS = 1


class SwiftTestTimeout(subprocess.TimeoutExpired):
    """A timed-out command with an explicit teardown verdict for this launch."""

    def __init__(self, timeout: subprocess.TimeoutExpired, verified: bool) -> None:
        super().__init__(timeout.cmd, timeout.timeout, timeout.output, timeout.stderr)
        self.verified = verified


def run_timed_swift_test(
    command: list[str], root: Path, timeout: int, env: dict[str, str] | None
) -> subprocess.CompletedProcess[bytes]:
    """Run SwiftPM with time to cancel and reap its runners after a timeout."""
    lineage = DarwinProcessLineage.open()
    if lineage is None:
        return subprocess.run(
            command, cwd=root, capture_output=True, timeout=timeout, env=env
        )

    process = subprocess.Popen(
        command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    launcher_id = None
    try:
        launcher_id = lineage.creation_id(process.pid)
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, process.wait(), stdout, stderr)
    except subprocess.TimeoutExpired as exc:
        cancellation_deadline = time.monotonic() + _INTERRUPT_GRACE_SECONDS
        latest, reaped = _interrupt_and_reap(process, exc, cancellation_deadline)
        # AI: Separate runner groups can finish cancellation after SwiftPM
        # exits and closes its pipes. Use the remaining cancellation budget
        # for proof, keeping a short minimum window after forced teardown.
        deadline = max(cancellation_deadline, time.monotonic() + _LINEAGE_GRACE_SECONDS)
        verified = (
            reaped
            and launcher_id is not None
            and lineage.verify_after_reap(launcher_id, deadline)
        )
        raise SwiftTestTimeout(latest, verified) from exc
    finally:
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def _interrupt_and_reap(
    process: subprocess.Popen[bytes],
    expired: subprocess.TimeoutExpired,
    cancellation_deadline: float,
) -> tuple[subprocess.TimeoutExpired, bool]:
    # AI: SwiftPM owns runner groups and its SIGINT handler cancels them. Only
    # signal the direct child here. Its descendants may be in other groups.
    try:
        process.send_signal(signal.SIGINT)
        remaining = max(0.0, cancellation_deadline - time.monotonic())
        stdout, stderr = process.communicate(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        # AI: An escaped process can retain a pipe after the launcher exits.
        # After escalation wait only for the child, without draining the pipes.
        _copy_output(expired, exc.output, exc.stderr)
        return expired, _kill_and_reap(process)
    except OSError:
        logger.warning("SwiftPM interrupt could not be observed", exc_info=True)
        _ = _kill_and_reap(process)
        return expired, False
    _copy_output(expired, stdout, stderr)
    return expired, True


def _copy_output(
    expired: subprocess.TimeoutExpired,
    stdout: str | bytes | None,
    stderr: bytes | None,
) -> None:
    expired.output = stdout if stdout is not None else expired.output
    expired.stderr = stderr if stderr is not None else expired.stderr


def _kill_and_reap(process: subprocess.Popen[bytes]) -> bool:
    try:
        process.kill()
        _ = process.wait(timeout=_KILL_GRACE_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        logger.warning("SwiftPM launcher exit could not be confirmed", exc_info=True)
        return False
    return True
