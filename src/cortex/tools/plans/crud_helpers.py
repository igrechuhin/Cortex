"""
Helpers for plan CRUD: slug sanitization, path resolution, content extraction.
"""

import logging
import re
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_frontmatter_normalize import normalize_plan_frontmatter
from cortex.tools.plans.archive import is_path_under_archive
from cortex.tools.plans.crud_models import (
    CreatePlanResult,
    GetPlanResult,
    ListPlansResult,
    PlanEntry,
)
from cortex.wiki.glossary_models import TerminologyReport

logger = logging.getLogger(__name__)


def sanitize_plan_slug(title: str) -> str:
    """Sanitize title to create a valid filename slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def get_plan_directory(root: Path) -> Path:
    """Get the plans directory path."""
    return get_cortex_path(root, CortexResourceType.PLANS)


def extract_first_heading(content: str) -> str | None:
    """Extract first # or ## line text (strip # and whitespace)."""
    for line in content.split("\n"):
        s = line.strip()
        if s.startswith("#"):
            return re.sub(r"^#+\s*", "", s).strip() or None
    return None


def extract_status_line(content: str) -> str | None:
    """Extract **Status**: value from plan content."""
    for line in content.split("\n"):
        s = line.strip()
        if s.lower().startswith("**status**") and ":" in s:
            return s.split(":", 1)[1].strip().strip(".").strip()
    return None


def list_plan_files(
    root: Path, include_archive: bool
) -> tuple[list[tuple[str, Path]], str | None]:
    """List .md plan files. Returns ([(slug, path), ...], error_message)."""
    plans_dir = get_plan_directory(root)
    if not plans_dir.exists():
        return ([], None)
    result: list[tuple[str, Path]] = []
    try:
        for path in plans_dir.rglob("*.md"):
            if not path.is_file():
                continue
            if not include_archive:
                try:
                    rel = path.relative_to(plans_dir)
                    if is_path_under_archive(rel):
                        continue
                except ValueError:
                    continue
            result.append((path.stem, path))
        result.sort(key=lambda x: (x[1].name, str(x[1])))
        return (result, None)
    except Exception as e:
        return ([], str(e))


def get_plan_path(root: Path, slug: str) -> Path | None:
    """Resolve plan file path by slug (filename without .md). Returns None if not found."""
    plans_dir = get_plan_directory(root)
    if not plans_dir.exists():
        return None
    candidate = plans_dir / f"{slug}.md"
    if candidate.is_file():
        return candidate
    for path in plans_dir.rglob("*.md"):
        if path.stem == slug and path.is_file():
            return path
    return None


def create_plan_file(
    root: Path,
    title: str,
    slug: str | None,
    content: str,
) -> tuple[Path | None, str | None]:
    """Create a plan file. Returns (path, error_message)."""
    plans_dir = get_plan_directory(root)

    if not plans_dir.exists():
        try:
            plans_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return (None, f"Failed to create plans directory: {str(e)}")

    final_slug = slug if slug else sanitize_plan_slug(title)
    if not final_slug:
        return (None, "Could not generate valid filename from title or slug")

    plan_file = plans_dir / f"{final_slug}.md"

    try:
        _ = plan_file.write_text(normalize_plan_frontmatter(content), encoding="utf-8")
        return (plan_file, None)
    except Exception as e:
        return (None, f"Failed to write plan file: {str(e)}")


def create_success_result(
    plan_path: Path | None,
    *,
    planning_mode: str | None = None,
    review_prompt: str | None = None,
    terminology: TerminologyReport | None = None,
) -> CreatePlanResult:
    """Create a success result for plan creation.

    ``terminology`` is advisory only — it is echoed into the result and never
    downgrades ``status``.
    """
    if plan_path is None:
        return CreatePlanResult(
            status="error",
            file_path=None,
            message="Plan path is None",
            error="Unexpected: no path returned",
        )
    return CreatePlanResult(
        status="success",
        file_path=str(plan_path),
        message=f"Plan created at {plan_path}",
        error=None,
        planning_mode=planning_mode,
        review_prompt=review_prompt,
        terminology_findings=list(terminology.findings) if terminology else [],
        terminology_summary=terminology.summary() if terminology else None,
    )


def create_error_result(error: str) -> CreatePlanResult:
    """Create an error result for plan creation."""
    return CreatePlanResult(
        status="error",
        file_path=None,
        message="Failed to create plan file",
        error=error,
    )


