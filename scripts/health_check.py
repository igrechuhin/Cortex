#!/usr/bin/env python3
"""
Health-check CLI: run prompts/rules/tools analysis and emit JSON or Markdown report.

Usage:
    python scripts/health_check.py --type all --threshold 0.75 --output report.json
    uv run python scripts/health_check.py --type prompts --format markdown
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root so cortex package is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from cortex.health_check.models import HealthCheckReport
from cortex.health_check.report_generator import ReportGenerator
from cortex.tools.health_check_operations import run_health_check_analysis


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run health-check analysis on prompts, rules, and/or tools."
    )
    parser.add_argument(
        "--type",
        choices=["prompts", "rules", "tools", "all"],
        default="all",
        help="Analysis type (default: all)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Similarity threshold 0.0-1.0 (default: 0.75)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Report format (default: json)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root (default: current directory)",
    )
    parser.add_argument(
        "--no-dependencies",
        action="store_true",
        help="Skip dependency mapping",
    )
    parser.add_argument(
        "--no-quality-validation",
        action="store_true",
        help="Skip quality validation",
    )
    return parser.parse_args()


async def _run_analysis(args: argparse.Namespace) -> str:
    """Run health-check analysis and return JSON string."""
    project_root = args.project_root or Path.cwd()
    return await run_health_check_analysis(
        analysis_type=args.type,
        similarity_threshold=args.threshold,
        include_dependencies=not args.no_dependencies,
        validate_quality=not args.no_quality_validation,
        project_root=project_root,
    )


def _emit_report(json_str: str, fmt: str, output_path: Path | None) -> None:
    """Emit report as JSON or Markdown to file or stdout."""
    if fmt == "json":
        content = json_str
    else:
        report: HealthCheckReport = json.loads(json_str)
        content = ReportGenerator().generate_markdown_report(report, None)

    if output_path:
        output_path.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


def main() -> int:
    """Entry point: run analysis and emit report."""
    args = _parse_args()
    if not (0.0 <= args.threshold <= 1.0):
        print("error: --threshold must be between 0.0 and 1.0", file=sys.stderr)
        return 1
    try:
        json_str = asyncio.run(_run_analysis(args))
        _emit_report(json_str, args.format, args.output)
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
