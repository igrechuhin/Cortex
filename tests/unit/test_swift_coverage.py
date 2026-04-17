"""Unit tests for Swift coverage parsing helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest

from cortex.services.framework_adapters.swift_coverage import (
    aggregate_spvm_codecov_json_line_fraction,
    build_swift_llvm_cov_ignore_regex,
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
