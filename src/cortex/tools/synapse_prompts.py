"""
Dynamic Synapse Prompts Registration

This module loads prompts from .cortex/synapse/prompts/ and registers them
as MCP prompts so they appear in Cursor chat interface.

Prompts are loaded synchronously at import time to enable decorator registration.
"""

import json
from pathlib import Path
from typing import cast

from cortex.server import mcp


def _get_synapse_prompts_path() -> Path | None:
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


def _load_prompts_manifest(prompts_path: Path) -> dict[str, object] | None:
    """Load prompts manifest synchronously."""
    manifest_path = prompts_path / "prompts-manifest.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _load_prompt_content(
    prompts_path: Path, category: str, filename: str
) -> str | None:
    """Load prompt file content synchronously."""
    # Prompts are in the root of prompts/ directory, not in category subdirectories
    prompt_file = prompts_path / filename
    if not prompt_file.exists():
        return None

    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _create_prompt_function(name: str, content: str, description: str) -> None:
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


def _register_synapse_prompts() -> None:
    """Load and register all Synapse prompts as MCP prompts."""
    prompts_path = _get_synapse_prompts_path()
    if not prompts_path:
        # Silently fail if Synapse prompts directory doesn't exist
        # This is expected if Synapse isn't set up yet
        return

    manifest = _load_prompts_manifest(prompts_path)
    if not manifest:
        # Manifest doesn't exist or is invalid
        return

    registered_count = 0

    categories = manifest.get("categories")
    if not isinstance(categories, dict):
        return

    # Iterate through categories and prompts
    for category_name, category_info in cast(dict[str, object], categories).items():
        if not isinstance(category_info, dict):
            continue

        prompts_list = category_info.get("prompts", [])
        if not isinstance(prompts_list, list):
            continue

        for prompt_info in prompts_list:
            if not isinstance(prompt_info, dict):
                continue

            filename = prompt_info.get("file")
            if not isinstance(filename, str):
                continue

            prompt_name = prompt_info.get(
                "name", filename.replace(".md", "").replace("-", "_")
            )
            if not isinstance(prompt_name, str):
                continue

            description = prompt_info.get("description", "")
            if not isinstance(description, str):
                description = ""

            # Load prompt content
            content = _load_prompt_content(prompts_path, category_name, filename)
            if not content:
                continue

            # Create sanitized function name
            func_name = prompt_name.lower().replace(" ", "_").replace("-", "_")
            func_name = "".join(
                c if c.isalnum() or c == "_" else "_" for c in func_name
            )

            # Register the prompt
            try:
                _create_prompt_function(func_name, content, description)
                registered_count += 1
            except Exception as e:
                # Log error but continue with other prompts
                from cortex.core.logging_config import logger

                logger.warning(f"Failed to register prompt {func_name}: {e}")
                continue

    # Log registration summary and verify
    if registered_count > 0:
        from cortex.core.logging_config import logger

        logger.info(f"Registered {registered_count} Synapse prompts")

        # Verify functions exist in module namespace
        registered_names = [
            name
            for name in globals()
            if name.startswith("commit_")
            or name.startswith("fix_")
            or name.startswith("review_")
            or name.startswith("run_")
        ]
        logger.debug(f"Registered prompt functions in namespace: {registered_names}")


# Register prompts at import time
_register_synapse_prompts()
