"""Project-level session settings from ``.cortex/session.yaml``."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.pydantic_extra import EXTRA_ALLOW

logger = logging.getLogger(__name__)

_SESSION_YAML = "session.yaml"
_SCHEMA_NAME_PATTERN = re.compile(r"^[a-z0-9][-a-z0-9]{0,63}$")


class ProjectSessionConfig(BaseModel):
    """Typed view of optional ``.cortex/session.yaml`` (workflow and future keys)."""

    # AI: Allow unknown keys so workflow ``condition`` expressions (e.g. eda_required)
    # can read values from session.yaml via ``model_dump`` without extending the model
    # each time a schema adds a flag.
    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    workflow_schema: str = Field(
        default="default",
        description="Stem of workflow YAML under .cortex/schemas/ or bundled schemas.",
    )
    experience_recall_enabled: bool = Field(
        default=True,
        description=(
            "Enable vector-seeded similar-task recall in session() orientation."
        ),
    )
    experience_recall_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Max similar prior tasks to surface in the recall block.",
    )
    experience_recall_similarity_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity for a task to be recalled.",
    )
    experience_recall_budget_chars: int = Field(
        default=600,
        ge=0,
        description="Max characters of the rendered recall block in SessionBrief.",
    )


def project_session_config_path(project_root: Path) -> Path:
    """Return path to ``.cortex/session.yaml``."""
    return get_cortex_path(project_root, CortexResourceType.CORTEX_DIR) / _SESSION_YAML


def load_project_session_config(project_root: Path) -> ProjectSessionConfig:
    """Load ``.cortex/session.yaml`` when present; otherwise defaults."""
    path = project_session_config_path(project_root)
    if not path.is_file():
        return ProjectSessionConfig()
    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        logger.warning("Failed to read session.yaml: %s", e)
        return ProjectSessionConfig()
    if raw is None:
        return ProjectSessionConfig()
    if not isinstance(raw, dict):
        logger.warning("session.yaml root must be a mapping")
        return ProjectSessionConfig()
    try:
        return ProjectSessionConfig.model_validate(raw)
    except Exception as e:
        logger.warning("Invalid session.yaml: %s", e)
        return ProjectSessionConfig()


def validate_schema_fork_name(name: str) -> str | None:
    """Return error message if ``name`` is not a safe schema file stem, else None."""
    n = name.strip().lower()
    if not n:
        return "new_name must be non-empty"
    if not _SCHEMA_NAME_PATTERN.fullmatch(n):
        return (
            "new_name must match ^[a-z0-9][-a-z0-9]{0,63}$ "
            "(lowercase letters, digits, hyphen)"
        )
    return None
