"""Canonical-root read orchestration for ``plan()`` list/get operations.

Each canonical file is captured exactly once (raw bytes) and that single
capture feeds both parsing and provenance. Before returning, every capture
is re-verified unchanged and the canonical HEAD revision is revalidated, so
mutations during assembly fail closed instead of binding mismatched content
and revision. Local freshness uses the existing plan identity index once and
reports ambiguous/unreadable local counterparts as such. Read-only: no
writes to either root, no manager initialization, no local semantics
changes.
"""

from __future__ import annotations

from pathlib import Path

from cortex.core.canonical_project import (
    CanonicalLocalState,
    CanonicalProjectError,
    CanonicalProjectIdentity,
    CanonicalReadProvenance,
    CapturedSource,
    capture_file,
    local_context_unsafe,
    resolve_canonical_identity,
    revalidate_revision,
    sha256_bytes,
)
from cortex.core.models import PlanReadSource
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_identity import (
    PlanIdentityIndex,
    build_plan_identity_index,
)
from cortex.tools.plans.crud_helpers import (
    build_plan_result_from_text,
    get_plan_path,
    list_plan_files,
)
from cortex.tools.plans.crud_models import (
    GetPlanResult,
    ListPlansResult,
    PlanEntry,
)


def canonical_read_error(operation: str, exc: CanonicalProjectError) -> str:
    """Structured JSON error for an unavailable canonical read (fail closed)."""
    if operation == "list":
        return ListPlansResult(
            status="error",
            plans=[],
            message="Canonical read unavailable",
            error=f"{exc.failure.value}: {exc.detail}",
        ).model_dump_json()
    return GetPlanResult(
        status="error",
        slug=None,
        content=None,
        title=None,
        plan_status=None,
        relative_path=None,
        message="Canonical read unavailable",
        error=f"{exc.failure.value}: {exc.detail}",
    ).model_dump_json()


def _get_error(slug: str, message: str, error: str) -> str:
    return GetPlanResult(
        status="error",
        slug=slug,
        content=None,
        title=None,
        plan_status=None,
        relative_path=None,
        message=message,
        error=error,
    ).model_dump_json()


def _mutation_error(slug: str | None, list_mode: bool = False) -> str:
    if list_mode:
        return ListPlansResult(
            status="error",
            plans=[],
            message="Canonical plans changed during read",
            error="revision_changed_during_read: re-read required",
        ).model_dump_json()
    return _get_error(
        slug or "",
        "Canonical plan changed during read",
        "revision_changed_during_read: re-read required",
    )


