"""Unit tests for Swift coverage parsing helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest

from cortex.services.framework_adapters.swift_coverage import (
    FileCoverageEntry,
    aggregate_spvm_codecov_json_line_fraction,
    build_coverage_gaps,
    build_swift_llvm_cov_ignore_regex,
    build_uncovered_files,
    compile_swift_coverage_exclude_regexes,
    parse_llvm_cov_report_line_coverage_fraction,
    read_swift_codecov_json_fraction,
    should_skip_swift_cov_path,
)


class TestParseLlvmCovReport:
    """Tests for ``parse_llvm_cov_report_line_coverage_fraction``."""

    def test_parses_total_row_last_percent(self) -> None:
        report = (
            "Filename                      Lines    Missed   Cover\n"
            "foo.swift                        10         2  80.00%\n"
            "TOTAL                            10         2  80.00%\n"
        )
        assert parse_llvm_cov_report_line_coverage_fraction(report) == pytest.approx(  # type: ignore[unknown-member-type]
            0.80
        )

    def test_returns_none_without_total(self) -> None:
        assert parse_llvm_cov_report_line_coverage_fraction("no totals here") is None

    def test_uses_last_total_row(self) -> None:
        report = "TOTAL ... 50.00%\nOTHER\nTOTAL ... 75.00%\n"
        assert parse_llvm_cov_report_line_coverage_fraction(report) == pytest.approx(  # type: ignore[unknown-member-type]
            0.75
        )


class TestCodecovJson:
    """Tests for SwiftPM / LLVM JSON codecov aggregation."""

    def test_aggregate_skips_tests_paths(self) -> None:
        payload = {
            "data": [
                {
                    "files": [
                        {
                            "filename": "/proj/Sources/Core.swift",
                            "summary": {
                                "lines": {"count": 100, "covered": 90},
                            },
                        },
                        {
                            "filename": "/proj/Tests/CoreTests.swift",
                            "summary": {
                                "lines": {"count": 50, "covered": 50},
                            },
                        },
                    ],
                },
            ],
        }
        frac = aggregate_spvm_codecov_json_line_fraction(
            cast(dict[str, object], payload)
        )
        assert frac == pytest.approx(0.90)  # type: ignore[unknown-member-type]

    def test_aggregate_skips_pb_swift_when_extra_regex_set(self) -> None:
        """Config-driven regex excludes generated protobuf files from totals."""
        extra = [re.compile(r"\.pb\.swift$", re.IGNORECASE)]
        payload = {
            "data": [
                {
                    "files": [
                        {
                            "filename": "/proj/Sources/App.swift",
                            "summary": {"lines": {"count": 100, "covered": 90}},
                        },
                        {
                            "filename": "/proj/Sources/Generated/x.pb.swift",
                            "summary": {"lines": {"count": 100, "covered": 0}},
                        },
                    ],
                },
            ],
        }
        frac = aggregate_spvm_codecov_json_line_fraction(
            cast(dict[str, object], payload),
            extra,
        )
        assert frac == pytest.approx(0.90)  # type: ignore[unknown-member-type]

    def test_read_swift_codecov_json_fraction_roundtrip(self, tmp_path: Path) -> None:
        payload = {
            "data": [
                {
                    "files": [
                        {
                            "filename": "/src/App.swift",
                            "summary": {"lines": {"count": 10, "covered": 8}},
                        },
                    ],
                },
            ],
        }
        p = tmp_path / "cov.json"
        _ = p.write_text(json.dumps(payload), encoding="utf-8")
        assert read_swift_codecov_json_fraction(p) == pytest.approx(0.8)  # type: ignore[unknown-member-type]

    def test_malformed_json_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        _ = p.write_text("{not json", encoding="utf-8")
        assert read_swift_codecov_json_fraction(p) is None


class TestLlvmCovIgnoreRegex:
    """Tests for ``llvm-cov -ignore-filename-regex`` builder."""

    def test_build_includes_default_and_extras(self) -> None:
        built = build_swift_llvm_cov_ignore_regex([r"\.pb\.swift$"])
        assert ".build" in built or r"\.build" in built
        assert "pb" in built


class TestCompileExcludePatterns:
    """Tests for regex compilation from config strings."""

    def test_invalid_pattern_is_dropped(self) -> None:
        out = compile_swift_coverage_exclude_regexes([r"(unclosed", r"\.ok\.swift$"])
        assert len(out) == 1


class TestShouldSkipSwiftCovPath:
    """Tests for path skip helper."""

    def test_extra_regex_matches_pb_path(self) -> None:
        extra = compile_swift_coverage_exclude_regexes([r"\.pb\.swift$"])
        assert should_skip_swift_cov_path(r"C:\proj\Sources\Gen\a.pb.swift", extra)
        assert not should_skip_swift_cov_path("/proj/Sources/App.swift", extra)


def _entry(filename: str, total: int, covered: int) -> FileCoverageEntry:
    return FileCoverageEntry(
        filename=filename, lines_total=total, lines_covered=covered
    )


class TestBuildCoverageGaps:
    """Tests for ``build_coverage_gaps`` two-tier ranking."""

    def test_returns_empty_when_coverage_meets_threshold(self) -> None:
        entries = [_entry("A.swift", 100, 80)]
        assert build_coverage_gaps(entries, 0.90, 0.90) == []

    def test_returns_empty_when_coverage_is_none(self) -> None:
        entries = [_entry("A.swift", 100, 80)]
        assert build_coverage_gaps(entries, None, 0.90) == []

    def test_zero_coverage_files_appear_before_partial(self) -> None:
        partial = _entry("Big.swift", 500, 250)  # 50% covered, 250 uncovered
        zero_small = _entry("Small.swift", 30, 0)  # 0% covered, 30 lines
        zero_large = _entry("Medium.swift", 80, 0)  # 0% covered, 80 lines
        gaps = build_coverage_gaps([partial, zero_small, zero_large], 0.50, 0.90)
        files = [g.file for g in gaps]
        # Both zero-coverage files must precede the partial file
        assert files.index("Small.swift") < files.index("Big.swift")
        assert files.index("Medium.swift") < files.index("Big.swift")

    def test_zero_coverage_files_sorted_by_lines_total_ascending(self) -> None:
        entries = [
            _entry("Large.swift", 200, 0),
            _entry("Tiny.swift", 10, 0),
            _entry("Mid.swift", 50, 0),
        ]
        gaps = build_coverage_gaps(entries, 0.0, 0.90)
        files = [g.file for g in gaps]
        assert files == ["Tiny.swift", "Mid.swift", "Large.swift"]

    def test_partial_files_sorted_by_uncovered_lines_descending(self) -> None:
        entries = [
            _entry("Few.swift", 100, 90),  # 10 uncovered
            _entry("Many.swift", 100, 20),  # 80 uncovered
            _entry("Some.swift", 100, 50),  # 50 uncovered
        ]
        gaps = build_coverage_gaps(entries, 0.50, 0.90)
        files = [g.file for g in gaps]
        assert files == ["Many.swift", "Some.swift", "Few.swift"]

    def test_max_entries_respected(self) -> None:
        entries = [_entry(f"F{i}.swift", 10, 0) for i in range(20)]
        gaps = build_coverage_gaps(entries, 0.0, 0.90, max_entries=5)
        assert len(gaps) == 5

    def test_gap_fields_populated_correctly(self) -> None:
        entry = _entry("Foo.swift", 100, 40)
        gaps = build_coverage_gaps([entry], 0.40, 0.90)
        assert len(gaps) == 1
        g = gaps[0]
        assert g.file == "Foo.swift"
        assert g.coverage == 0.4
        assert g.lines_total == 100
        assert g.lines_uncovered == 60


class TestBuildUncoveredFiles:
    """Tests for ``build_uncovered_files`` — always-populated zero-coverage list."""

    def test_returns_only_zero_coverage_files(self) -> None:
        entries = [
            _entry("Full.swift", 100, 100),
            _entry("Partial.swift", 100, 50),
            _entry("Zero.swift", 40, 0),
        ]
        result = build_uncovered_files(entries)
        assert len(result) == 1
        assert result[0].file == "Zero.swift"

    def test_sorted_by_lines_total_ascending(self) -> None:
        entries = [
            _entry("Big.swift", 200, 0),
            _entry("Tiny.swift", 10, 0),
            _entry("Mid.swift", 50, 0),
        ]
        result = build_uncovered_files(entries)
        assert [g.file for g in result] == ["Tiny.swift", "Mid.swift", "Big.swift"]

    def test_populated_regardless_of_threshold(self) -> None:
        # Even when coverage already meets threshold, uncovered_files is not empty
        entries = [
            _entry("Almost.swift", 100, 95),
            _entry("Zero.swift", 10, 0),
        ]
        # Coverage = (95) / (110) ≈ 0.864 — below threshold, but we verify the
        # function doesn't take threshold as an argument at all
        result = build_uncovered_files(entries)
        assert len(result) == 1
        assert result[0].file == "Zero.swift"

    def test_excludes_files_with_zero_total_lines(self) -> None:
        entries = [
            _entry("Empty.swift", 0, 0),
            _entry("Real.swift", 30, 0),
        ]
        result = build_uncovered_files(entries)
        assert len(result) == 1
        assert result[0].file == "Real.swift"

    def test_returns_empty_when_all_files_have_coverage(self) -> None:
        entries = [_entry("A.swift", 100, 80), _entry("B.swift", 50, 50)]
        assert build_uncovered_files(entries) == []

    def test_gap_fields_populated_correctly(self) -> None:
        entry = _entry("Zero.swift", 45, 0)
        result = build_uncovered_files([entry])
        assert len(result) == 1
        g = result[0]
        assert g.file == "Zero.swift"
        assert g.coverage == 0.0
        assert g.lines_total == 45
        assert g.lines_uncovered == 45

    def test_no_cap_returns_all_zero_coverage_files(self) -> None:
        entries = [_entry(f"F{i}.swift", i + 1, 0) for i in range(50)]
        result = build_uncovered_files(entries)
        assert len(result) == 50
