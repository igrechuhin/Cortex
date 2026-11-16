#!/usr/bin/env python3
"""Require a nonempty pytest JUnit report with every test successfully executed."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def check_report(path: Path, required_case: str | None = None) -> int:
    """Return the executed test count, rejecting incomplete or unsuccessful reports."""
    root = ET.parse(path).getroot()
    if root.tag not in {"testsuites", "testsuite"}:
        raise ValueError("Expected a pytest JUnit testsuites or testsuite root")
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    if not suites:
        raise ValueError("JUnit report has no test suites")
    total = 0
    for suite in suites:
        count = int(suite.attrib["tests"])
        cases = suite.findall("testcase")
        if count <= 0 or count != len(cases):
            raise ValueError("JUnit suite is empty or its test count is inconsistent")
        if any(
            int(suite.attrib[key]) != 0 for key in ("failures", "errors", "skipped")
        ):
            raise ValueError("JUnit suite reports failed, errored, or skipped tests")
        total += count
    for tag in ("failure", "error", "skipped"):
        if next(root.iter(tag), None) is not None:
            raise ValueError(f"JUnit report contains a {tag} result")
    if required_case is not None:
        require_unique_case(root, required_case)
    return total


def require_unique_case(root: ET.Element, name: str) -> None:
    """Reject a report that omitted or duplicated the specifically required test."""
    count = sum(case.get("name") == name for case in root.iter("testcase"))
    if count != 1:
        raise ValueError(f"Required test case {name!r} occurred {count} times")


def main() -> int:
    """Validate one report and expose a fail-closed exit status to CI."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("report", type=Path)
    _ = parser.add_argument("--require-case", help="Require one successful named test")
    args = parser.parse_args()
    try:
        count = check_report(args.report, args.require_case)
    except (OSError, ET.ParseError, KeyError, ValueError) as exc:
        print(f"JUnit acceptance failed: {exc}", file=sys.stderr)
        return 1
    print(f"JUnit acceptance passed: {count} tests executed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
