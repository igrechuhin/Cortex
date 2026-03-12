"""Archive logic for plan completion.

Handles moving completed plan files to appropriate archive subdirectories,
and removing the completed task's roadmap entry.
"""

import re
import shutil
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def archive_subdir_for_plan(filename: str) -> str | None:
    """Return archive subdir relative to plans/archive/ from plan filename, or None if unknown."""
    name = filename.strip()
    if not name or "/" in name or "\\" in name:
        return None
    if name.startswith("session-optimization-") and name.endswith(".md"):
        return "SessionOptimization"
    if "investigate" in name.lower() and name.endswith(".md"):
        match = re.search(r"(\d{8})", name)
        if match:
            d = match.group(1)
            return f"Investigations/{d[:4]}-{d[4:6]}-{d[6:8]}"
        return "Investigations"
    phase_match = re.match(r"phase-(\d+)-", name, re.IGNORECASE)
    if phase_match and name.endswith(".md"):
        return f"Phase{phase_match.group(1)}"
    return "Other"


def remove_roadmap_entry_for_plan(content: str, plan_file_name: str) -> str:
    """Remove the roadmap bullet that references plans/<plan_file_name>.

    Archiving a plan means the task is complete or declined — the entire
    roadmap entry is removed, not just the plan-file fragment.
    """
    escaped = re.escape(plan_file_name)
    pattern = re.compile(
        r"^- .*Plan:\s*`plans/" + escaped + r"`.*\n?",
        re.IGNORECASE | re.MULTILINE,
    )
    return pattern.sub("", content)


def _remove_roadmap_entry(root: Path, plan_file_name: str) -> None:
    """Remove the roadmap bullet for this plan file; best-effort, non-blocking."""
    from cortex.core.constants import MemoryBankFile
    from cortex.tools.plans.corruption import fix_roadmap_content_if_needed

    mem_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    roadmap_path = mem_dir / MemoryBankFile.ROADMAP
    try:
        content = roadmap_path.read_text(encoding="utf-8")
        new_content = remove_roadmap_entry_for_plan(content, plan_file_name)
        if new_content != content:
            fixed = fix_roadmap_content_if_needed(new_content)
            _ = roadmap_path.write_text(fixed, encoding="utf-8")
    except OSError:
        pass


def archive_plan_file(root: Path, plan_file_name: str) -> tuple[str | None, str | None]:
    """Move plan file to archive and remove its roadmap entry. Returns (archive_path, error)."""
    if Path(plan_file_name).name != plan_file_name:
        return (None, "plan_file_name must be a single filename (no path components)")
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    source = plans_dir / plan_file_name
    if not source.exists():
        return (None, f"Plan file not found: {plan_file_name}")
    subdir = archive_subdir_for_plan(plan_file_name)
    if subdir is None:
        return (None, f"Cannot determine archive location for: {plan_file_name}")
    plans_archive_root = get_cortex_path(root, CortexResourceType.PLANS_ARCHIVE)
    archive_dir = plans_archive_root / subdir
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / plan_file_name
    try:
        _ = shutil.move(str(source), str(dest))
    except OSError as e:
        return (None, f"Failed to move plan file: {e}")
    if source.exists():
        try:
            _ = source.unlink()
        except OSError:
            pass
    _remove_roadmap_entry(root, plan_file_name)
    return (str(dest), None)
