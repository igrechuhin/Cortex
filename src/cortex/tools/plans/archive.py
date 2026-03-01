"""
Plan archive path helpers.

Used by plan_crud when listing plans (include_archive / exclude archive paths).
"""

from pathlib import Path


def is_path_under_archive(rel: Path) -> bool:
    """Return True if the path is under an 'archive' directory."""
    return "archive" in rel.parts
