"""Resolve prompt directories and load manifest / prompt file content."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.core.models import JsonDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def _paths_anchor() -> Path:
    """Return this module's path (tests may patch this for discovery fallbacks)."""
    return Path(__file__)


def get_prompts_paths() -> list[Path]:
    """Get paths to all prompts directories.

    Walks up the directory tree from current working directory to find
    prompts directories. Returns paths for both:
    - .cortex/synapse/prompts/ (shared Synapse prompts)
    - .cortex/prompts/ (project-specific prompts)

    Also tries to find them relative to the module file location as fallback.
    """
    found_paths: list[Path] = []

    # Directories to check (relative to .cortex/)
    prompt_dirs = ["synapse/prompts", "prompts"]

    # Try current working directory first (works when server runs from project root)
    current = Path.cwd()
    for path in [current, *current.parents]:
        cortex_root = get_cortex_path(path, CortexResourceType.CORTEX_DIR)
        for prompt_dir in prompt_dirs:
            prompts_path = cortex_root / prompt_dir
            if prompts_path.exists() and prompts_path.is_dir():
                if prompts_path not in found_paths:
                    found_paths.append(prompts_path)

    # Fallback: try relative to this module's location
    # This helps when CWD is not the project root
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
    """Get path to Synapse prompts directory (for backwards compatibility)."""
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
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None
