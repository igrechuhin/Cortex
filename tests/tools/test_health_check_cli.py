"""Tests for health-check CLI (scripts/health_check.py)."""

import subprocess
import sys
from pathlib import Path


def _run_cli(
    args: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the health-check CLI with given args."""
    script = (
        Path(__file__).resolve().parent.parent.parent / "scripts" / "health_check.py"
    )
    cmd = [sys.executable, str(script)] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or Path.cwd(),
        timeout=60,
    )


class TestHealthCheckCli:
    """Tests for health-check CLI."""

    def test_cli_help_exits_zero(self) -> None:
        """--help exits with code 0."""
        result = _run_cli(["--help"])
        assert result.returncode == 0
        assert "health-check" in result.stdout or "type" in result.stdout

    def test_cli_invalid_threshold_exits_one(self) -> None:
        """Invalid --threshold (e.g. 1.5) exits with code 1."""
        result = _run_cli(["--type", "prompts", "--threshold", "1.5"])
        assert result.returncode == 1
        assert "threshold" in result.stderr.lower() or "error" in result.stderr.lower()
