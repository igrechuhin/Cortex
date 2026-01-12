"""
Dynamic Synapse Prompts Registration

This module loads prompts from .cortex/synapse/prompts/ and registers them
as MCP prompts so they appear in Cursor chat interface.

Prompts are loaded synchronously at import time to enable decorator registration.
"""

import json
from pathlib import Path
from typing import cast

from cortex.server import (
    mcp,  # noqa: F401  # pyright: ignore[reportUnusedImport]  # Used in exec() string
)


def get_synapse_prompts_path() -> Path | None:
    """Get path to Synapse prompts directory.

    Walks up the directory tree from current working directory to find
    .cortex/synapse/prompts directory. This works when MCP server is run
    from project root or any subdirectory.

    Also tries to find it relative to the module file location as fallback.
    """
    # Try current working directory first (works when server runs from project root)
    current = Path.cwd()
    for path in [current, *current.parents]:
        prompts_path = path / ".cortex" / "synapse" / "prompts"
        if prompts_path.exists() and prompts_path.is_dir():
            return prompts_path

    # Fallback: try relative to this module's location
    # This helps when CWD is not the project root
    module_file = Path(__file__)
    # Go up from src/cortex/tools/synapse_prompts.py to project root
    for path in [
        module_file.parent.parent.parent.parent,
        *module_file.parent.parent.parent.parent.parents,
    ]:
        prompts_path = path / ".cortex" / "synapse" / "prompts"
        if prompts_path.exists() and prompts_path.is_dir():
            return prompts_path

    return None


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


def register_synapse_prompts() -> None:
    """Load and register all Synapse prompts as MCP prompts."""
    prompts_path = get_synapse_prompts_path()
    if not prompts_path:
        return

    manifest = load_prompts_manifest(prompts_path)
    if not manifest:
        return

    categories = manifest.get("categories")
    if not isinstance(categories, dict):
        return

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

    log_registration_summary(registered_count)


# Register prompts at import time
register_synapse_prompts()
