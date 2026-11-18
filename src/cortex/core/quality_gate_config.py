"""Persistent, opt-in project defaults for the quality gate."""

from __future__ import annotations

import json
import os
import tempfile
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

DEFAULT_TEST_TIMEOUT = 900


class SwiftTestOutput(StrEnum):
    """Project-reviewed operational paths that are not Swift test inputs."""

    ACTIVE_CONTEXT = ".cortex/memory-bank/activeContext.md"
    PROGRESS = ".cortex/memory-bank/progress.md"
    ROADMAP = ".cortex/memory-bank/roadmap.md"
    EXPERIENCE = ".cortex/experience/experience.db"
    EXPERIENCE_ARTIFACTS = ".cortex/experience/artifacts/"
    TOOL_WAL = ".cortex/wal/tool_invocations.jsonl"
    WRITE_WAL = ".cortex/wal/write_log.jsonl"
    MARKDOWN_CACHE = ".rumdl_cache/"
    PYTHON_VENV = ".venv/"


class ProjectQualityGateConfig(BaseModel):
    """A project timeout default, independent of pipeline sessions."""

    model_config = ConfigDict(extra="forbid", strict=True)

    test_timeout: int | None = Field(gt=0)
    reuse_swiftpm_final_tests: bool = False
    swiftpm_final_test_outputs: tuple[SwiftTestOutput, ...] = ()


def quality_gate_config_path(root: Path) -> Path:
    """Resolve the project-owned config without following external symlinks."""
    path = get_cortex_path(root, CortexResourceType.CONFIG) / "quality-gate.json"
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Quality-gate configuration must stay inside the project")
    if path.is_symlink():
        raise ValueError("Quality-gate configuration must not be a symlink")
    return path


def load_quality_gate_config(root: Path) -> ProjectQualityGateConfig:
    """Read the project policy; malformed configuration fails closed."""
    path = quality_gate_config_path(root)
    if not path.exists():
        return ProjectQualityGateConfig(test_timeout=None)
    return ProjectQualityGateConfig.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def effective_test_timeout(root: Path) -> int:
    """Resolve the project override or the global fifteen-minute default."""
    return load_quality_gate_config(root).test_timeout or DEFAULT_TEST_TIMEOUT


def save_quality_gate_config(root: Path, config: ProjectQualityGateConfig) -> Path:
    """Atomically replace one small project configuration file."""
    path = quality_gate_config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # AI: Unique siblings avoid partial JSON and competing writers' temporary files.
    fd, temporary = tempfile.mkstemp(prefix=".quality-gate-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            _ = stream.write(
                config.model_dump_json(indent=2, exclude_defaults=True) + "\n"
            )
        _ = Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def configure_quality_gate(root: Path, data: str | None) -> str:
    """Read with no payload, or set validated project policy with a payload."""
    try:
        config = (
            load_quality_gate_config(root)
            if data is None
            else ProjectQualityGateConfig.model_validate_json(data)
        )
        path = (
            quality_gate_config_path(root)
            if data is None
            else save_quality_gate_config(root, config)
        )
    except (OSError, ValueError) as exc:
        return json.dumps({"status": "error", "error": str(exc)})
    return json.dumps(
        {
            "status": "ok",
            "scope": "project",
            "config_file": str(path),
            "config": config.model_dump(exclude_defaults=True),
            "effective_default_test_timeout": config.test_timeout
            or DEFAULT_TEST_TIMEOUT,
            "timeout_semantics": "session override > project setting > global default",
            "mutation_performed": data is not None,
        }
    )
