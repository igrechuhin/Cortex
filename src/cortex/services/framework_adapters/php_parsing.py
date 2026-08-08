"""PHP test-report parsing.

PHPUnit/Pest emit machine-readable reports (JUnit XML for results, Clover XML
for coverage). Parse those instead of scraping console output.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from .base import CoverageGap


class JUnitCounts:
    """Passed/failed/skipped counts plus failure messages from a JUnit report."""

    def __init__(
        self, passed: int, failed: int, skipped: int, failures: list[str]
    ) -> None:
        self.passed = passed
        self.failed = failed
        self.skipped = skipped
        self.failures = failures


def parse_junit(report: Path) -> JUnitCounts | None:
    """Parse a PHPUnit/Pest JUnit XML report.

    Counts ``<testcase>`` elements directly rather than trusting suite-level
    attributes, which differ across PHPUnit versions.

    Args:
        report: Path to the JUnit XML file.

    Returns:
        JUnitCounts, or None if the file is missing or malformed.
    """
    try:
        root = ElementTree.parse(report).getroot()
    except (OSError, ElementTree.ParseError):
        return None

    passed = failed = skipped = 0
    failures: list[str] = []
    for case in root.iter("testcase"):
        bad = [c for c in case if c.tag in ("failure", "error")]
        if bad:
            failed += 1
            failures.append(_failure_message(case, bad[0]))
        elif any(c.tag == "skipped" for c in case):
            skipped += 1
        else:
            passed += 1
    return JUnitCounts(passed, failed, skipped, failures)


def _failure_message(case: ElementTree.Element, node: ElementTree.Element) -> str:
    """Build a one-line ``Class::method: message`` string for a failed case."""
    name = case.get("name", "?")
    cls = case.get("class") or case.get("classname")
    label = f"{cls}::{name}" if cls else name
    text = (node.get("message") or node.text or "").strip().splitlines()
    return f"{label}: {text[0]}" if text else label


def parse_clover(
    report: Path, project_root: Path
) -> tuple[float | None, list[CoverageGap]]:
    """Parse a Clover XML coverage report.

    Args:
        report: Path to the Clover XML file.
        project_root: Root used to make file paths relative.

    Returns:
        (overall line coverage fraction or None, per-file gaps).
    """
    try:
        root = ElementTree.parse(report).getroot()
    except (OSError, ElementTree.ParseError):
        return None, []

    gaps = [g for g in (_file_gap(f, project_root) for f in root.iter("file")) if g]
    total = sum(g.lines_total for g in gaps)
    covered = total - sum(g.lines_uncovered for g in gaps)
    overall = (covered / total) if total > 0 else None
    return overall, gaps


def _file_gap(node: ElementTree.Element, project_root: Path) -> CoverageGap | None:
    """Build a CoverageGap from a Clover ``<file>`` element."""
    metrics = node.find("metrics")
    name = node.get("name")
    if metrics is None or not name:
        return None
    total = _int_attr(metrics, "statements")
    covered = _int_attr(metrics, "coveredstatements")
    if total <= 0:
        return None
    return CoverageGap(
        file=_relative(name, project_root),
        coverage=min(covered / total, 1.0),
        lines_total=total,
        lines_uncovered=max(total - covered, 0),
    )


def _int_attr(node: ElementTree.Element, key: str) -> int:
    """Read an integer attribute, defaulting to 0 when absent or malformed."""
    try:
        return int(node.get(key, "0"))
    except ValueError:
        return 0


def _relative(name: str, project_root: Path) -> str:
    """Make a Clover absolute file path relative to the project root."""
    try:
        return str(Path(name).relative_to(project_root))
    except ValueError:
        return name
