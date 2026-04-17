"""Tests for ``swift_coverage.json`` loading."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.config.swift_coverage_config import (
    SwiftCoverageConfig,
    load_swift_coverage_config,
)


def test_load_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    cfg = load_swift_coverage_config(tmp_path)
    assert cfg.exclude_filename_regex_patterns == []


def test_load_reads_patterns(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".cortex" / "config"
    cfg_dir.mkdir(parents=True)
    payload = {"exclude_filename_regex_patterns": [r"\.pb\.swift$"]}
    _ = (cfg_dir / "swift_coverage.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    cfg = load_swift_coverage_config(tmp_path)
    assert cfg.exclude_filename_regex_patterns == [r"\.pb\.swift$"]


def test_load_strips_schema_key(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".cortex" / "config"
    cfg_dir.mkdir(parents=True)
    payload = {
        "$schema": "cortex-swift-coverage-config-v1",
        "exclude_filename_regex_patterns": [r"\.grpc\.swift$"],
    }
    _ = (cfg_dir / "swift_coverage.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    cfg = load_swift_coverage_config(tmp_path)
    assert cfg == SwiftCoverageConfig(
        exclude_filename_regex_patterns=[r"\.grpc\.swift$"]
    )


def test_load_invalid_json_returns_defaults(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".cortex" / "config"
    cfg_dir.mkdir(parents=True)
    _ = (cfg_dir / "swift_coverage.json").write_text("{", encoding="utf-8")
    cfg = load_swift_coverage_config(tmp_path)
    assert cfg.exclude_filename_regex_patterns == []
