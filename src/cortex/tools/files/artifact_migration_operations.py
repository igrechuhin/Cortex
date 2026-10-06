"""Validated manage_file boundary for artifact relocation."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.managers.types import ManagersDict
from cortex.tools.files.artifact_migration import migrate_artifacts
from cortex.tools.response_builder import error_response


class ArtifactMigrationRequest(BaseModel):
    """Only preview/apply controls are accepted; callers cannot choose paths."""

    model_config = ConfigDict(extra=EXTRA_FORBID, strict=True)

    apply: StrictBool = False
    expected_preview_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


async def handle_artifact_migration(
    root: Path, managers: ManagersDict, content: str | None
) -> str:
    """Default to preview and reject malformed or path-bearing requests."""
    try:
        request = ArtifactMigrationRequest.model_validate_json(content or "{}")
    except ValidationError as exc:
        return json.dumps(
            error_response(error=str(exc), error_type="ValidationError"), indent=2
        )
    return await migrate_artifacts(
        root,
        managers,
        apply=request.apply,
        expected_preview_digest=request.expected_preview_digest,
    )