def _safe_digest(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return None


def _local_state_for_slug(
    local_root: Path, slug: str, canonical_sha256: str
) -> tuple[CanonicalLocalState, str | None]:
    """Freshness of one local plan counterpart, preserving failure states."""
    if local_context_unsafe(local_root):
        return (CanonicalLocalState.UNSAFE, None)
    try:
        local_path = get_plan_path(local_root, slug)
    except ValueError:
        return (CanonicalLocalState.AMBIGUOUS, None)
    if local_path is None:
        return (CanonicalLocalState.MISSING, None)
    local_digest = _safe_digest(local_path)
    if local_digest is None:
        return (CanonicalLocalState.UNREADABLE, None)
    if local_digest == canonical_sha256:
        return (CanonicalLocalState.IDENTICAL, local_digest)
    return (CanonicalLocalState.DIVERGED, local_digest)


def canonical_get_plan(local_root: Path, slug: str, response_format: str) -> str:
    """Read one plan from the canonical main worktree with provenance."""
    try:
        identity = resolve_canonical_identity(local_root)
    except CanonicalProjectError as exc:
        return canonical_read_error("get", exc)
    capture = _canonical_capture_or_error(identity.canonical_root, slug)
    if isinstance(capture, str):
        return capture
    result = build_plan_result_from_text(
        slug,
        capture.text(),
        capture.path.relative_to(identity.canonical_root).as_posix(),
        response_format,
    )
    if result.status != "success":
        return result.model_dump_json()
    local_state, local_digest = _local_state_for_slug(local_root, slug, capture.sha256)
    # AI: Final coherence gate — content, provenance and repository context
    # must all describe the same instant, so re-verify after assembly.
    if not capture.unchanged() or not revalidate_revision(identity):
        return _mutation_error(slug)
    result.provenance = CanonicalReadProvenance(
        source=PlanReadSource.CANONICAL,
        root=identity.canonical_root,
        relation=identity.relation,
        git_revision=identity.git_revision,
        content_sha256=capture.sha256,
        local_state=local_state,
        local_content_sha256=local_digest,
    )
    return result.model_dump_json()


def _entry_from_capture(
    canonical_root: Path,
    plans_dir: Path,
    slug: str,
    path: Path,
) -> tuple[PlanEntry, CapturedSource | None]:
    from cortex.tools.plans.crud_helpers import extract_plan_title

    try:
        capture = capture_file(path)
        title = extract_plan_title(capture.text())
    except OSError:
        capture = None
        title = None
    entry = PlanEntry(
        slug=slug,
        title=title,
        relative_path=path.relative_to(canonical_root).as_posix(),
        archived=path.relative_to(plans_dir).parts[:1] == ("archive",),
    )
    return (entry, capture)


def _canonical_capture_or_error(
    canonical_root: Path, slug: str
) -> CapturedSource | str:
    """Capture one canonical plan file, or return a serialized error result."""
    try:
        canonical_path = get_plan_path(canonical_root, slug)
    except ValueError as exc:
        return _get_error(slug, "Ambiguous canonical plan identity", str(exc))
    if canonical_path is None:
        return _get_error(
            slug,
            "Plan not found in canonical root",
            f"No canonical plan file with slug '{slug}'",
        )
    try:
        return capture_file(canonical_path)
    except OSError as exc:
        return _get_error(slug, "Failed to read canonical plan", str(exc))


class _FreshnessLists:
    """Mutable local freshness slug lists for one canonical list read."""

    def __init__(self) -> None:
        self.missing: list[str] = []
        self.stale: list[str] = []
        self.unsafe: list[str] = []
        self.ambiguous: list[str] = []
        self.unreadable: list[str] = []


def _list_freshness_lists(
    local_root: Path, captures: dict[str, CapturedSource]
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Local freshness slug lists, preserving ambiguous/unreadable/unsafe."""
    unsafe_context = local_context_unsafe(local_root)
    local_index = (
        None
        if unsafe_context
        else build_plan_identity_index(
            get_cortex_path(local_root, CortexResourceType.PLANS),
            include_archive=True,
        )
    )
    lists = _FreshnessLists()
    seen_slugs: set[str] = set()
    for capture in captures.values():
        slug = capture.path.stem
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        _classify_local_slug(slug, capture.sha256, unsafe_context, local_index, lists)
    return (lists.missing, lists.stale, lists.unsafe, lists.ambiguous, lists.unreadable)


def _classify_local_slug(
    slug: str,
    canonical_sha256: str,
    unsafe_context: bool,
    local_index: PlanIdentityIndex | None,
    lists: _FreshnessLists,
) -> None:
    """Assign one slug its local freshness category, preserving failures."""
    if unsafe_context or local_index is None:
        lists.unsafe.append(slug)
    elif slug in local_index.ambiguous:
        lists.ambiguous.append(slug)
    elif slug not in local_index.unique:
        lists.missing.append(slug)
    else:
        local_digest = _safe_digest(local_index.unique[slug].path)
        if local_digest is None:
            lists.unreadable.append(slug)
        elif local_digest != canonical_sha256:
            lists.stale.append(slug)


def _capture_canonical_entries(
    canonical_root: Path, plans_dir: Path, pairs: list[tuple[str, Path]]
) -> tuple[list[PlanEntry], dict[str, CapturedSource]]:
    """Capture every canonical plan once, keyed by resolved path."""
    entries: list[PlanEntry] = []
    # AI: Key captures by resolved path so duplicate slugs in the canonical
    # tree cannot silently overwrite each other's captured revision.
    captures: dict[str, CapturedSource] = {}
    for slug, path in pairs:
        entry, capture = _entry_from_capture(canonical_root, plans_dir, slug, path)
        entries.append(entry)
        if capture is not None:
            captures[path.resolve().as_posix()] = capture
    return (entries, captures)


def _list_snapshot_unchanged(
    canonical_root: Path,
    include_archive: bool,
    pairs: list[tuple[str, Path]],
    captures: dict[str, CapturedSource],
) -> bool:
    """Re-verify directory membership, captured bytes and canonical HEAD."""
    after_pairs, after_err = list_plan_files(canonical_root, include_archive)
    membership_changed = after_err is not None or {
        path.resolve().as_posix() for _, path in pairs
    } != {path.resolve().as_posix() for _, path in after_pairs}
    if membership_changed:
        return False
    return all(capture.unchanged() for capture in captures.values())


def _canonical_list_result(
    identity: CanonicalProjectIdentity,
    entries: list[PlanEntry],
    freshness: tuple[list[str], list[str], list[str], list[str], list[str]],
) -> str:
    """Serialize the successful canonical list result with provenance."""
    missing, stale, unsafe, ambiguous, unreadable = freshness
    result = ListPlansResult(
        status="success",
        plans=entries,
        message=f"Found {len(entries)} canonical plan(s)",
        error=None,
    )
    result.provenance = CanonicalReadProvenance(
        source=PlanReadSource.CANONICAL,
        root=identity.canonical_root,
        relation=identity.relation,
        git_revision=identity.git_revision,
        local_unsafe=sorted(unsafe),
        local_missing=sorted(missing),
        local_stale=sorted(stale),
        local_ambiguous=sorted(ambiguous),
        local_unreadable=sorted(unreadable),
    )
    return result.model_dump_json()


def canonical_list_plans(local_root: Path, include_archive: bool) -> str:
    """List plans from the canonical main worktree with provenance."""
    try:
        identity = resolve_canonical_identity(local_root)
    except CanonicalProjectError as exc:
        return canonical_read_error("list", exc)
    canonical_root = identity.canonical_root
    plans_dir = get_cortex_path(canonical_root, CortexResourceType.PLANS)
    pairs, err = list_plan_files(canonical_root, include_archive)
    if err:
        return ListPlansResult(
            status="error",
            plans=[],
            message="Failed to list canonical plans",
            error=err,
        ).model_dump_json()
    entries, captures = _capture_canonical_entries(canonical_root, plans_dir, pairs)
    freshness = _list_freshness_lists(local_root, captures)
    # AI: Final coherence gate after freshness assembly — re-verify every
    # captured source, the directory membership, and the repository context
    # before publishing results; an incomplete snapshot fails closed.
    if not _list_snapshot_unchanged(
        canonical_root, include_archive, pairs, captures
    ) or not revalidate_revision(identity):
        return _mutation_error(None, list_mode=True)
    return _canonical_list_result(identity, entries, freshness)


def supported_canonical_operations() -> tuple[str, ...]:
    """Operations that accept ``source="canonical"`` (read-only surface)."""
    return ("list", "get")


__all__ = [
    "canonical_get_plan",
    "canonical_list_plans",
    "canonical_read_error",
    "supported_canonical_operations",
]
