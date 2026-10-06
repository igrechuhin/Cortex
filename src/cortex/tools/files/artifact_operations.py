"""Artifact filing helpers for manage_file(file_artifact)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from os.path import relpath
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.artifacts.artifact_types import (
    ArtifactType,
    get_artifact_directory,
    get_artifact_type_metadata,
)
from cortex.tools.plans.completion_content import (
    create_section_and_append,
    has_completed_entry_for_date_and_title,
)
from cortex.tools.plans.completion_io import read_file, write_active_context
from cortex.tools.plans.completion_transaction_io import validate_contained_path
from cortex.tools.response_builder import error_response, success_response
from cortex.wiki.categories import WikiCategoryDir
from cortex.wiki.wiki_root_files import WikiRootDocument


class FileArtifactParams(BaseModel):
    """Validated parameters for the file_artifact manage_file operation."""

    model_config = ConfigDict(frozen=True)

    artifact_type: ArtifactType
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    tags: list[str] | None = None


def _coerce_artifact_type(
    artifact_type: ArtifactType | str | None,
) -> ArtifactType | None:
    if artifact_type is None:
        return None
    if isinstance(artifact_type, ArtifactType):
        return artifact_type
    return ArtifactType(artifact_type)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "artifact"


def _build_candidate_path(
    project_root: Path,
    artifact_type: ArtifactType,
    title: str,
    date_iso: str,
) -> Path:
    metadata = get_artifact_type_metadata(artifact_type)
    slug = _slugify(title)
    file_name = metadata.filename_template.format(slug=slug, date=date_iso)
    return get_artifact_directory(project_root, artifact_type) / file_name


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _validate_params(
    artifact_type: ArtifactType | str | None,
    title: str | None,
    content: str | None,
    tags: list[str] | None,
) -> FileArtifactParams:
    resolved_type = _coerce_artifact_type(artifact_type)
    if resolved_type is None:
        raise ValueError("artifact_type is required for file_artifact operation")
    return FileArtifactParams(
        artifact_type=resolved_type,
        title=title or "",
        content=content or "",
        tags=tags,
    )


def _write_artifact_file(project_root: Path, params: FileArtifactParams) -> Path:
    date_iso = datetime.now(UTC).date().isoformat()
    target_path = _build_candidate_path(
        project_root=project_root,
        artifact_type=params.artifact_type,
        title=params.title,
        date_iso=date_iso,
    )
    validate_contained_path(target_path, project_root)
    final_path = _dedupe_path(target_path)
    validate_contained_path(final_path, project_root)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    with final_path.open("x", encoding="utf-8") as output:
        _ = output.write(params.content)
    return final_path


def _cross_reference_summary(
    artifact_type: ArtifactType,
    title: str,
    date_iso: str,
) -> str:
    metadata = get_artifact_type_metadata(artifact_type)
    return metadata.cross_reference_summary_template.format(title=title, date=date_iso)


def _validate_wiki_artifact_outputs(project_root: Path, candidate: Path) -> None:
    wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
    validate_contained_path(wiki_root, project_root)
    if not wiki_root.is_dir():
        return
    mirror = wiki_root / WikiCategoryDir.ANALYSES.value / candidate.name
    validate_contained_path(mirror, project_root)
    mirror = _dedupe_path(mirror)
    index = wiki_root / WikiRootDocument.INDEX.value
    for path in (mirror, index):
        validate_contained_path(path, project_root)
        validate_contained_path(path.with_suffix(f"{path.suffix}.tmp"), project_root)


def _validate_artifact_outputs(project_root: Path, params: FileArtifactParams) -> None:
    candidate = _build_candidate_path(
        project_root,
        params.artifact_type,
        params.title,
        datetime.now(UTC).date().isoformat(),
    )
    validate_contained_path(candidate, project_root)
    memory_bank = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    validate_contained_path(memory_bank / "activeContext.md", project_root)
    if params.artifact_type in (
        ArtifactType.REVIEW_REPORT,
        ArtifactType.SESSION_ANALYSIS,
    ):
        _validate_wiki_artifact_outputs(project_root, candidate)


async def execute_append_artifact_cross_reference(
    memory_bank_dir: Path,
    artifact_type: ArtifactType,
    title: str,
    artifact_path: Path,
    date_iso: str,
) -> str | None:
    """Append one artifact cross-reference entry to activeContext.md."""
    active_context_path = memory_bank_dir / "activeContext.md"
    validate_contained_path(active_context_path, memory_bank_dir.parent.parent)
    active_content, read_err = read_file(active_context_path)
    if read_err or active_content is None:
        return read_err or "Failed to read activeContext.md"

    cross_ref_rel_path = Path(relpath(artifact_path, memory_bank_dir)).as_posix()
    summary = _cross_reference_summary(artifact_type, title, date_iso)
    cross_ref_title = f"{title} [{cross_ref_rel_path}]"
    entry_summary = f"[{title}]({cross_ref_rel_path}) — {summary}"

    # AI: Title includes relative path so duplicate-suppression stays idempotent per artifact file.
    if has_completed_entry_for_date_and_title(
        active_content, date_iso, cross_ref_title
    ):
        return None

    new_content, inserted = create_section_and_append(
        active_content,
        date_iso,
        cross_ref_title,
        entry_summary,
    )
    if inserted is None:
        return "Could not find or create Completed Work section in activeContext.md"

    return await write_active_context(active_context_path, new_content)


async def file_artifact(
    project_root: Path,
    artifact_type: ArtifactType | str | None,
    title: str | None,
    content: str | None,
    tags: list[str] | None,
) -> str:
    """Write an artifact to its canonical directory and return its absolute path."""
    params, err = _validate_file_artifact_input(artifact_type, title, content, tags)
    if err is not None:
        return err
    assert params is not None
    return await _file_artifact_with_cross_reference(project_root, params)


def _validate_file_artifact_input(
    artifact_type: ArtifactType | str | None,
    title: str | None,
    content: str | None,
    tags: list[str] | None,
) -> tuple[FileArtifactParams | None, str | None]:
    try:
        return _validate_params(artifact_type, title, content, tags), None
    except Exception as exc:
        return None, json.dumps(
            error_response(error=str(exc), error_type="ValueError"), indent=2
        )


async def _file_artifact_with_cross_reference(
    project_root: Path, params: FileArtifactParams
) -> str:
    date_iso = datetime.now(UTC).date().isoformat()
    try:
        _validate_artifact_outputs(project_root, params)
        final_path = _write_artifact_file(project_root, params)
    except ValueError as exc:
        return json.dumps(
            error_response(error=str(exc), error_type="ValueError"), indent=2
        )
    memory_bank_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    from cortex.wiki.artifact_mirror import mirror_file_artifact_to_wiki_if_enabled

    _ = mirror_file_artifact_to_wiki_if_enabled(project_root, params)
    cross_ref_err = await execute_append_artifact_cross_reference(
        memory_bank_dir=memory_bank_dir,
        artifact_type=params.artifact_type,
        title=params.title,
        artifact_path=final_path,
        date_iso=date_iso,
    )
    if cross_ref_err:
        return json.dumps(
            error_response(error=cross_ref_err, error_type="ValueError"),
            indent=2,
        )
    _invalidate_cortex_context_cache()
    return _file_artifact_success_response(params, final_path)


def _invalidate_cortex_context_cache() -> None:
    # AI: cortex://context caches JSON; new filings must show in Recent Artifacts without stale reads.
    try:
        from cortex.tools.optimization.handlers import invalidate_context_resource_cache
    except ImportError:
        return
    invalidate_context_resource_cache()


def _file_artifact_success_response(
    params: FileArtifactParams, final_path: Path
) -> str:
    return json.dumps(
        success_response(
            operation="file_artifact",
            artifact_type=params.artifact_type.value,
            title=params.title,
            path=str(final_path),
        ),
        indent=2,
    )


async def file_artifact_from_payload(project_root: Path, payload: str | None) -> str:
    """Parse JSON payload and delegate to file_artifact."""
    if payload is None:
        return json.dumps(
            error_response(error="content is required for file_artifact operation"),
            indent=2,
        )
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return json.dumps(
            error_response(error="content for file_artifact must be valid JSON"),
            indent=2,
        )
    if not isinstance(data, dict):
        return json.dumps(
            error_response(error="content for file_artifact must be a JSON object"),
            indent=2,
        )
    try:
        params = FileArtifactParams.model_validate(data)
    except ValidationError as exc:
        return json.dumps(
            error_response(error=str(exc), error_type="ValueError"), indent=2
        )
    return await file_artifact(
        project_root=project_root,
        artifact_type=params.artifact_type,
        title=params.title,
        content=params.content,
        tags=params.tags,
    )
