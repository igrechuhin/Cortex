"""
Helpers for plan CRUD: slug sanitization, path resolution, content extraction.
"""

import re
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.archive import is_path_under_archive
from cortex.tools.plans.crud_models import (
    CreatePlanResult,
    GetPlanResult,
    ListPlansResult,
    PlanEntry,
)


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
        _ = plan_file.write_text(content, encoding="utf-8")
        return (plan_file, None)
    except Exception as e:
        return (None, f"Failed to write plan file: {str(e)}")


def create_success_result(plan_path: Path | None) -> CreatePlanResult:
    """Create a success result for plan creation."""
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
        except Exception:
            pass
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
    )


def get_plan_result_success(
    slug: str,
    content: str | None,
    title: str | None,
    plan_status: str | None,
    message: str,
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
    )


def get_plan_impl(root: Path, slug: str, response_format: str) -> GetPlanResult:
    """Read plan by slug. Returns GetPlanResult."""
    path = get_plan_path(root, slug)
    if path is None:
        return get_plan_result_error(
            slug, "Plan not found", f"No plan file with slug '{slug}'"
        )
    content, read_err = get_plan_read_content(path)
    if read_err:
        return get_plan_result_error(slug, "Failed to read plan", read_err)
    if response_format == "content":
        return get_plan_result_success(
            slug, content, None, None, f"Plan '{slug}' read successfully"
        )
    return get_plan_result_success(
        slug,
        None,
        extract_first_heading(content or ""),
        extract_status_line(content or ""),
        f"Plan '{slug}' metadata",
    )
