"""Exact active plan identity for guarded lifecycle updates."""

import re
import stat
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_identity import build_plan_identity_index, is_plan_document
from cortex.tools.files.guarded_operation_refusal import (
    GuardedOperationRefusal,
    validate_guarded_path,
)

_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def require_active_plan_target(root: Path, slug: str | None) -> Path:
    """Require a unique, regular plan in the active plan directory."""
    if (
        slug is None
        or _SLUG.fullmatch(slug) is None
        or ".." in slug
        or slug.casefold().endswith(".md")
    ):
        raise GuardedOperationRefusal(
            "An exact root active plan slug without .md is required"
        )
    plans = get_cortex_path(root, CortexResourceType.PLANS)
    target = plans / f"{slug}.md"
    validate_guarded_path(target, root)
    if not is_plan_document(target) or not stat.S_ISREG(target.stat().st_mode):
        raise GuardedOperationRefusal(
            "Target must be an existing regular active plan, not scaffolding"
        )
    row = build_plan_identity_index(plans, include_archive=True).unique.get(slug)
    if row is None or row.archived or row.path != target:
        raise GuardedOperationRefusal(
            "Plan identity is archived, ambiguous, or a draft"
        )
    return target
