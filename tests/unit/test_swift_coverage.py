"""Unit tests for Swift coverage parsing helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.services.framework_adapters.swift_coverage import (
    aggregate_spvm_codecov_json_line_fraction,
    parse_llvm_cov_report_line_coverage_fraction,
    read_swift_codecov_json_fraction,
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
