"""Swift SPM code coverage helpers (llvm-cov / SwiftPM JSON exports).

Used by :class:`SwiftAdapter` after ``swift test --enable-code-coverage``.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from .base import CoverageGap

logger = logging.getLogger(__name__)

# llvm-cov ``-ignore-filename-regex``: built-in skip for build dir + test bundles.
_DEFAULT_LLVM_COV_IGNORE_FRAGMENT = r"(?:\.build|Tests)"


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


def should_skip_swift_cov_path(
    path_str: str,
    extra_filename_regexes: Sequence[re.Pattern[str]] | None = None,
) -> bool:
    """Return True when a path should not contribute to line-coverage totals."""
    norm = path_str.replace("\\", "/").lower()
    if ".build/" in norm or "/tests/" in norm or norm.endswith("/tests"):
        return True
    unified = path_str.replace("\\", "/")
    if extra_filename_regexes:
        for rx in extra_filename_regexes:
            if rx.search(unified):
                return True
    return False


def compile_swift_coverage_exclude_regexes(
    patterns: list[str],
) -> list[re.Pattern[str]]:
    """Compile user patterns from config; drop invalid entries with a warning."""
    out: list[re.Pattern[str]] = []
    for raw in patterns:
        s = raw.strip()
        if not s:
            continue
        try:
            out.append(re.compile(s, re.IGNORECASE))
        except re.error as exc:
            logger.warning(
                "Invalid swift coverage exclude_filename_regex_patterns entry %r: %s",
                raw,
                exc,
            )
    return out


def build_swift_llvm_cov_ignore_regex(extra_patterns: list[str]) -> str:
    """Build a single alternation regex for ``llvm-cov -ignore-filename-regex``."""
    parts: list[str] = [_DEFAULT_LLVM_COV_IGNORE_FRAGMENT]
    for p in extra_patterns:
        s = p.strip()
        if not s:
            continue
        parts.append(f"(?:{s})")
    return "|".join(parts)


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


class FileCoverageEntry:
    """Per-file coverage data extracted from a codecov JSON export."""

    __slots__ = ("filename", "lines_total", "lines_covered")

    def __init__(self, filename: str, lines_total: int, lines_covered: int) -> None:
        self.filename = filename
        self.lines_total = lines_total
        self.lines_covered = lines_covered

    @property
    def lines_uncovered(self) -> int:
        return self.lines_total - self.lines_covered

    @property
    def fraction(self) -> float:
        if self.lines_total <= 0:
            return 1.0
        return self.lines_covered / self.lines_total


def extract_per_file_coverage(
    payload: dict[str, object],
    extra_filename_regexes: Sequence[re.Pattern[str]] | None = None,
) -> list[FileCoverageEntry]:
    """Extract per-file coverage entries from a SwiftPM / LLVM JSON codecov export.

    Skips ``Tests`` and ``.build`` paths. Returns all remaining file entries.
    """
    entries: list[FileCoverageEntry] = []
    for entry in _extract_json_files(payload):
        name = entry.get("filename")
        if not isinstance(name, str):
            continue
        if should_skip_swift_cov_path(name, extra_filename_regexes):
            continue
        counts = _extract_line_counts(entry)
        if counts is None:
            continue
        count, covered = counts
        entries.append(FileCoverageEntry(name, count, covered))
    return entries


def aggregate_spvm_codecov_json_line_fraction(
    payload: dict[str, object],
    extra_filename_regexes: Sequence[re.Pattern[str]] | None = None,
) -> float | None:
    """Aggregate line coverage from a SwiftPM / LLVM JSON codecov export.

    Sums ``lines.covered`` / ``lines.count`` across files, skipping ``Tests``
    and ``.build`` paths when possible.
    """
    entries = extract_per_file_coverage(payload, extra_filename_regexes)
    total_lines = sum(e.lines_total for e in entries)
    covered_lines = sum(e.lines_covered for e in entries)

    if total_lines <= 0:
        return None
    return covered_lines / total_lines


def read_swift_codecov_json_fraction(
    path: Path,
    extra_filename_regexes: Sequence[re.Pattern[str]] | None = None,
) -> float | None:
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
    return aggregate_spvm_codecov_json_line_fraction(
        cast(dict[str, object], parsed),
        extra_filename_regexes,
    )


def read_swift_codecov_json_per_file(
    path: Path,
    extra_filename_regexes: Sequence[re.Pattern[str]] | None = None,
) -> list[FileCoverageEntry]:
    """Load a SwiftPM codecov JSON file and return per-file coverage entries."""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        parsed: object = json.loads(raw_text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    return extract_per_file_coverage(
        cast(dict[str, object], parsed),
        extra_filename_regexes,
    )


def build_coverage_gaps(
    per_file: list[FileCoverageEntry],
    coverage: float | None,
    threshold: float,
    max_entries: int = 10,
) -> list[CoverageGap]:
    """Build top coverage gaps sorted by uncovered lines descending.

    Only populated when coverage is below *threshold* and *per_file* data is
    available.
    """
    if not per_file or coverage is None or coverage >= threshold:
        return []
    ranked = sorted(per_file, key=lambda e: e.lines_uncovered, reverse=True)
    return [
        CoverageGap(
            file=e.filename,
            coverage=round(e.fraction, 4),
            lines_total=e.lines_total,
            lines_uncovered=e.lines_uncovered,
        )
        for e in ranked[:max_entries]
        if e.lines_uncovered > 0
    ]


def default_profdata_path(bin_path: Path) -> Path:
    """Return canonical ``default.profdata`` path under a Swift bin directory."""
    return bin_path / "codecov" / "default.profdata"


def _build_profdata_merge_cmd(
    profraw_files: list[Path],
    profdata: Path,
) -> list[str]:
    """Build argv for ``llvm-profdata merge`` (macOS uses ``xcrun``)."""
    tool = (
        ["xcrun", "llvm-profdata", "merge"]
        if sys.platform == "darwin"
        else ["llvm-profdata", "merge"]
    )
    return [*tool, *[str(p) for p in profraw_files], "-o", str(profdata)]


def merge_profraw_to_profdata(
    bin_path: Path,
    timeout: int | None = None,
) -> bool:
    """Merge ``*.profraw`` files in ``codecov/`` into ``default.profdata``.

    SwiftPM skips the auto-merge for projects mixing XCTest and Swift Testing.
    Returns True when ``default.profdata`` exists after the call.
    """
    profdata = default_profdata_path(bin_path)
    if profdata.is_file():
        return True
    profraw_files = sorted((bin_path / "codecov").glob("*.profraw"))
    if not profraw_files:
        return False
    cmd = _build_profdata_merge_cmd(profraw_files, profdata)
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except Exception:
        logger.debug("llvm-profdata merge failed", exc_info=True)
        return False
    if result.returncode != 0:
        logger.debug(
            "llvm-profdata merge exited %d: %s",
            result.returncode,
            result.stderr.decode("utf-8", errors="replace") if result.stderr else "",
        )
        return False
    return profdata.is_file()


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


def _build_llvm_cov_export_command(
    binary: Path,
    profdata: Path,
    extra_filename_regexes: Sequence[re.Pattern[str]] | None = None,
) -> list[str]:
    """Build llvm-cov export argv with optional ignore-regex extensions."""
    base = ["xcrun", "llvm-cov"] if sys.platform == "darwin" else ["llvm-cov"]
    ignore = _DEFAULT_LLVM_COV_IGNORE_FRAGMENT
    if extra_filename_regexes:
        parts = [ignore] + [p.pattern for p in extra_filename_regexes]
        ignore = "|".join(f"(?:{p})" for p in parts)
    return [
        *base,
        "export",
        str(binary),
        f"-instr-profile={profdata}",
        f"--ignore-filename-regex={ignore}",
        "--skip-expansions",
        "--skip-branches",
    ]


def _run_llvm_cov_export_command(
    cmd: list[str], timeout: int | None
) -> dict[str, object] | None:
    """Run llvm-cov export and parse JSON response into a mapping."""
    try:
        raw = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            timeout=timeout,
        )
    except Exception:
        return None
    if raw.returncode != 0:
        return None
    stdout = raw.stdout.decode("utf-8", errors="replace") if raw.stdout else ""
    try:
        parsed: object = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return cast(dict[str, object], parsed)


def llvm_cov_export_per_file(
    binary: Path,
    profdata: Path,
    extra_filename_regexes: Sequence[re.Pattern[str]] | None = None,
    timeout: int | None = None,
) -> list[FileCoverageEntry]:
    """Generate per-file coverage via ``llvm-cov export`` (JSON) when SwiftPM JSON is absent.

    Falls back to this when ``pick_codecov_json_file`` returns ``None``.  The
    ``llvm-cov export`` subcommand produces the same JSON schema as SwiftPM's
    bundled export, so ``extract_per_file_coverage`` can parse it directly.
    Returns an empty list on any subprocess or parse error.
    """
    cmd = _build_llvm_cov_export_command(binary, profdata, extra_filename_regexes)
    parsed = _run_llvm_cov_export_command(cmd, timeout)
    if parsed is None:
        return []
    return extract_per_file_coverage(parsed, extra_filename_regexes)
