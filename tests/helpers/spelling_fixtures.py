"""Installed-executable boundary faults for real spelling subprocess consumers."""

import os
import shlex
import shutil
import signal
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPELLING_CASES = [
    pytest.param("success", True, "All spelling checks passed", id="success"),
    # cspell:disable-next-line
    pytest.param("findings", False, "Unknown word: mispellled", id="findings"),
    pytest.param("missing", False, "No such file", id="missing-tool"),
    pytest.param("preflight", False, "version probe failed", id="preflight-error"),
    pytest.param("version", False, "require 8.6.1", id="unsupported-version"),
    pytest.param("cli", False, "unknown option '--files-only'", id="cli-error"),
    pytest.param("permission", False, "Permission denied", id="startup-permission"),
    pytest.param("eacces", False, "EACCES", id="checker-permission"),
    pytest.param("transport", False, "ECONNRESET", id="transport"),
    pytest.param("timeout", False, "timed out", id="lint-timeout"),
    pytest.param("preflight-timeout", False, "timed out", id="preflight-timeout"),
    pytest.param("hard-timeout", False, "timed out", id="kill-timeout"),
    pytest.param("signal", False, "checker exit code -15", id="checker-signal"),
]
CHECKER_SOURCE = """import os
import signal
import subprocess
import sys
import time
from pathlib import Path

mode = sys.argv[1]
root = Path(__file__).parent
(root / "checker.pid").write_text(str(os.getpid()))
version_probe = sys.argv[2:] == ["--version"]
if mode == "preflight" and version_probe:
    print("version probe failed", flush=True)
    print("preflight stderr preserved", file=sys.stderr, flush=True)
    sys.exit(21)
if version_probe and mode != "preflight-timeout":
    print("9.0.0" if mode == "version" else "8.6.1")
    sys.exit(0)
if mode in {"timeout", "preflight-timeout"}:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    (root / "checker-child.pid").write_text(str(child.pid))

    def stop(_signum: int, _frame: object) -> None:
        child.terminate()
        child.wait(timeout=1)
        (root / "child-reaped").write_text("yes")
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    print("checker waiting", flush=True)
    time.sleep(60)
if mode == "hard-timeout":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    print("checker ignoring termination", flush=True)
    time.sleep(60)
if mode == "signal":
    os.kill(os.getpid(), signal.SIGTERM)
assert sys.argv[2:4] == ["lint", "--no-progress"], sys.argv
assert any(path.endswith(".py") for path in sys.argv[4:]), sys.argv
failures = {
    # cspell:disable-next-line
    "findings": (1, "src/subject.py:1:1 - Unknown word: mispellled"),
    "cli": (2, "error: unknown option '--files-only'"),
    "eacces": (13, "npm error code EACCES: cache permission denied"),
    "transport": (17, "npm error code ECONNRESET: connection reset"),
}
code, diagnostic = failures.get(mode, (0, "Checked source files"))
print(diagnostic, flush=True)
print("checker stderr preserved", file=sys.stderr, flush=True)
sys.exit(code)
"""


def install_spelling_script(root: Path) -> Path:
    """Copy the real stdlib script and its utility, not a replacement verdict."""
    scripts = root / ".cortex" / "synapse" / "scripts" / "python"
    scripts.mkdir(parents=True, exist_ok=True)
    for name in ("check_spelling.py", "_utils.py"):
        _ = shutil.copyfile(
            REPOSITORY_ROOT / ".cortex" / "synapse" / "scripts" / "python" / name,
            scripts / name,
        )
    source = root / "src"
    source.mkdir(exist_ok=True)
    _ = (source / "subject.py").write_text("answer = 42\n", encoding="utf-8")
    return scripts / "check_spelling.py"


def configure_checker(root: Path, mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Select an explicit installed boundary executable, including argv spaces."""
    checker = root / "checker boundary.py"
    _ = checker.write_text(f"#!{sys.executable}\n" + CHECKER_SOURCE, encoding="utf-8")
    checker.chmod(0o644 if mode == "permission" else 0o755)
    if mode == "missing":
        command = [str(root / "missing-cspell")]
    elif mode == "permission":
        command = [str(checker), mode]
    else:
        command = [sys.executable, str(checker), mode]
    monkeypatch.setenv("SPELL_CHECKER_CMD", shlex.join(command))
    monkeypatch.setenv("SPELL_CHECKER_PREFLIGHT_TIMEOUT", "5")
    monkeypatch.setenv("SPELL_CHECKER_TIMEOUT", "0.5" if "timeout" in mode else "5")
    if mode == "preflight-timeout":
        monkeypatch.setenv("SPELL_CHECKER_PREFLIGHT_TIMEOUT", "0.5")
    monkeypatch.delenv("SRC_DIR", raising=False)
    monkeypatch.delenv("TESTS_DIR", raising=False)


def cleanup_checker(root: Path) -> None:
    """Remove only processes recorded by this test-owned checker executable."""
    for name in ("checker.pid", "checker-child.pid"):
        marker = root / name
        if not marker.exists():
            continue
        pid = int(marker.read_text(encoding="utf-8"))
        try:
            if name == "checker.pid":
                os.killpg(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
