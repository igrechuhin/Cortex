"""Resolve prompt directories and load manifest / prompt file content."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cortex.core.models import JsonDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

_logger = logging.getLogger(__name__)

_POST_PROMPT_HOOK_REF = "post-prompt-hook.md"
_POST_PROMPT_HOOK_SNIPPET = (
    "## Post-Prompt Hook\n\n"
    "Read `.cortex/synapse/prompts/post-prompt-hook.md` and execute it after "
    "the final report to run the post-prompt self-improvement router.\n"
)
_POST_PROMPT_HOOK_EXCLUDED_FILES = frozenset({"analyze.md", "post-prompt-hook.md"})


def _paths_anchor() -> Path:
    """Return this module's path (tests may patch this for discovery fallbacks)."""
    return Path(__file__)


def get_prompts_paths(project_root: Path | None = None) -> list[Path]:
    """Get paths to all prompts directories.

    When *project_root* is provided the search is scoped to that directory and
    no further CWD or module-anchor walking is performed.  This is the
    preferred call-site when the project root has already been resolved
    (e.g. via :func:`resolve_project_root_async`).

    When *project_root* is ``None`` the function falls back to the original
    heuristic: walk up from CWD first, then from the module file location.
    The fallback exists for backward-compatibility and for the case where the
    server is run directly from the project directory (``python -m cortex.main``
    with a correctly inherited CWD).

    Returns paths for:
    - .cortex/synapse/prompts/ (shared Synapse prompts)
    - .cortex/prompts/ (project-specific prompts)
    """
    found_paths: list[Path] = []
    prompt_dirs = ["synapse/prompts", "prompts"]

    if project_root is not None:
        # Fast path: explicit root, no walking needed.
        cortex_root = get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
        for prompt_dir in prompt_dirs:
            prompts_path = cortex_root / prompt_dir
            if prompts_path.exists() and prompts_path.is_dir():
                found_paths.append(prompts_path)
        return found_paths

    # Heuristic fallback: walk up from CWD (works when CWD == project root).
    current = Path.cwd()
    for path in [current, *current.parents]:
        cortex_root = get_cortex_path(path, CortexResourceType.CORTEX_DIR)
        for prompt_dir in prompt_dirs:
            prompts_path = cortex_root / prompt_dir
            if prompts_path.exists() and prompts_path.is_dir():
                if prompts_path not in found_paths:
                    found_paths.append(prompts_path)

    # Secondary fallback: walk up from module file location.
    # Helps dev-install (src/ layout) when CWD is not the project root.
    # Does NOT help pip/uvx installs whose __file__ is in site-packages.
    anchor = _paths_anchor()
    for path in [
        anchor.parent.parent.parent.parent,
        *anchor.parent.parent.parent.parent.parents,
    ]:
        cortex_root = get_cortex_path(path, CortexResourceType.CORTEX_DIR)
        for prompt_dir in prompt_dirs:
            prompts_path = cortex_root / prompt_dir
            if prompts_path.exists() and prompts_path.is_dir():
                if prompts_path not in found_paths:
                    found_paths.append(prompts_path)

    return found_paths


def get_synapse_prompts_path() -> Path | None:
    """Get path to Synapse prompts directory (for backwards compatibility).

    Prefers ``.cortex/synapse/prompts/`` over ``.cortex/prompts/`` when both
    exist. Falls back to ``paths[0]`` (the first discovered path) when no
    synapse-shaped entry is found, or returns ``None`` if no paths exist.
    """
    paths = get_prompts_paths()
    for path in paths:
        if path.name == "prompts" and path.parent.name == "synapse":
            return path
    return paths[0] if paths else None


def load_prompts_manifest(prompts_path: Path) -> JsonDict | None:
    """Load prompts manifest synchronously."""
    manifest_path = prompts_path / "prompts-manifest.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
            return JsonDict.from_dict(data)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        _logger.debug("prompts manifest unreadable: %s", manifest_path, exc_info=True)
        return None


def load_prompt_content(prompts_path: Path, category: str, filename: str) -> str | None:
    """Load prompt file content synchronously."""
    # Prompts are in the root of prompts/ directory, not in category subdirectories
    # Apply path traversal protection to ensure files stay within prompts_path.
    base_dir = prompts_path.resolve()

    candidate = prompts_path / filename

    # Reject absolute paths or explicit parent directory traversal segments
    filename_path = Path(filename)
    if filename_path.is_absolute() or ".." in filename_path.parts:
        return None

    try:
        resolved = candidate.resolve()
    except OSError:
        return None

    # Ensure the resolved path is within the prompts base directory
    try:
        _ = resolved.relative_to(base_dir)
    except ValueError:
        return None

    if not resolved.exists() or not resolved.is_file():
        return None

    try:
        with open(resolved, encoding="utf-8") as f:
            content = f.read()
            if (
                filename not in _POST_PROMPT_HOOK_EXCLUDED_FILES
                and _POST_PROMPT_HOOK_REF not in content
            ):
                return f"{content.rstrip()}\n\n{_POST_PROMPT_HOOK_SNIPPET}"
            return content
    except (OSError, UnicodeDecodeError):
        return None
