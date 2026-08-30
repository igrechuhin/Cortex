"""Register Synapse and project prompts on the MCP server (facade module namespace)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import cast

from cortex.core.icon_helpers import create_emoji_icon
from cortex.core.models import JsonValue, ModelDict
from cortex.server import mcp
from cortex.tools.synapse.prompts_content import (
    DEFAULT_PROMPT_ICON,
    SYNAPSE_PROMPT_ICONS,
)
from cortex.tools.synapse.prompts_paths import (
    get_prompts_paths,
    load_prompt_content,
    load_prompts_manifest,
)


def _emoji_for_prompt(func_name: str) -> str:
    """Return emoji for a prompt by name; fallback to default."""
    return SYNAPSE_PROMPT_ICONS.get(func_name, DEFAULT_PROMPT_ICON)


def create_prompt_function(
    facade: ModuleType,
    name: str,
    content: str,
    description: str,
    icon_emoji: str | None = None,
) -> None:
    """Create and register a prompt function on the facade module namespace."""
    g = facade.__dict__
    if "_prompt_contents" not in g:
        g["_prompt_contents"] = {}
    cast(dict[str, str], g["_prompt_contents"])[name] = content

    emoji = icon_emoji if icon_emoji else _emoji_for_prompt(name)
    icon = create_emoji_icon(emoji)

    def prompt_func() -> str:
        """Return prompt content."""
        return cast(dict[str, str], g["_prompt_contents"])[name]

    prompt_func.__name__ = name
    prompt_func.__doc__ = description

    decorated = mcp.prompt(icons=[icon])(prompt_func)
    g[name] = decorated


def _description_and_icon(prompt_info: ModelDict) -> tuple[str, str | None]:
    """Extract description string and optional icon emoji from a prompt info dict.

    Returns empty string for description and None for icon when the fields are
    absent or not strings.
    """
    raw_desc = prompt_info.get("description", "")
    description = raw_desc if isinstance(raw_desc, str) else ""
    icon_raw = prompt_info.get("icon")
    icon = icon_raw if isinstance(icon_raw, str) else None
    return description, icon


def _mcp_func_name(prompt_name: str) -> str:
    """Convert a prompt name to a valid Python/MCP function identifier.

    Lowercases the name, replaces spaces and hyphens with underscores, and
    replaces any remaining non-alphanumeric characters with underscores.
    """
    base = prompt_name.lower().replace(" ", "_").replace("-", "_")
    return "".join(c if c.isalnum() or c == "_" else "_" for c in base)


def _try_publish_prompt(
    facade: ModuleType,
    func_name: str,
    content: str,
    description: str,
    icon_emoji: str | None,
) -> int:
    """Register via the facade hook (patchable as ``prompts.create_prompt_function``)."""
    try:
        pub_create = getattr(facade, "create_prompt_function")
        pub_create(func_name, content, description, icon_emoji)
        return 1
    except Exception as e:
        from cortex.core.logging_config import logger

        logger.warning(f"Failed to register prompt {func_name}: {e}")
        return 0


# Appended to a workflow redirect when the manifest entry sets ``refresh_roadmap_page``.
#
# A prompt superseded by a ``.wf.js`` script never delivers its own markdown, so a step written
# into (for example) ``commit.md`` would never run. The workflow's own subagents cannot publish
# either — the Artifact tool is not in their toolsets — so the refresh has to be carried out by
# the orchestrating session once the script returns. That is what this instruction addresses.
_ROADMAP_PAGE_REFRESH = (
    "\n\nAfter the workflow completes, follow"
    " `.cortex/synapse/prompts/roadmap-page.md` to refresh the operator's visual roadmap,"
    " because this pipeline can change `roadmap.md` and a page that silently lags the roadmap"
    " is worse than none. Skip it only if the run made no memory-bank changes, and say so."
)


def _workflow_redirect_content(
    script_path: Path, *, refresh_roadmap_page: bool = False
) -> str:
    """Return prompt content that tells Claude Code to run a Workflow script."""
    content = (
        f'Use the Workflow tool with `scriptPath: "{script_path}"`'
        f" to run this pipeline as a deterministic workflow script.\n\n"
        f"Do not interpret this as prose instructions — invoke the Workflow tool directly."
    )
    if refresh_roadmap_page:
        content += _ROADMAP_PAGE_REFRESH
    return content


def _try_workflow_redirect(
    facade: ModuleType,
    prompt_info: ModelDict,
    prompts_path: Path,
    prompt_name: str,
    description: str,
    icon_emoji: str | None,
) -> int | None:
    """Publish a Workflow-script redirect prompt, or None when not applicable."""
    superseded_by = prompt_info.get("superseded_by")
    if not (isinstance(superseded_by, str) and superseded_by.endswith(".wf.js")):
        return None
    script_path = prompts_path / superseded_by
    if not script_path.exists():
        return None
    content = _workflow_redirect_content(
        script_path,
        refresh_roadmap_page=prompt_info.get("refresh_roadmap_page") is True,
    )
    return _try_publish_prompt(
        facade, _mcp_func_name(prompt_name), content, description, icon_emoji
    )


def process_prompt_info(
    facade: ModuleType,
    prompt_info: ModelDict,
    prompts_path: Path,
    category_name: str,
) -> int:
    """Process one manifest entry; return 0 or 1 prompts registered."""
    if prompt_info.get("internal") is True:
        return 0
    filename = prompt_info.get("file")
    if not isinstance(filename, str):
        return 0
    # AI: init-wiki is registered lazily when the wiki scaffold exists but has no
    # pages — see cortex.setup.lazy_prompt_registration._register_init_wiki_prompt_if_needed.
    if filename == "init-wiki.md":
        return 0
    prompt_name = prompt_info.get("name", filename.replace(".md", "").replace("-", "_"))
    if not isinstance(prompt_name, str):
        return 0
    description, icon_emoji = _description_and_icon(prompt_info)

    redirected = _try_workflow_redirect(
        facade, prompt_info, prompts_path, prompt_name, description, icon_emoji
    )
    if redirected is not None:
        return redirected

    content = load_prompt_content(prompts_path, category_name, filename)
    if not content:
        return 0
    return _try_publish_prompt(
        facade, _mcp_func_name(prompt_name), content, description, icon_emoji
    )


def log_registration_summary(facade: ModuleType, registered_count: int) -> None:
    """Log registration summary and verify functions exist."""
    if registered_count > 0:
        from cortex.core.logging_config import logger

        logger.info(f"Registered {registered_count} Synapse prompts")
        g = facade.__dict__
        registered_names = [
            name
            for name in g
            if name.startswith("commit_")
            or name.startswith("fix_")
            or name.startswith("review_")
            or name.startswith("run_")
        ]
        logger.debug(f"Registered prompt functions in namespace: {registered_names}")


def register_prompts_from_path(facade: ModuleType, prompts_path: Path) -> int:
    """Load and register prompts from a single path.

    Returns:
        Number of prompts registered from this path.
    """
    manifest = load_prompts_manifest(prompts_path)
    if not manifest:
        return 0

    manifest_dict = cast(ModelDict, manifest.model_dump(mode="json"))
    categories = manifest_dict.get("categories")
    if not isinstance(categories, dict):
        return 0

    registered_count = 0
    for category_name, category_info in cast(ModelDict, categories).items():
        if not isinstance(category_info, dict):
            continue

        prompts_list_raw: JsonValue = cast(ModelDict, category_info).get("prompts", [])
        if not isinstance(prompts_list_raw, list):
            continue

        for prompt_info_raw in cast(list[JsonValue], prompts_list_raw):
            if isinstance(prompt_info_raw, dict):
                prompt_info = cast(ModelDict, prompt_info_raw)
                registered_count += process_prompt_info(
                    facade, prompt_info, prompts_path, category_name
                )

    return registered_count


def register_synapse_prompts_impl(
    facade: ModuleType, project_root: Path | None = None
) -> None:
    """Load and register all prompts from Synapse and project-specific directories.

    Args:
        facade: The facade module on whose namespace prompts are registered.
        project_root: Explicit project root. When ``None``, falls back to the
            CWD/module-anchor heuristic inside :func:`get_prompts_paths`.
    """
    prompts_paths = get_prompts_paths(project_root)
    if not prompts_paths:
        return

    total_registered = 0
    for prompts_path in prompts_paths:
        registered = register_prompts_from_path(facade, prompts_path)
        total_registered += registered

    log_registration_summary(facade, total_registered)


def register_synapse_prompts_for_facade(
    facade: ModuleType | None = None,
    project_root: Path | None = None,
) -> None:
    """Register prompts; defaults to the ``cortex.tools.synapse.prompts`` module.

    Args:
        facade: The facade module. Defaults to ``cortex.tools.synapse.prompts``.
        project_root: Explicit project root passed to :func:`register_synapse_prompts_impl`.
    """
    mod = facade or sys.modules["cortex.tools.synapse.prompts"]
    register_synapse_prompts_impl(mod, project_root)
