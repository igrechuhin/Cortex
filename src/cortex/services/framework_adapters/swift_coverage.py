"""Swift SPM code coverage helpers (llvm-cov / SwiftPM JSON exports).

Used by :class:`SwiftAdapter` after ``swift test --enable-code-coverage``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast


def parse_llvm_cov_report_line_coverage_fraction(report_text: str) -> float | None:
    """Parse overall line coverage fraction from ``llvm-cov report`` stdout.

    Uses the line ``TOTAL ...`` row and the last ``NN.NN%`` token on that row
    (line coverage column). Returns ``[0.0, 1.0]`` or ``None`` when missing.
    """
    last_frac: float | None = None
    for raw in report_text.splitlines():
        s = raw.strip()
        if not s.startswith("TOTAL"):
            continue
        row_frac: float | None = None
        for part in reversed(s.split()):
            if not part.endswith("%"):
                continue
            try:
                pct = float(part[:-1])
            except ValueError:
                continue
            if 0.0 <= pct <= 100.0:
                row_frac = pct / 100.0
                break
        if row_frac is not None:
            last_frac = row_frac
    return last_frac


def _should_skip_swift_cov_path(path_str: str) -> bool:
    norm = path_str.replace("\\", "/").lower()
    return ".build/" in norm or "/tests/" in norm or norm.endswith("/tests")


def _extract_json_files(payload: dict[str, object]) -> list[dict[str, object]]:
    data_obj = payload.get("data")
    if not isinstance(data_obj, list) or not data_obj:
        return []
    data_list = cast(list[object], data_obj)
    first: object = data_list[0]
    if not isinstance(first, dict):
        return []
    first_dict = cast(dict[str, object], first)
    files_obj = first_dict.get("files")
    if not isinstance(files_obj, list):
        return []
    files_list = cast(list[object], files_obj)
    result: list[dict[str, object]] = []
    for raw in files_list:
        if isinstance(raw, dict):
            result.append(cast(dict[str, object], raw))
    return result


def _extract_line_counts(entry: dict[str, object]) -> tuple[int, int] | None:
    summary_obj = entry.get("summary")
    if not isinstance(summary_obj, dict):
        return None
    summary = cast(dict[str, object], summary_obj)
    lines_obj = summary.get("lines")
    if not isinstance(lines_obj, dict):
        return None
    lines = cast(dict[str, object], lines_obj)
    count_obj = lines.get("count")
    covered_obj = lines.get("covered")
    if not isinstance(count_obj, int) or not isinstance(covered_obj, int):
        return None
    if count_obj < 0 or covered_obj < 0:
        return None
    return count_obj, min(covered_obj, count_obj)


def aggregate_spvm_codecov_json_line_fraction(
    payload: dict[str, object],
) -> float | None:
    """Aggregate line coverage from a SwiftPM / LLVM JSON codecov export.

    Sums ``lines.covered`` / ``lines.count`` across files, skipping ``Tests``
    and ``.build`` paths when possible.
    """
    total_lines = 0
    covered_lines = 0
    for entry in _extract_json_files(payload):
        name = entry.get("filename")
        if isinstance(name, str) and _should_skip_swift_cov_path(name):
            continue
        counts = _extract_line_counts(entry)
        if counts is None:
            continue
        count, covered = counts
        total_lines += count
        covered_lines += covered

    if total_lines <= 0:
        return None
    return covered_lines / total_lines


def read_swift_codecov_json_fraction(path: Path) -> float | None:
    """Load a SwiftPM codecov JSON file and return aggregate line fraction."""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        parsed: object = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return aggregate_spvm_codecov_json_line_fraction(cast(dict[str, object], parsed))


def default_profdata_path(bin_path: Path) -> Path:
    """Return canonical ``default.profdata`` path under a Swift bin directory."""
    return bin_path / "codecov" / "default.profdata"


def find_package_tests_executable(bin_path: Path) -> Path | None:
    """Locate the PackageTests binary under ``swift build --show-bin-path``."""
    matches = sorted(bin_path.glob("*PackageTests.xctest"))
    if not matches:
        return None
    xctest = matches[0]
    if sys.platform == "darwin":
        stem = xctest.stem
        exe = xctest / "Contents" / "MacOS" / stem
        if exe.is_file():
            return exe
        return None
    # Linux / other Unix: executable often mirrors macOS layout; fall back to stem path.
    exe = xctest / xctest.stem
    if exe.is_file():
        return exe
    nested = xctest / "Contents" / "MacOS" / xctest.stem
    if nested.is_file():
        return nested
    return None


def pick_codecov_json_file(codecov_dir: Path) -> Path | None:
    """Pick a JSON export under ``codecov/``, preferring the largest non-empty file."""
    candidates = sorted(codecov_dir.glob("*.json"))
    best: Path | None = None
    best_size = -1
    for p in candidates:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > best_size:
            best_size = size
            best = p
    return best
