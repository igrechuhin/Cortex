"""Structured quality configuration for Cortex projects.

Reads quality thresholds from ``.cortex/config/quality.json`` with
validated defaults. Replaces fragile markdown-parsed thresholds.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.pydantic_extra import EXTRA_FORBID

logger = logging.getLogger(__name__)

_CONFIG_RELATIVE_PATH = ".cortex/config/quality.json"


class QualityConfig(BaseModel):
    """Quality thresholds and scanning configuration."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    coverage_threshold: int = Field(
        default=90, ge=0, le=100, description="Minimum test coverage %"
    )
    max_file_lines: int = Field(
        default=400, ge=100, description="Maximum lines per source file"
    )
    max_function_lines: int = Field(
        default=30, ge=10, description="Maximum lines per function"
    )
    test_timeout_seconds: int = Field(
        default=120, ge=10, description="Default test timeout in seconds"
    )
    todo_patterns: list[str] = Field(
        default_factory=lambda: ["TODO", "FIXME", "HACK", "XXX"],
        description="Patterns to scan for in TODO detection",
    )
    exclude_from_todo_scan: list[str] = Field(
        default_factory=lambda: ["tests/", "examples/", "samples/", "demos/"],
        description="Path prefixes excluded from TODO scanning",
    )
    markdown_line_length: int = Field(
        default=120, ge=80, description="Max line length for markdown files"
    )

    @property
    def coverage_threshold_fraction(self) -> float:
        """Coverage threshold as a 0.0-1.0 fraction."""
        return self.coverage_threshold / 100.0


def load_quality_config(project_root: Path) -> QualityConfig:
    """Load quality config from ``.cortex/config/quality.json``.

    Returns defaults if the config file is missing or invalid.
    """
    config_path = project_root / _CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        logger.debug("quality.json not found at %s, using defaults", config_path)
        return QualityConfig()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        # Strip the $schema key — it's for documentation, not validation
        data.pop("$schema", None)
        return QualityConfig.model_validate(data)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load quality.json: %s — using defaults", exc)
        return QualityConfig()
    except ValidationError as exc:
        logger.warning("Invalid quality.json: %s — using defaults", exc)
        return QualityConfig()
