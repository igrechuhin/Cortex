"""Tests for ``swift_test.json`` loading."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.config.swift_test_config import SwiftTestConfig, load_swift_test_config


def test_load_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    cfg = load_swift_test_config(tmp_path)
    assert cfg.skip_testing == []


def test_load_reads_identifiers(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".cortex" / "config"
    cfg_dir.mkdir(parents=True)
    payload = {"skip_testing": ["SampleTests/LiveNetworkIntegrationTests"]}
    _ = (cfg_dir / "swift_test.json").write_text(json.dumps(payload), encoding="utf-8")
    cfg = load_swift_test_config(tmp_path)
    assert cfg.skip_testing == ["SampleTests/LiveNetworkIntegrationTests"]


def test_load_strips_schema_key(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".cortex" / "config"
    cfg_dir.mkdir(parents=True)
    payload = {
        "$schema": "cortex-swift-test-config-v1",
        "skip_testing": ["SampleTests/LiveNetworkIntegrationTests"],
    }
    _ = (cfg_dir / "swift_test.json").write_text(json.dumps(payload), encoding="utf-8")
    cfg = load_swift_test_config(tmp_path)
    assert cfg == SwiftTestConfig(
        skip_testing=["SampleTests/LiveNetworkIntegrationTests"]
    )


def test_load_invalid_json_returns_defaults(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".cortex" / "config"
    cfg_dir.mkdir(parents=True)
    _ = (cfg_dir / "swift_test.json").write_text("{", encoding="utf-8")
    cfg = load_swift_test_config(tmp_path)
    assert cfg.skip_testing == []


def test_load_non_object_root_returns_defaults(tmp_path: Path) -> None:
    cfg_dir = tmp_path / ".cortex" / "config"
    cfg_dir.mkdir(parents=True)
    _ = (cfg_dir / "swift_test.json").write_text("[]", encoding="utf-8")
    cfg = load_swift_test_config(tmp_path)
    assert cfg.skip_testing == []
