"""Explicit, byte-preserving execution-owner correction for existing active plans."""

import hashlib
import json
import re
import stat
from collections.abc import Callable
from pathlib import Path
from typing import cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from yaml.nodes import MappingNode, ScalarNode

from cortex.core.context_logging import MCPContext
from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.core.models import PlanExecutionMode, PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_identity import build_plan_identity_index, is_plan_document
from cortex.core.plan_metadata import (
    read_plan_status_metadata,
    resolve_plan_status_token,
)
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.tools.files.document_patch_operations import (
    document_metadata_bytes,
    write_existing_document,
)
from cortex.tools.plans.completion_transaction_io import validate_contained_path

_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_OWNER = re.compile(
    rb"^execution[ \t]*:[ \t]*(?P<quote>['\"]?)(?P<owner>agent|operator)"
    + rb"(?P=quote)[ \t]*(?:#[^\r\n]*)?\r?$",
    re.M | re.I,
)


class PlanExecutionRequest(BaseModel):
    """Require an exact raw-byte preimage and explicit correction intent."""

    model_config = ConfigDict(extra=EXTRA_FORBID, strict=True)

    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution: PlanExecutionMode
    reason: str = Field(min_length=1)
    dry_run: StrictBool


def _execution_target(root: Path, slug: str | None) -> Path:
    if (
        slug is None
        or _SLUG.fullmatch(slug) is None
        or ".." in slug
        or slug.casefold().endswith(".md")
    ):
        raise ValueError("An exact root active plan slug without .md is required")
    plans = get_cortex_path(root, CortexResourceType.PLANS)
    target = plans / f"{slug}.md"
    validate_contained_path(target, root)
    if not is_plan_document(target) or not stat.S_ISREG(target.stat().st_mode):
        raise ValueError(
            "Target must be an existing regular active plan, not scaffolding"
        )
    row = build_plan_identity_index(plans, include_archive=True).unique.get(slug)
    if row is None or row.archived or row.path != target:
        raise ValueError("Plan identity is archived, ambiguous, or a draft")
    return target


def _execution_owners(frontmatter: bytes, status: PlanStatus) -> list[ScalarNode]:
    block = frontmatter.decode("utf-8-sig").splitlines()[1:-1]
    loader = yaml.SafeLoader("\n".join(block))
    try:
        node = loader.get_single_node()
    finally:
        cast(Callable[[], None], getattr(loader, "dispose"))()
    if not isinstance(node, MappingNode):
        raise ValueError("Plan frontmatter must be a mapping")
    owners: list[ScalarNode] = []
    for key, value in node.value:
        if not isinstance(key, ScalarNode):
            raise ValueError("Plan metadata keys must be scalars")
        if key.value == "<<":
            raise ValueError("Merged execution metadata is not supported")
        if key.value.casefold() == "status" and (
            not isinstance(value, ScalarNode)
            or resolve_plan_status_token(value.value) != status
        ):
            raise ValueError("Plan status metadata is conflicting or noncanonical")
        if key.value.casefold() == "execution":
            if (
                not isinstance(value, ScalarNode)
                or value.tag != "tag:yaml.org,2002:str"
            ):
                raise ValueError("Execution owner must be a scalar agent or operator")
            owners.append(value)
    return owners


def _execution_bytes(before: bytes, request: PlanExecutionRequest) -> tuple[bytes, str]:
    if hashlib.sha256(before).hexdigest() != request.expected_sha256:
        raise ValueError("Stale expected_sha256: plan bytes changed; read again")
    text = before.decode("utf-8-sig")
    metadata = read_plan_status_metadata(text)
    if not metadata.recognized or metadata.status == PlanStatus.DONE:
        raise ValueError(
            "Plan must have a recognized nonterminal, nonconflicting status"
        )
    frontmatter, title = document_metadata_bytes(before)
    if frontmatter is None:
        raise ValueError("Plan must have frontmatter with one scalar execution owner")
    if title and re.search(rb"\((?:DONE|COMPLETE|COMPLETED)\)", title, re.I):
        raise ValueError("Terminal plan title cannot receive an execution correction")
    owners = _execution_owners(frontmatter, metadata.status)
    matches = list(_OWNER.finditer(frontmatter))
    if len(owners) != 1 or len(matches) != 1:
        raise ValueError("Execution owner must be unique, explicit, and nonconflicting")
    previous = owners[0].value
    if previous not in {mode.value for mode in PlanExecutionMode}:
        raise ValueError("Execution owner must be agent or operator")
    match = matches[0]
    if match.group("owner").decode() != previous:
        raise ValueError("Execution owner must use one canonical scalar declaration")
    start, end = match.span("owner")
    return before[:start] + request.execution.value.encode() + before[end:], previous


async def _apply_execution(
    root: Path,
    slug: str | None,
    target: Path,
    relative: str,
    request: PlanExecutionRequest,
    result: dict[str, object],
) -> None:
    lock = target.with_suffix(".md.lock")
    validate_contained_path(lock, root)
    manager = FileSystemManager(root)
    await manager.acquire_lock(lock)
    try:
        target = _execution_target(root, slug)
        before = target.read_bytes()
        after, previous = _execution_bytes(before, request)
        changed = before != after
        if changed and not request.dry_run:
            write_existing_document(root, relative, target, before, after)
        result.update(
            status="success",
            before_sha256=hashlib.sha256(before).hexdigest(),
            after_sha256=hashlib.sha256(after).hexdigest(),
            previous_execution=previous,
            new_execution=request.execution.value,
            reason=request.reason,
            dry_run=request.dry_run,
            mutation_performed=changed and not request.dry_run,
        )
    finally:
        await manager.release_lock(lock)


async def set_plan_execution(
    slug: str | None, content: str | None, ctx: MCPContext | None
) -> str:
    """Correct metadata only; never complete a plan or authorize its actions."""
    root = Path(await get_or_resolve_project_root(ctx))
    result: dict[str, object] = {
        "status": "error",
        "operation": "set_execution",
        "project_root": str(root.absolute()),
        "target": None,
        "mutation_performed": False,
    }
    try:
        if ".." in root.parts or root.absolute() != root.resolve():
            raise ValueError("Plan project root cannot traverse symlinks")
        root = root.absolute()
        request = PlanExecutionRequest.model_validate_json(content or "{}")
        if not request.reason.strip():
            raise ValueError("Execution correction reason must be nonempty")
        target = _execution_target(root, slug)
        relative = target.relative_to(root).as_posix()
        result["target"] = relative
        _ = _execution_bytes(target.read_bytes(), request)
        await _apply_execution(root, slug, target, relative, request, result)
    except (OSError, ValueError, FileLockTimeoutError, yaml.YAMLError) as exc:
        result.update(error=str(exc), error_type=type(exc).__name__)
    return json.dumps(result, indent=2)
