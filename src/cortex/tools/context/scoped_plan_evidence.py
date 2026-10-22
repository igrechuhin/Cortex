"""Select plan evidence with canonical identities and graph metadata semantics."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.core.artifact_graph import read_plan_dependencies_from_content
from cortex.core.models._enums import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_identity import PlanIdentityIndex, build_plan_identity_index
from cortex.core.plan_metadata import (
    PlanStatusMetadata,
    read_frontmatter_fields,
    read_plan_status_metadata,
)
from cortex.tools.context.scoped_evidence_state import ScopedEvidenceState
from cortex.tools.context.scoped_readiness import ScopedReadiness
from cortex.tools.context.scoped_snapshot import ScopedSnapshot
from cortex.tools.context.scoped_source_state import ScopedSourceState
from cortex.tools.context.source_revision import SourceRevision


def _membership(index: PlanIdentityIndex, slug: str) -> list[str]:
    row = index.unique.get(slug)
    rows = [row] if row is not None else index.ambiguous.get(slug, [])
    return [row.relative_path for row in rows]


def _select_plan(
    snapshot: ScopedSnapshot, index: PlanIdentityIndex, slug: str
) -> str | None:
    key = f"plan:{slug}"
    members = _membership(index, slug)
    snapshot.memberships[slug] = members
    snapshot.add_text(f"selection:{key}", json.dumps(members), "membership", key)
    row = index.unique.get(slug)
    if row is None:
        state = ScopedSourceState.AMBIGUOUS if members else ScopedSourceState.MISSING
        snapshot.sources[key] = SourceRevision(
            identity=key,
            kind="plan",
            reference=key,
            provenance="canonical plan identity index",
            state=state,
        )
        snapshot.issue(state.value, [key], f"Plan identity is {state.value}: {slug}")
        return None
    try:
        text = snapshot.read(row.path, "plan", key)
    except (OSError, UnicodeError):
        snapshot.issue("unreadable", [key], f"Cannot decode selected plan: {slug}")
        return None
    snapshot.plans[slug] = text
    _metadata_issues(snapshot, slug, text)
    return text


def _metadata_issues(snapshot: ScopedSnapshot, slug: str, text: str) -> None:
    key = f"plan:{slug}"
    status = read_plan_status_metadata(text)
    if not status.recognized:
        code = (
            "conflicting_status" if status.conflicting else "missing_or_invalid_status"
        )
        snapshot.issue(
            code, [key], "Declared status is not unambiguous recognized evidence."
        )
    fields = read_frontmatter_fields(text, "depends_on")
    if not fields:
        snapshot.issue(
            "missing_dependencies", [key], "No declared dependency metadata."
        )
    elif len(set(fields)) > 1:
        snapshot.issue(
            "conflicting_dependencies", [key], "Dependency declarations disagree."
        )
    elif not (fields[0].startswith("[") and fields[0].endswith("]")):
        snapshot.issue(
            "invalid_dependencies",
            [key],
            "Dependency declaration is not an inline list.",
        )


def _visit_plan(
    snapshot: ScopedSnapshot,
    index: PlanIdentityIndex,
    slug: str,
    visiting: set[str],
    visited: set[str],
) -> None:
    if slug in visiting:
        snapshot.issue(
            "dependency_cycle",
            [f"plan:{slug}"],
            "Selected dependencies contain a cycle.",
        )
        return
    if slug in visited:
        return
    visited.add(slug)
    text = _select_plan(snapshot, index, slug)
    if text is None:
        return
    visiting.add(slug)
    for dependency in read_plan_dependencies_from_content(text):
        _visit_plan(snapshot, index, dependency, visiting, visited)
    visiting.remove(slug)
    status = read_plan_status_metadata(text)
    if (
        slug != snapshot.scope.removeprefix("plan:")
        and status.recognized
        and status.status == PlanStatus.DONE
    ):
        snapshot.upstream.append(slug)


def capture_plan_evidence(snapshot: ScopedSnapshot) -> None:
    """Read each selected plan once; keep incomplete and absent dependency evidence."""
    plans = get_cortex_path(snapshot.root, CortexResourceType.PLANS)
    index = build_plan_identity_index(plans, include_archive=True)
    slug = snapshot.scope.removeprefix("plan:")
    _visit_plan(snapshot, index, slug, set(), set())
    text = snapshot.plans.get(slug)
    if text is None:
        return
    metadata = read_plan_status_metadata(text)
    state = _status_evidence_state(metadata)
    snapshot.task.evidence("status", metadata.raw_token, [f"plan:{slug}"], state)
    for dependency in read_plan_dependencies_from_content(text):
        status = read_plan_status_metadata(snapshot.plans.get(dependency, ""))
        snapshot.task.dependency(
            dependency,
            f"plan:{dependency}",
            status.raw_token,
            status.recognized and status.status == PlanStatus.DONE,
        )
    blocked = any(not dep.satisfied for dep in snapshot.task.dependencies)
    snapshot.task.readiness = (
        ScopedReadiness.BLOCKED if blocked else ScopedReadiness.READY
    )
    if snapshot.task.issues:
        snapshot.task.readiness = (
            ScopedReadiness.UNKNOWN if not blocked else ScopedReadiness.BLOCKED
        )


def plan_membership_unchanged(snapshot: ScopedSnapshot) -> bool:
    """Detect selected identities created, removed, archived, or made ambiguous."""
    plans: Path = get_cortex_path(snapshot.root, CortexResourceType.PLANS)
    index = build_plan_identity_index(plans, include_archive=True)
    return all(
        _membership(index, slug) == members
        for slug, members in snapshot.memberships.items()
    )


def _status_evidence_state(metadata: PlanStatusMetadata) -> ScopedEvidenceState:
    if metadata.recognized:
        return ScopedEvidenceState.PRESENT
    if metadata.conflicting:
        return ScopedEvidenceState.CONFLICTING
    if metadata.raw_token is None:
        return ScopedEvidenceState.MISSING
    return ScopedEvidenceState.INVALID
