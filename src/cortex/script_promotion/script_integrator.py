"""Integrate session scripts into Synapse script library templates."""

from cortex.core.path_resolver import ProjectResourceType
from cortex.script_detection.models import ScriptCaptureRecord


def _script_stem_from_task(task: str) -> str:
    """Derive a script filename stem from task description."""
    normalized = "".join(c if c.isalnum() or c in " _-" else " " for c in (task or ""))
    parts = normalized.lower().split()[:4]
    return "_".join(parts) if parts else "session_script"


def script_integration_template(
    record: ScriptCaptureRecord,
    language: str = "python",
    script_name: str | None = None,
) -> tuple[str, str]:
    """Produce Synapse script path and content template.

    Args:
        record: Captured script record.
        language: Target language directory (e.g. python).
        script_name: Optional script stem; derived from task if missing.

    Returns:
        (relative_path, content) e.g. ("scripts/python/check_foo.py", "...")
    """
    stem = (script_name or "").strip() or _script_stem_from_task(
        record.task_description
    )
    rel_path = f"scripts/{language}/{stem}.py"
    doc = (record.task_description or "Session script").replace('"""', "'")
    content = f'''"""
Synapse script template from session script: {record.script_id}
Original task: {doc[:200]}
Run via: {ProjectResourceType.VENV.value}/bin/python .cortex/synapse/scripts/{language}/{stem}.py
"""

import sys


def main() -> int:
    """Entry point. TODO: Port logic from captured script."""
    # TODO: Port logic from script_content.
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
    return (rel_path, content)
