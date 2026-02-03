"""CLI entry point for health-check analysis (python -m cortex.health_check)."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from cortex.health_check.report_generator import ReportGenerator
from cortex.tools.health_check_operations import (
    get_project_root,
    run_health_check_analysis,
)


def _add_analysis_arguments(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "--type",
        choices=("prompts", "rules", "tools", "all"),
        default="all",
        help="What to analyze (default: all)",
    )
    _ = parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Similarity threshold 0.0–1.0 (default: 0.75)",
    )
    _ = parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root directory (default: current dir)",
    )
    _ = parser.add_argument(
        "--no-dependencies",
        action="store_true",
        help="Skip dependency mapping",
    )
    _ = parser.add_argument(
        "--no-quality-validation",
        action="store_true",
        help="Skip quality validation",
    )


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: stdout)",
    )
    _ = parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format (default: json)",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cortex.health_check",
        description="Analyze prompts, rules, and MCP tools for merge/optimization opportunities.",
    )
    _add_analysis_arguments(parser)
    _add_output_arguments(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not (0.0 <= args.threshold <= 1.0):
        print("error: --threshold must be between 0.0 and 1.0", file=sys.stderr)
        return 1
    project_root = get_project_root(
        str(args.project_root) if args.project_root is not None else None
    )
    json_str = asyncio.run(
        run_health_check_analysis(
            analysis_type=args.type,
            similarity_threshold=args.threshold,
            include_dependencies=not args.no_dependencies,
            validate_quality=not args.no_quality_validation,
            project_root=project_root,
        )
    )
    if args.format == "markdown":
        report = json.loads(json_str)
        content = ReportGenerator().generate_markdown_report(report)
    else:
        content = json_str
    if args.output is not None:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
