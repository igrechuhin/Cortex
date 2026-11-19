"""Report observed Cortex phase and Swift test durations from existing logs."""

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

SWIFT = re.compile(r'\bTest (?!run with )(.+) (passed|failed) after (\d+(?:\.\d+)?) seconds?\.')
XCTEST = re.compile(r"Test Case '(.+)' (passed|failed) \((\d+(?:\.\d+)?) seconds?\)")


@dataclass
class TimingReport:
    phases: list[tuple[str, float | None]] = field(default_factory=list)
    tests: list[tuple[str, str, float]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def swift_tests(lines: Iterable[str]) -> list[tuple[str, str, float]]:
    """Extract only individual tests, excluding runs and suites."""
    return [
        (match[1], match[2], float(match[3]))
        for line in lines
        if (match := SWIFT.search(line) or XCTEST.search(line))
    ]


def phase_timings(lines: Iterable[str], report: TimingReport) -> None:
    """Measure between successful checkpoints within one controller log."""
    previous: float | None = None
    for number, line in enumerate(lines, 1):
        try:
            event = json.loads(line)
            observed = event["time"]
            data = event["data"]
            if event["kind"] == "blocked":
                report.warnings.append("Controller reported a blocker.")
            if event["kind"] != "mcp" or data["tool"] != "pipeline_handoff":
                continue
            args = data["args"]
            if data["result"]["isError"] or not isinstance(observed, (int, float)):
                continue
            if args["operation"] == "init":
                previous = observed
            if args["operation"] == "write":
                if args.get("data", {}).get("status") not in {"complete", "completed", "passed"}:
                    continue
                duration = observed - previous if previous is not None else None
                report.phases.append((str(args["phase"]), duration if duration is None or duration >= 0 else None))
                previous = observed
        except (ValueError, TypeError, KeyError, AttributeError):
            report.warnings.append(f"Ignored incomplete or invalid event line {number}.")


def render(report: TimingReport, top: int) -> str:
    """Keep checkpoint elapsed and individual test durations distinct."""
    output = ["Phase checkpoints (wall time since previous checkpoint; includes waits and overhead):"]
    counts: Counter[str] = Counter()
    for phase, elapsed in report.phases:
        counts[phase] += 1
        duration = "unknown" if elapsed is None else f"{elapsed:.3f}s"
        output.append(f"  {phase} #{counts[phase]}: {duration}")
    if not report.phases:
        output.append("  No timed phase checkpoints found.")
    repeated = [f"{phase} ×{count}" for phase, count in counts.items() if count > 1]
    output.append("Repeated phases: " + (", ".join(repeated) or "none observed"))
    output.append("Longest individual tests (parallel durations are not additive wall time):")
    for name, status, elapsed in sorted(report.tests, key=lambda row: -row[2])[:top]:
        output.append(f"  {elapsed:9.3f}s  {status}  {name}")
    if not report.tests:
        output.append("  No individual test durations found.")
    output.extend(f"Note: {message}" for message in report.warnings)
    output.append("Only recorded completions are shown. Absent phases or tests may be incomplete.")
    return "\n".join(output)


def main() -> None:
    """Read optional event and test streams without modifying their files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, help="Controller JSONL event log")
    parser.add_argument("--tests", type=Path, help="Swift Testing or XCTest text log")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    if not (args.events or args.tests) or args.top < 1:
        parser.error("provide --events or --tests, and a positive --top")
    report = TimingReport()
    try:
        if args.events:
            with args.events.open(encoding="utf-8", errors="replace") as stream:
                phase_timings(stream, report)
        if args.tests:
            with args.tests.open(encoding="utf-8", errors="replace") as stream:
                report.tests = swift_tests(stream)
    except OSError as exc:
        parser.error(str(exc))
    print(render(report, args.top))


if __name__ == "__main__":
    main()
