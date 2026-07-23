"""Swift xcodebuild test-skip configuration for Cortex quality gate.

Optional config at ``.cortex/config/swift_test.json`` lists Xcode
``-skip-testing:`` identifiers (``Target/Class`` or ``Target/Class/method``)
excluded from ``xcodebuild test`` / ``test-without-building`` runs — e.g. a
live-network integration test suite a project's own CLAUDE.md documents as
excluded from its standard test command.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.pydantic_extra import EXTRA_FORBID

logger = logging.getLogger(__name__)

_CONFIG_RELATIVE_PATH = ".cortex/config/swift_test.json"
_MAX_IDENTIFIERS = 32
_MAX_IDENTIFIER_LEN = 256

_SkipTestingIdentifier = Annotated[
    str, Field(min_length=1, max_length=_MAX_IDENTIFIER_LEN)
]


class SwiftTestConfig(BaseModel):
    """Swift xcodebuild test-run options."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    skip_testing: list[_SkipTestingIdentifier] = Field(
        default_factory=list,
        max_length=_MAX_IDENTIFIERS,
        description=(
            "Xcode -skip-testing: identifiers (Target/Class or "
            "Target/Class/method) excluded from xcodebuild test / "
            "test-without-building runs."
        ),
    )


def load_swift_test_config(project_root: Path) -> SwiftTestConfig:
    """Load ``.cortex/config/swift_test.json`` or return defaults."""
    config_path = project_root / _CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        logger.debug("swift_test.json not found at %s, using defaults", config_path)
        return SwiftTestConfig()
    try:
        raw_obj: object = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw_obj, dict):
            logger.warning("swift_test.json root must be an object — using defaults")
            return SwiftTestConfig()
        data = cast(dict[str, object], raw_obj)
        _ = data.pop("$schema", None)
        return SwiftTestConfig.model_validate(data)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load swift_test.json: %s — using defaults", exc)
        return SwiftTestConfig()
    except ValidationError as exc:
        logger.warning("Invalid swift_test.json: %s — using defaults", exc)
        return SwiftTestConfig()
