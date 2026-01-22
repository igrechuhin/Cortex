"""
Dynamic Prompts Registration

This module loads prompts from two locations and registers them as MCP prompts:
1. .cortex/synapse/prompts/ - Shared prompts from Synapse (language-agnostic)
2. .cortex/prompts/ - Project-specific prompts (e.g., Cortex MCP tools)

Prompts are loaded synchronously at import time to enable decorator registration.
"""

import json
from pathlib import Path
from typing import cast

from cortex.server import (
    mcp,  # noqa: F401  # pyright: ignore[reportUnusedImport]  # Used in exec() string
)


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
        for prompt_dir in prompt_dirs:
            prompts_path = path / ".cortex" / prompt_dir
            if prompts_path.exists() and prompts_path.is_dir():
                if prompts_path not in found_paths:
                    found_paths.append(prompts_path)

    # Fallback: try relative to this module's location
    # This helps when CWD is not the project root
    module_file = Path(__file__)
    # Go up from src/cortex/tools/synapse_prompts.py to project root
    for path in [
        module_file.parent.parent.parent.parent,
        *module_file.parent.parent.parent.parent.parents,
    ]:
        for prompt_dir in prompt_dirs:
            prompts_path = path / ".cortex" / prompt_dir
            if prompts_path.exists() and prompts_path.is_dir():
                if prompts_path not in found_paths:
                    found_paths.append(prompts_path)

    return found_paths


def get_synapse_prompts_path() -> Path | None:
    """Get path to Synapse prompts directory (for backwards compatibility)."""
    paths = get_prompts_paths()
    for path in paths:
        if "synapse" in str(path):
            return path
    return paths[0] if paths else None


def load_prompts_manifest(prompts_path: Path) -> dict[str, object] | None:
    """Load prompts manifest synchronously."""
    manifest_path = prompts_path / "prompts-manifest.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_prompt_content(prompts_path: Path, category: str, filename: str) -> str | None:
    """Load prompt file content synchronously."""
    # Prompts are in the root of prompts/ directory, not in category subdirectories
    prompt_file = prompts_path / filename
    if not prompt_file.exists():
        return None

    try:
        with open(prompt_file, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def create_prompt_function(name: str, content: str, description: str) -> None:
    """Create and register a prompt function dynamically.

    Stores content in module-level dict and creates function that references it,
    then uses exec() to apply the decorator at module level.
    """
    # Store content in module-level dict to avoid closure issues
    if "_prompt_contents" not in globals():
        globals()["_prompt_contents"] = {}
    globals()["_prompt_contents"][name] = content

    # Create function definition with decorator using exec()
    # Function references the module-level dict to get the content
    func_code = f'''@mcp.prompt()
def {name}() -> str:
    """{description}"""
    return _prompt_contents["{name}"]
'''

    # Execute in module globals so the function is created at module level
    exec(func_code, globals())


def process_prompt_info(
    prompt_info: dict[str, object], prompts_path: Path, category_name: str
) -> int:
    """Process a single prompt info and register it.

    Returns:
        Number of prompts registered (0 or 1)
    """
    filename = prompt_info.get("file")
    if not isinstance(filename, str):
        return 0

    prompt_name = prompt_info.get("name", filename.replace(".md", "").replace("-", "_"))
    if not isinstance(prompt_name, str):
        return 0

    description = prompt_info.get("description", "")
    if not isinstance(description, str):
        description = ""

    content = load_prompt_content(prompts_path, category_name, filename)
    if not content:
        return 0

    func_name = prompt_name.lower().replace(" ", "_").replace("-", "_")
    func_name = "".join(c if c.isalnum() or c == "_" else "_" for c in func_name)

    try:
        create_prompt_function(func_name, content, description)
        return 1
    except Exception as e:
        from cortex.core.logging_config import logger

        logger.warning(f"Failed to register prompt {func_name}: {e}")
        return 0


def log_registration_summary(registered_count: int) -> None:
    """Log registration summary and verify functions exist."""
    if registered_count > 0:
        from cortex.core.logging_config import logger

        logger.info(f"Registered {registered_count} Synapse prompts")
        registered_names = [
            name
            for name in globals()
            if name.startswith("commit_")
            or name.startswith("fix_")
            or name.startswith("review_")
            or name.startswith("run_")
        ]
        logger.debug(f"Registered prompt functions in namespace: {registered_names}")


def register_prompts_from_path(prompts_path: Path) -> int:
    """Load and register prompts from a single path.

    Returns:
        Number of prompts registered from this path.
    """
    manifest = load_prompts_manifest(prompts_path)
    if not manifest:
        return 0

    categories = manifest.get("categories")
    if not isinstance(categories, dict):
        return 0

    registered_count = 0
    for category_name, category_info in cast(dict[str, object], categories).items():
        if not isinstance(category_info, dict):
            continue

        prompts_list_raw = cast(dict[str, object], category_info).get("prompts", [])
        if not isinstance(prompts_list_raw, list):
            continue

        prompts_list = cast(list[object], prompts_list_raw)
        for prompt_info_raw in prompts_list:
            if isinstance(prompt_info_raw, dict):
                prompt_info = cast(dict[str, object], prompt_info_raw)
                registered_count += process_prompt_info(
                    prompt_info, prompts_path, category_name
                )

    return registered_count


def register_synapse_prompts() -> None:
    """Load and register all prompts from Synapse and project-specific directories."""
    prompts_paths = get_prompts_paths()
    if not prompts_paths:
        return

    total_registered = 0
    for prompts_path in prompts_paths:
        registered = register_prompts_from_path(prompts_path)
        total_registered += registered

    log_registration_summary(total_registered)


# Register prompts at import time
register_synapse_prompts()
