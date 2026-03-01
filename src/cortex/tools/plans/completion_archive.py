"""Archive logic for plan completion.

Handles moving completed plan files to appropriate archive subdirectories.
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


def archive_plan_file(root: Path, plan_file_name: str) -> tuple[str | None, str | None]:
    """Move plan file to archive and remove duplicate from plans root. Returns (archive_path, error)."""
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
    return (str(dest), None)
