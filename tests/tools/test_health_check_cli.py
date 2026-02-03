"""Tests for health-check CLI (python -m cortex.health_check)."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


def _run_cli(
    args: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the health-check CLI with given args via python -m cortex.health_check."""
    cmd = [sys.executable, "-m", "cortex.health_check"] + args
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

    def test_parse_args_defaults(self) -> None:
        """parse_args with default argv returns expected defaults (in-process coverage)."""
        from cortex.health_check import __main__ as cli_main

        with patch.object(sys, "argv", ["cortex.health_check"]):
            args = cli_main.parse_args()
        assert args.type == "all"
        assert args.threshold == 0.75
        assert args.format == "json"
        assert args.output is None
        assert args.no_dependencies is False
        assert args.no_quality_validation is False

    def test_parse_args_custom(self) -> None:
        """parse_args with custom argv parses correctly (in-process coverage)."""
        from cortex.health_check import __main__ as cli_main

        with patch.object(
            sys,
            "argv",
            [
                "cortex.health_check",
                "--type",
                "rules",
                "--threshold",
                "0.8",
                "--format",
                "markdown",
                "--no-dependencies",
            ],
        ):
            args = cli_main.parse_args()
        assert args.type == "rules"
        assert args.threshold == 0.8
        assert args.format == "markdown"
        assert args.no_dependencies is True

    def test_main_returns_zero_with_mocked_analysis(self) -> None:
        """main() runs and returns 0 when analysis is mocked (in-process coverage)."""
        from cortex.health_check import __main__ as cli_main

        fake_result = '{"status": "success", "analysis_type": "prompts"}'

        def _fake_asyncio_run(coro: object) -> str:
            return fake_result

        with (
            patch.object(sys, "argv", ["cortex.health_check", "--type", "prompts"]),
            patch("asyncio.run", side_effect=_fake_asyncio_run),
        ):
            exit_code = cli_main.main()
        assert exit_code == 0
