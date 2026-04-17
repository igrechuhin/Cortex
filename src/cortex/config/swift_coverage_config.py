"""Swift line-coverage exclusions for Cortex quality gate.

Optional config at ``.cortex/config/swift_coverage.json`` extends default
exclusions (``.build`` and ``Tests``) for SwiftPM JSON aggregation and
``llvm-cov report`` fallback.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.pydantic_extra import EXTRA_FORBID

logger = logging.getLogger(__name__)

_CONFIG_RELATIVE_PATH = ".cortex/config/swift_coverage.json"
_MAX_PATTERNS = 32
_MAX_PATTERN_LEN = 256

_ShortRegexFragment = Annotated[str, Field(min_length=1, max_length=_MAX_PATTERN_LEN)]


class SwiftCoverageConfig(BaseModel):
    """Swift coverage aggregation options."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    exclude_filename_regex_patterns: list[_ShortRegexFragment] = Field(
        default_factory=list,
        max_length=_MAX_PATTERNS,
        description=(
            "Regex fragments matched against each file path (forward slashes). "
            "Combined with built-in skips for .build and Tests paths."
        ),
    )


def load_swift_coverage_config(project_root: Path) -> SwiftCoverageConfig:
    """Load ``.cortex/config/swift_coverage.json`` or return defaults."""
    config_path = project_root / _CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        logger.debug("swift_coverage.json not found at %s, using defaults", config_path)
        return SwiftCoverageConfig()
    try:
        raw_obj: object = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw_obj, dict):
            logger.warning(
                "swift_coverage.json root must be an object — using defaults"
            )
            return SwiftCoverageConfig()
        data = cast(dict[str, object], raw_obj)
        _ = data.pop("$schema", None)
        return SwiftCoverageConfig.model_validate(data)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load swift_coverage.json: %s — using defaults", exc)
        return SwiftCoverageConfig()
    except ValidationError as exc:
        logger.warning("Invalid swift_coverage.json: %s — using defaults", exc)
        return SwiftCoverageConfig()