def list_plans_impl(root: Path, include_archive: bool) -> ListPlansResult:
    """List plans; optionally include archive. Returns ListPlansResult."""
    pairs, err = list_plan_files(root, include_archive)
    if err:
        return ListPlansResult(
            status="error",
            plans=[],
            message="Failed to list plans",
            error=err,
        )
    entries: list[PlanEntry] = []
    for slug, path in pairs:
        title: str | None = None
        try:
            content = path.read_text(encoding="utf-8")
            title = extract_first_heading(content)
        except OSError as e:
            logger.warning("Failed to read plan %s: %s", path, e)
        except Exception as e:  # pragma: no cover
            logger.debug("Skipping plan %s due to unexpected error: %s", path, e)
        entries.append(PlanEntry(slug=slug, title=title))
    return ListPlansResult(
        status="success",
        plans=entries,
        message=f"Found {len(entries)} plan(s)",
        error=None,
    )


def get_plan_read_content(path: Path) -> tuple[str | None, str | None]:
    """Read plan file content. Returns (content, error_message)."""
    try:
        return (path.read_text(encoding="utf-8"), None)
    except Exception as e:
        return (None, str(e))


def get_plan_result_error(slug: str, message: str, error: str) -> GetPlanResult:
    """Build error GetPlanResult."""
    return GetPlanResult(
        status="error",
        slug=slug,
        content=None,
        title=None,
        plan_status=None,
        message=message,
        error=error,
        task_graph=[],
        can_parallelize=False,
    )


def _load_plan_raw_or_error(root: Path, slug: str) -> GetPlanResult | tuple[Path, str]:
    """Resolve plan path and read raw markdown, or return an error result."""
    path = get_plan_path(root, slug)
    if path is None:
        return get_plan_result_error(
            slug, "Plan not found", f"No plan file with slug '{slug}'"
        )
    content, read_err = get_plan_read_content(path)
    if read_err:
        return get_plan_result_error(slug, "Failed to read plan", read_err)
    return (path, content or "")


def _plan_task_graph_or_parse_error(
    slug: str, raw: str
) -> GetPlanResult | tuple[list[dict[str, object]], bool]:
    """Parse task graph or return a structured error result."""
    from cortex.core.plan_utils import (
        PlanValidationError,
        parse_task_graph,
        task_graph_can_parallelize,
    )

    try:
        nodes = parse_task_graph(raw)
    except PlanValidationError as exc:
        return get_plan_result_error(slug, "Invalid plan task graph", str(exc))
    task_graph = [node.model_dump() for node in nodes]
    return (task_graph, task_graph_can_parallelize(nodes))


def get_plan_result_success(
    slug: str,
    content: str | None,
    title: str | None,
    plan_status: str | None,
    message: str,
    *,
    change_count: int = 0,
    latest_delta: str | None = None,
    task_graph: list[dict[str, object]] | None = None,
    can_parallelize: bool = False,
) -> GetPlanResult:
    """Build success GetPlanResult."""
    return GetPlanResult(
        status="success",
        slug=slug,
        content=content,
        title=title,
        plan_status=plan_status,
        message=message,
        error=None,
        change_count=change_count,
        latest_delta=latest_delta,
        task_graph=list(task_graph or []),
        can_parallelize=can_parallelize,
    )


def get_plan_impl(root: Path, slug: str, response_format: str) -> GetPlanResult:
    """Read plan by slug. Returns GetPlanResult."""
    from cortex.core.plan_change_history import change_history_stats

    loaded = _load_plan_raw_or_error(root, slug)
    if isinstance(loaded, GetPlanResult):
        return loaded
    _path, raw = loaded
    chg_count, latest_d = change_history_stats(raw)
    parsed = _plan_task_graph_or_parse_error(slug, raw)
    if isinstance(parsed, GetPlanResult):
        return parsed
    task_graph, can_parallelize = parsed
    want_content = response_format == "content"
    return get_plan_result_success(
        slug,
        raw if want_content else None,
        None if want_content else extract_first_heading(raw),
        None if want_content else extract_status_line(raw),
        (
            f"Plan '{slug}' read successfully"
            if want_content
            else f"Plan '{slug}' metadata"
        ),
        change_count=chg_count,
        latest_delta=latest_d,
        task_graph=task_graph,
        can_parallelize=can_parallelize,
    )
