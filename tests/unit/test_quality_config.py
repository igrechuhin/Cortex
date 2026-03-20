"""Tests for structured quality configuration loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cortex.config.quality_config import QualityConfig, load_quality_config


class TestQualityConfigModel:
    """QualityConfig Pydantic model validation."""

    def test_defaults(self) -> None:
        cfg = QualityConfig()
        assert cfg.coverage_threshold == 90
        assert cfg.max_file_lines == 400
        assert cfg.max_function_lines == 30
        assert cfg.test_timeout_seconds == 120
        assert cfg.todo_patterns == ["TODO", "FIXME", "HACK", "XXX"]
        assert cfg.markdown_line_length == 120

    def test_custom_values(self) -> None:
        cfg = QualityConfig(
            coverage_threshold=80,
            max_file_lines=500,
            max_function_lines=50,
            test_timeout_seconds=60,
            todo_patterns=["TODO"],
            exclude_from_todo_scan=["vendor/"],
            markdown_line_length=100,
        )
        assert cfg.coverage_threshold == 80
        assert cfg.max_file_lines == 500
        assert cfg.exclude_from_todo_scan == ["vendor/"]

    def test_coverage_threshold_fraction(self) -> None:
        cfg = QualityConfig(coverage_threshold=85)
        assert cfg.coverage_threshold_fraction == pytest.approx(0.85)  # type: ignore[unknown-member-type]

    def test_coverage_threshold_min(self) -> None:
        cfg = QualityConfig(coverage_threshold=0)
        assert cfg.coverage_threshold == 0

    def test_coverage_threshold_max(self) -> None:
        cfg = QualityConfig(coverage_threshold=100)
        assert cfg.coverage_threshold == 100

    def test_coverage_threshold_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            _ = QualityConfig(coverage_threshold=101)

    def test_coverage_threshold_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            _ = QualityConfig(coverage_threshold=-1)

    def test_max_file_lines_too_low_raises(self) -> None:
        with pytest.raises(ValidationError):
            _ = QualityConfig(max_file_lines=50)

    def test_max_function_lines_too_low_raises(self) -> None:
        with pytest.raises(ValidationError):
            _ = QualityConfig(max_function_lines=5)

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _ = QualityConfig(unknown_field="value")  # type: ignore[call-arg]


class TestLoadQualityConfig:
    """load_quality_config reads from .cortex/config/quality.json."""

    def test_load_from_file(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".cortex" / "config"
        config_dir.mkdir(parents=True)
        data = {"coverage_threshold": 85, "max_file_lines": 300}
        _ = (config_dir / "quality.json").write_text(json.dumps(data))

        cfg = load_quality_config(tmp_path)
        assert cfg.coverage_threshold == 85
        assert cfg.max_file_lines == 300
        # Other fields get defaults
        assert cfg.max_function_lines == 30

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_quality_config(tmp_path)
        assert cfg.coverage_threshold == 90
        assert cfg.max_file_lines == 400

    def test_invalid_json_returns_defaults(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".cortex" / "config"
        config_dir.mkdir(parents=True)
        _ = (config_dir / "quality.json").write_text("{not valid json")

        cfg = load_quality_config(tmp_path)
        assert cfg.coverage_threshold == 90

    def test_invalid_values_returns_defaults(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".cortex" / "config"
        config_dir.mkdir(parents=True)
        data = {"coverage_threshold": 200}  # Out of range
        _ = (config_dir / "quality.json").write_text(json.dumps(data))

        cfg = load_quality_config(tmp_path)
        assert cfg.coverage_threshold == 90  # Fallback to defaults

    def test_schema_key_stripped(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".cortex" / "config"
        config_dir.mkdir(parents=True)
        data = {
            "$schema": "cortex-quality-config-v1",
            "coverage_threshold": 75,
        }
        _ = (config_dir / "quality.json").write_text(json.dumps(data))

        cfg = load_quality_config(tmp_path)
        assert cfg.coverage_threshold == 75

    def test_load_real_config(self) -> None:
        """Verify the real .cortex/config/quality.json loads successfully."""
        project_root = Path(__file__).resolve().parents[2]
        config_path = project_root / ".cortex" / "config" / "quality.json"
        if config_path.is_file():
            cfg = load_quality_config(project_root)
            assert cfg.coverage_threshold == 90
            assert cfg.max_file_lines == 400
