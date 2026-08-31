"""Small helpers for step plan workflow (keeps public handlers under line limits)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import PlanSectionStatus
from cortex.core.plan_frontmatter_normalize import normalize_plan_frontmatter
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.plans.crud_helpers import get_plan_directory
from cortex.tools.plans.step_draft_core import (
    STEP_STATE_BEGIN,
    ParsedStepDraft,
    StepSectionRecord,
    all_sections_terminal,
    canonical_section_key,
    draft_filename_for_slug,
    find_draft_section_key,
    find_next_pending_key,
    parse_step_draft_file,
    render_published_plan,
    render_step_draft_file,
    replace_section_body,
    update_record_status,
)
from cortex.tools.plans.step_plan_models import (
    StepApproveResult,
    StepContinueResult,
    StepFinalizeResult,
)
from cortex.tools.plans.terminology_gate import check_plan_terminology
from cortex.wiki.glossary_models import TerminologyReport


def slug_base(slug: str) -> str:
    return slug.removeprefix("draft-").removesuffix(".md")


def draft_path(root: Path, slug: str) -> Path:
    return get_plan_directory(root) / draft_filename_for_slug(slug)


def read_draft_text_with_root(
    root: Path, slug: str
) -> tuple[Path, str] | tuple[None, None]:
    path = draft_path(root, slug)
    if not path.is_file():
        return (None, None)
    return (path, path.read_text(encoding="utf-8"))


async def read_draft_bundle(
    slug: str, ctx: MCPContext | None
) -> tuple[Path, Path, str] | tuple[None, None, None]:
    root = await resolve_project_root_async(None, ctx)
    got = read_draft_text_with_root(root, slug)
    if got[0] is None:
        return (None, None, None)
    path, raw = got
    return (root, path, raw)


def load_parsed_draft(slug: str, raw: str) -> ParsedStepDraft | str:
    parsed = parse_step_draft_file(raw)
    if parsed is None:
        return (
            f"Draft '{draft_filename_for_slug(slug)}' is missing valid "
            f"{STEP_STATE_BEGIN.strip()} footer"
        )
    return parsed


def record_for_key(
    records: tuple[StepSectionRecord, ...], key: str
) -> StepSectionRecord | None:
    for r in records:
        if r.key == key:
            return r
    return None


def continue_error(
    message: str,
    error: str,
    *,
    file_path: str | None = None,
) -> str:
    return StepContinueResult(
        status="error",
        message=message,
        error=error,
        section_key=None,
        file_path=file_path,
    ).model_dump_json()


def approve_error(
    message: str,
    error: str,
    *,
    file_path: str | None = None,
    section_key: str | None = None,
) -> str:
    return StepApproveResult(
        status="error",
        message=message,
        error=error,
        file_path=file_path,
        section_key=section_key,
        next_hint=None,
    ).model_dump_json()


def finalize_error(
    message: str,
    error: str,
    *,
    draft_removed: str | None = None,
) -> str:
    return StepFinalizeResult(
        status="error",
        message=message,
        error=error,
        final_path=None,
        draft_removed=draft_removed,
        register_json=None,
    ).model_dump_json()


async def persist_draft(
    path: Path,
    fm: str | None,
    bodies: dict[str, str],
    records: tuple[StepSectionRecord, ...],
) -> None:
    text = render_step_draft_file(fm, bodies, records)
    _ = path.write_text(text, encoding="utf-8")


def continue_early_errors(slug: str | None, content: str | None) -> str | None:
    if not slug or not content or not content.strip():
        return continue_error(
            "slug and non-empty content are required for continue_step",
            "Missing slug or content",
        )
    return None


async def continue_load_parsed(
    slug: str, ctx: MCPContext | None
) -> tuple[Path, ParsedStepDraft] | str:
    bundle = await read_draft_bundle(slug, ctx)
    if bundle[0] is None:
        return continue_error(
            f"No draft file for slug '{slug_base(slug)}'",
            "Draft not found",
        )
    _root, path, raw = bundle
    loaded = load_parsed_draft(slug, raw)
    if isinstance(loaded, str):
        return continue_error(loaded, "Invalid draft", file_path=str(path))
    return (path, loaded)


def continue_gate_drafts(path: Path, parsed: ParsedStepDraft) -> str | None:
    active = find_draft_section_key(parsed.records)
    if active is None:
        return None
    return continue_error(
        (
            f"Section '{active}' is still in draft; call approve_step "
            "before generating the next section."
        ),
        "Draft section pending approval",
        file_path=str(path),
    )


async def continue_commit_write(
    path: Path,
    parsed: ParsedStepDraft,
    next_key: str,
    content: str,
    ctx: MCPContext | None,
) -> str:
    bodies = replace_section_body(parsed.bodies, next_key, content)
    new_records = update_record_status(
        parsed.records,
        next_key,
        status=PlanSectionStatus.DRAFT,
        approved_at=None,
    )
    text = render_step_draft_file(parsed.frontmatter, bodies, new_records)
    _ = path.write_text(text, encoding="utf-8")
    await log_client(
        ctx,
        "info",
        f"continue_step: wrote section {next_key} on {path}",
        logger_name=__name__,
    )
    return StepContinueResult(
        status="success",
        message=f"Drafted section '{next_key}' for review.",
        error=None,
        section_key=next_key,
        file_path=str(path),
    ).model_dump_json()


async def continue_step_run(
    slug: str | None,
    content: str | None,
    ctx: MCPContext | None,
) -> str:
    early = continue_early_errors(slug, content)
    if early is not None:
        return early
    assert slug is not None and content is not None
    resolved = await continue_load_parsed(slug, ctx)
    if isinstance(resolved, str):
        return resolved
    path, parsed = resolved
    blocked = continue_gate_drafts(path, parsed)
    if blocked is not None:
        return blocked
    next_key = find_next_pending_key(parsed.records)
    if next_key is None:
        return continue_error(
            "No pending sections remain; use finalize_step.",
            "No pending sections",
            file_path=str(path),
        )
    return await continue_commit_write(path, parsed, next_key, content, ctx)


async def approve_skip_branch(
    path: Path,
    parsed: ParsedStepDraft,
    key: str,
    ctx: MCPContext | None,
) -> str:
    bodies = parsed.bodies
    new_records = update_record_status(
        parsed.records,
        key,
        status=PlanSectionStatus.SKIPPED,
        approved_at=None,
    )
    if key in bodies:
        bodies = replace_section_body(bodies, key, "")
    await persist_draft(path, parsed.frontmatter, bodies, new_records)
    return StepApproveResult(
        status="success",
        message=f"Section '{key}' marked skipped.",
        error=None,
        file_path=str(path),
        section_key=key,
        next_hint=_post_approve_hint(new_records),
    ).model_dump_json()


def _post_approve_hint(records: tuple[StepSectionRecord, ...]) -> str:
    if find_draft_section_key(records):
        return (
            "Review the current draft section, then approve_step or apply corrections."
        )
    if find_next_pending_key(records):
        return "Call continue_step with markdown for the next pending section."
    if all_sections_terminal(records):
        return (
            "All sections approved or skipped — call finalize_step to publish the plan."
        )
    return "Proceed with the next planning tool action."


async def approve_corrections_branch(
    path: Path,
    parsed: ParsedStepDraft,
    key: str,
    corrections: str,
    ctx: MCPContext | None,
) -> str:
    bodies = replace_section_body(parsed.bodies, key, corrections)
    new_records = update_record_status(
        parsed.records,
        key,
        status=PlanSectionStatus.DRAFT,
        approved_at=None,
    )
    await persist_draft(path, parsed.frontmatter, bodies, new_records)
    msg = f"Section '{key}' revised from corrections (still draft)."
    await log_client(ctx, "info", f"approve_step: {msg}", logger_name=__name__)
    return StepApproveResult(
        status="success",
        message=msg,
        error=None,
        file_path=str(path),
        section_key=key,
        next_hint=_post_approve_hint(new_records),
    ).model_dump_json()


async def approve_plain_branch(
    path: Path,
    parsed: ParsedStepDraft,
    key: str,
    ctx: MCPContext | None,
) -> str:
    bodies = parsed.bodies
    new_records = update_record_status(
        parsed.records,
        key,
        status=PlanSectionStatus.APPROVED,
        approved_at=datetime.now(UTC),
    )
    await persist_draft(path, parsed.frontmatter, bodies, new_records)
    msg = f"Section '{key}' approved."
    await log_client(ctx, "info", f"approve_step: {msg}", logger_name=__name__)
    return StepApproveResult(
        status="success",
        message=msg,
        error=None,
        file_path=str(path),
        section_key=key,
        next_hint=_post_approve_hint(new_records),
    ).model_dump_json()


def final_plan_path(root: Path, slug: str) -> Path:
    base = slug_base(slug)
    return get_plan_directory(root) / f"{base}.md"


async def finalize_write_disk(
    root: Path,
    draft_path: Path,
    parsed: ParsedStepDraft,
    slug: str,
) -> Path:
    final_path = final_plan_path(root, slug)
    text = render_published_plan(parsed.frontmatter, parsed.bodies)
    _ = final_path.write_text(normalize_plan_frontmatter(text), encoding="utf-8")
    draft_path.unlink(missing_ok=False)
    return final_path


async def finalize_call_register(
    slug: str,
    plan_title: str,
    description: str,
    status: str,
    section: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.register import register_plan_in_roadmap

    base = slug_base(slug)
    return await register_plan_in_roadmap(
        plan_title=plan_title,
        description=description,
        status=status,
        section=section,
        plan_file_name=plan_file_name or f"{base}.md",
        plan_relative_path=plan_relative_path,
        ctx=ctx,
    )


def finalize_success_payload(
    final_path: Path,
    draft_path: Path,
    reg: str,
    terminology: TerminologyReport | None = None,
) -> StepFinalizeResult:
    return StepFinalizeResult(
        status="success",
        message=f"Plan finalized at {final_path}",
        error=None,
        final_path=str(final_path),
        draft_removed=str(draft_path),
        register_json=reg,
        terminology_findings=list(terminology.findings) if terminology else [],
        terminology_summary=terminology.summary() if terminology else None,
    )


async def _log_finalize_published(ctx: MCPContext | None, final_path: Path) -> None:
    """Log successful publication of a step-mode plan."""
    await log_client(
        ctx,
        "info",
        f"finalize_step: published {final_path} and registered roadmap",
        logger_name=__name__,
    )


async def finalize_register_result(
    final_path: Path,
    draft_path: Path,
    slug: str,
    plan_title: str,
    description: str,
    status: str,
    section: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
    terminology: TerminologyReport | None = None,
) -> str:
    reg = await finalize_call_register(
        slug,
        plan_title,
        description,
        status,
        section,
        plan_file_name,
        plan_relative_path,
        ctx,
    )
    await _log_finalize_published(ctx, final_path)
    return finalize_success_payload(
        final_path, draft_path, reg, terminology
    ).model_dump_json()


async def finalize_run(
    root: Path,
    draft_path: Path,
    parsed: ParsedStepDraft,
    slug: str,
    plan_title: str,
    description: str,
    status: str,
    section: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    final_path = await finalize_write_disk(root, draft_path, parsed, slug)
    # AI: Step mode registers the plan here, so the advisory gate runs at finalize —
    # after the file is published, so a collision can never block publication.
    terminology = check_plan_terminology(root, final_path.read_text(encoding="utf-8"))
    return await finalize_register_result(
        final_path,
        draft_path,
        slug,
        plan_title,
        description,
        status,
        section,
        plan_file_name,
        plan_relative_path,
        ctx,
        terminology,
    )


async def approve_fetch_draft(
    slug: str | None,
    ctx: MCPContext | None,
) -> tuple[Path, ParsedStepDraft] | str:
    if not slug:
        return approve_error(
            "slug and step_section are required for approve_step",
            "Missing slug or step_section",
        )
    bundle = await read_draft_bundle(slug, ctx)
    if bundle[0] is None:
        return approve_error(
            f"No draft file for slug '{slug_base(slug)}'",
            "Draft not found",
        )
    _root, path, raw = bundle
    loaded = load_parsed_draft(slug, raw)
    if isinstance(loaded, str):
        return approve_error(loaded, "Invalid draft", file_path=str(path))
    return (path, loaded)


def approve_resolve_section(
    path: Path,
    parsed: ParsedStepDraft,
    step_section: str | None,
) -> tuple[str, StepSectionRecord] | str:
    if not step_section:
        return approve_error(
            "slug and step_section are required for approve_step",
            "Missing slug or step_section",
        )
    key = canonical_section_key(step_section)
    if key is None:
        return approve_error(
            f"Unknown step_section '{step_section}'",
            "Invalid section key",
            file_path=str(path),
        )
    rec = record_for_key(parsed.records, key)
    if rec is None:
        return approve_error(
            f"Section '{key}' is not part of this draft",
            "Unknown section",
            file_path=str(path),
        )
    return (key, rec)


async def approve_handle_skip(
    path: Path,
    parsed: ParsedStepDraft,
    key: str,
    rec: StepSectionRecord,
    ctx: MCPContext | None,
) -> str:
    if rec.status not in (PlanSectionStatus.PENDING, PlanSectionStatus.DRAFT):
        return approve_error(
            f"Cannot skip section '{key}' in status {rec.status.value}",
            "Invalid status for skip",
            file_path=str(path),
            section_key=key,
        )
    return await approve_skip_branch(path, parsed, key, ctx)


async def approve_handle_corrections(
    path: Path,
    parsed: ParsedStepDraft,
    key: str,
    rec: StepSectionRecord,
    corrections: str,
    ctx: MCPContext | None,
) -> str:
    if rec.status != PlanSectionStatus.DRAFT:
        return approve_error(
            f"Corrections only apply when '{key}' is in draft status",
            "Invalid status for corrections",
            file_path=str(path),
            section_key=key,
        )
    return await approve_corrections_branch(path, parsed, key, corrections, ctx)


async def approve_handle_plain(
    path: Path,
    parsed: ParsedStepDraft,
    key: str,
    rec: StepSectionRecord,
    ctx: MCPContext | None,
) -> str:
    if rec.status != PlanSectionStatus.DRAFT:
        return approve_error(
            (
                "Only draft sections can be approved without corrections "
                f"(got {rec.status.value})"
            ),
            "Invalid status for approval",
            file_path=str(path),
            section_key=key,
        )
    return await approve_plain_branch(path, parsed, key, ctx)


async def approve_step_run(
    slug: str | None,
    step_section: str | None,
    corrections: str | None,
    step_skip: bool,
    ctx: MCPContext | None,
) -> str:
    if not step_section:
        return approve_error(
            "slug and step_section are required for approve_step",
            "Missing slug or step_section",
        )
    got = await approve_fetch_draft(slug, ctx)
    if isinstance(got, str):
        return got
    path, parsed = got
    resolved = approve_resolve_section(path, parsed, step_section)
    if isinstance(resolved, str):
        return resolved
    key, rec = resolved
    if step_skip:
        return await approve_handle_skip(path, parsed, key, rec, ctx)
    if corrections and corrections.strip():
        return await approve_handle_corrections(
            path, parsed, key, rec, corrections, ctx
        )
    return await approve_handle_plain(path, parsed, key, rec, ctx)


def finalize_validate_args(
    slug: str | None,
    plan_title: str | None,
    description: str | None,
) -> str | None:
    if not slug or not plan_title or not description:
        return finalize_error(
            "slug, plan_title, and description are required for finalize_step",
            "Missing finalize parameters",
        )
    return None


async def finalize_load_parsed_bundle(
    slug: str,
    ctx: MCPContext | None,
) -> tuple[Path, Path, ParsedStepDraft] | str:
    root = await resolve_project_root_async(None, ctx)
    got = read_draft_text_with_root(root, slug)
    if got[0] is None:
        return finalize_error(
            f"No draft file for slug '{slug_base(slug)}'",
            "Draft not found",
        )
    draft_path, raw = got
    loaded = load_parsed_draft(slug, raw)
    if isinstance(loaded, str):
        return finalize_error(loaded, "Invalid draft")
    parsed = loaded
    if not all_sections_terminal(parsed.records):
        return finalize_error(
            "All sections must be approved or skipped before finalize_step.",
            "Incomplete sections",
            draft_removed=str(draft_path),
        )
    return (root, draft_path, parsed)


async def finalize_step_run(
    slug: str | None,
    plan_title: str | None,
    description: str | None,
    status: str,
    section: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    early = finalize_validate_args(slug, plan_title, description)
    if early is not None:
        return early
    assert slug is not None and plan_title is not None and description is not None
    bundle = await finalize_load_parsed_bundle(slug, ctx)
    if isinstance(bundle, str):
        return bundle
    root, draft_path, parsed = bundle
    return await finalize_run(
        root,
        draft_path,
        parsed,
        slug,
        plan_title,
        description,
        status,
        section,
        plan_file_name,
        plan_relative_path,
        ctx,
    )
