# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Lazy prompt registration — defers project-root-dependent setup to the first
``list_prompts`` call so that the correct project root (supplied by the MCP
client via ``roots/list``) is used instead of the CWD at server-start time.

Problem solved
--------------
When Cursor (or another IDE) launches the Cortex MCP server via ``uvx`` or an
absolute binary path, the working directory at process start is the user's home
directory — not the project the IDE has open.  Startup-time calls to
``get_project_root()`` therefore return an incorrect path, which causes:

1. ``get_prompts_paths()`` to find no ``.cortex/synapse/prompts/`` directory →
   synapse prompts are never registered.
2. ``should_mount_setup()`` to return ``True`` for every project (including
   fully configured ones) → spurious init/migrate prompts appear.

Solution
--------
:class:`LazyPromptRegistry` wraps all project-root-dependent registration
work behind an async lock.  The *first* client that calls ``list_prompts``
triggers :meth:`ensure_registered`, which:

1. Resolves the project root via :func:`resolve_project_root_async` — this
   uses the MCP ``roots/list`` capability when the client supports it, giving
   us the IDE's actual workspace path.
2. Re-runs ``register_synapse_prompts(project_root)`` and
   ``sync_cursor_agents(project_root)`` with the correct root.
3. Evaluates ``get_project_config_status(project_root)`` and registers
   ``initialize`` / ``migrate`` / ``populate_tiktoken_cache`` prompts only
   when the project actually needs them.
4. Sends a ``notifications/prompts/list_changed`` notification so the client
   refreshes its cached prompt list.

All subsequent ``list_prompts`` calls are no-ops (the flag is set after the
first successful run).

Fast-path for correct-CWD launches
-----------------------------------
When the server is launched from the project directory (e.g. ``python -m
cortex.main`` with the CWD inherited from the IDE), the startup-time
``register_synapse_prompts()`` call in ``prompts.py`` already succeeds.
:class:`LazyPromptRegistry` detects this via
``prompt_manager_has_synapse_prompts()`` and short-circuits without issuing
another ``roots/list`` round-trip or sending a list-changed notification.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import cast

from cortex.core.context_logging import MCPContext
from cortex.core.icon_helpers import create_emoji_icon
from cortex.core.models import ModelDict
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.core.synapse_submodule_startup import (
    try_sync_synapse_submodule_at_mcp_startup,
)
from cortex.server import mcp
from cortex.setup import should_mount_setup
from cortex.setup.post_edit_hook_runtime import apply_project_post_edit_hook
from cortex.tools.config import get_project_config_status
from cortex.tools.synapse.prompts import (
    create_prompt_function,
    register_synapse_prompts,
    sync_cursor_agents,
)
from cortex.tools.synapse.prompts_content import SYNAPSE_PROMPT_ICONS
from cortex.tools.synapse.prompts_paths import (
    load_prompt_content,
    load_prompts_manifest,
)
from cortex.wiki.layout import wiki_has_content, wiki_scaffold_present

logger = logging.getLogger(__name__)

_SETUP_PROMPT_ICONS: dict[str, str] = {
    "initialize": "🏗️",
    "migrate": "🔄",
    "populate_tiktoken_cache": "💾",
}

# ---------------------------------------------------------------------------
# Prompt content
#
# Imported inside each _register_*() helper (not at module level) to avoid
# importing cortex.setup.prompts at module-level.  That module calls
# get_project_config_status() and registers prompts as a side-effect when
# imported, which would fire with the wrong project root before the lazy
# registry has had a chance to resolve the correct one.
# ---------------------------------------------------------------------------


def _get_initialize_prompt() -> str:
    from cortex.setup.prompts import INITIALIZE_PROMPT

    return INITIALIZE_PROMPT


def _get_migrate_prompt() -> str:
    from cortex.setup.prompts import MIGRATE_PROMPT

    return MIGRATE_PROMPT


def _get_tiktoken_prompt() -> str:
    from cortex.setup.prompts import POPULATE_TIKTOKEN_CACHE_PROMPT

    return POPULATE_TIKTOKEN_CACHE_PROMPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synapse_prompt_names() -> frozenset[str]:
    """Return the set of expected synapse prompt names (values of SYNAPSE_PROMPT_ICONS)."""
    return frozenset(SYNAPSE_PROMPT_ICONS.keys())


def registered_prompt_names() -> frozenset[str]:
    """Return names of all prompts currently registered on the MCP server."""
    # FastMCP's _prompt_manager.list_prompts() is synchronous.
    return frozenset(p.name for p in mcp._prompt_manager.list_prompts())  # type: ignore[attr-defined]


def _init_wiki_manifest_description(synapse_prompts_dir: Path) -> str:
    """Return the manifest description for init-wiki, or a short fallback."""
    fallback = (
        "Seed .cortex/wiki from existing project docs, run ingest snapshots, "
        "and rebuild index.md."
    )
    manifest = load_prompts_manifest(synapse_prompts_dir)
    if manifest is None:
        return fallback
    categories = manifest.get("categories")
    if not isinstance(categories, dict):
        return fallback
    general = categories.get("general")
    if not isinstance(general, dict):
        return fallback
    prompts_raw = general.get("prompts", [])
    if not isinstance(prompts_raw, list):
        return fallback
    for entry_raw in prompts_raw:
        if not isinstance(entry_raw, dict):
            continue
        entry = cast(ModelDict, entry_raw)
        if entry.get("file") != "init-wiki.md":
            continue
        desc = entry.get("description")
        if isinstance(desc, str) and desc.strip():
            return desc.strip()
    return fallback


def _register_init_wiki_prompt_if_needed(project_root: Path) -> bool:
    """Register ``init_wiki`` when the wiki scaffold exists and has no pages yet."""
    if "init_wiki" in registered_prompt_names():
        return False
    if not wiki_scaffold_present(project_root):
        return False
    if wiki_has_content(project_root):
        return False

    from cortex.core.path_resolver import CortexResourceType, get_cortex_path

    synapse_prompts_dir = (
        get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
        / "synapse"
        / "prompts"
    )
    if not synapse_prompts_dir.is_dir():
        return False
    content = load_prompt_content(synapse_prompts_dir, "general", "init-wiki.md")
    if not content:
        return False
    description = _init_wiki_manifest_description(synapse_prompts_dir)
    create_prompt_function("init_wiki", content, description, None)
    logger.debug("lazy_prompt_registration: registered init_wiki for %s", project_root)
    return True


def prompt_manager_has_synapse_prompts() -> bool:
    """Return True when at least one expected synapse prompt is already registered."""
    registered = registered_prompt_names()
    return bool(registered & _synapse_prompt_names())


def _register_initialize_prompt(project_root: Path) -> None:
    @mcp.prompt(icons=[create_emoji_icon(_SETUP_PROMPT_ICONS["initialize"])])
    def initialize() -> str:
        """Complete project initialization.

        Creates:
        - .cortex/ directory structure (memory-bank, plans, config)
        - Memory bank with 7 core files
        - Cursor integration (symlinks + mcp.json)
        - Optional Synapse setup with default URL
        """
        _ = apply_project_post_edit_hook(project_root)
        return _get_initialize_prompt()

    _ = initialize  # pyright: ignore[reportUnusedFunction]


def _register_migrate_prompt(project_root: Path) -> None:
    @mcp.prompt(icons=[create_emoji_icon(_SETUP_PROMPT_ICONS["migrate"])])
    def migrate() -> str:
        """Migrate legacy structure to new .cortex/ structure.

        Steps:
        1. Initialize new .cortex/ structure
        2. Migrate legacy files
        3. Remove legacy directories
        """
        _ = apply_project_post_edit_hook(project_root)
        return _get_migrate_prompt()

    _ = migrate  # pyright: ignore[reportUnusedFunction]


def _register_tiktoken_prompt() -> None:
    @mcp.prompt(
        icons=[create_emoji_icon(_SETUP_PROMPT_ICONS["populate_tiktoken_cache"])]
    )
    def populate_tiktoken_cache() -> str:
        """Populate bundled tiktoken cache with encoding files for offline operation."""
        return _get_tiktoken_prompt()

    _ = populate_tiktoken_cache  # pyright: ignore[reportUnusedFunction]


def register_setup_prompts(status: object, project_root: Path) -> None:
    """Register whichever setup prompts the project needs."""
    from cortex.tools.config import ProjectConfigStatus

    cfg: ProjectConfigStatus = status  # type: ignore[assignment]
    already = registered_prompt_names()

    if (
        not cfg.memory_bank_initialized
        and not cfg.structure_configured
        and not cfg.migration_needed
        and "initialize" not in already
    ):
        _register_initialize_prompt(project_root)

    if cfg.migration_needed and "migrate" not in already:
        _register_migrate_prompt(project_root)

    if not cfg.tiktoken_cache_available and "populate_tiktoken_cache" not in already:
        _register_tiktoken_prompt()


async def _run_startup_repair(project_root: Path) -> None:
    """Run startup repair and log a summary if anything was changed."""
    try:
        from cortex.structure.lifecycle.startup_repair import repair_project_setup

        report = await repair_project_setup(project_root)
        if not report.skipped:
            logger.info("startup_repair: %s", report.model_dump())
    except Exception as exc:
        logger.warning("startup_repair: failed: %s", exc)


async def _resolve_project_root(ctx: MCPContext | None) -> Path | None:
    try:
        return await resolve_project_root_async(None, ctx)
    except Exception as exc:
        logger.warning(
            "lazy_prompt_registration: root resolution failed (%s), skipping lazy registration",
            exc,
        )
        return None


def _try_sync_synapse_prompts(project_root: Path, already_has_synapse: bool) -> None:
    if already_has_synapse:
        return
    try:
        register_synapse_prompts(project_root)
        sync_cursor_agents(project_root)
    except Exception as exc:
        logger.warning("lazy_prompt_registration: synapse registration failed: %s", exc)


def _register_setup_if_needed(project_root: Path) -> bool:
    try:
        status = get_project_config_status(project_root)
        if not should_mount_setup(status):
            return False
        register_setup_prompts(status, project_root)
        logger.debug(
            "lazy_prompt_registration: registered setup prompts for %s",
            project_root,
        )
        return True
    except Exception as exc:
        logger.warning(
            "lazy_prompt_registration: setup prompt registration failed: %s",
            exc,
        )
        return False


async def _notify_prompt_list_changed_if_needed(
    ctx: MCPContext | None, needs_notify: bool
) -> None:
    if not needs_notify or ctx is None:
        return
    session = getattr(ctx, "session", None)
    if session is None or not hasattr(session, "send_prompt_list_changed"):
        return
    try:
        await session.send_prompt_list_changed()
        logger.debug("lazy_prompt_registration: sent prompt_list_changed notification")
    except Exception as exc:
        logger.debug(
            "lazy_prompt_registration: prompt_list_changed notification failed: %s",
            exc,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class LazyPromptRegistry:
    """Thread-safe, once-only prompt registration triggered on first list_prompts.

    Designed to be a singleton (see :data:`_registry` below).
    """

    def __init__(self) -> None:
        self._registered: bool = False
        self._lock: asyncio.Lock | None = None  # created on first use (event-loop safe)

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def ensure_registered(self, ctx: MCPContext | None) -> None:
        """Ensure all project-root-dependent prompts are registered exactly once.

        Safe to call from any async context; subsequent calls return immediately.
        """
        if self._registered:
            return

        async with self._get_lock():
            if self._registered:
                return
            self._registered = True
            await self.do_register(ctx)

    @property
    def registered(self) -> bool:
        """Public view of whether setup prompts were registered."""
        return self._registered

    async def do_register(self, ctx: MCPContext | None) -> None:
        """Public wrapper around the internal registration routine."""
        await self._do_register(ctx)

    async def _do_register(self, ctx: MCPContext | None) -> None:
        """Resolve the project root and register all prompts."""
        project_root = await _resolve_project_root(ctx)
        if project_root is None:
            return

        logger.debug("lazy_prompt_registration: resolved project root %s", project_root)

        # Best-effort synapse submodule sync (stash/update/pop) using correct root
        sync_result = try_sync_synapse_submodule_at_mcp_startup(project_root)
        logger.debug(
            "synapse_submodule_startup: %s", sync_result.model_dump(mode="json")
        )

        already_has_synapse = prompt_manager_has_synapse_prompts()
        _try_sync_synapse_prompts(project_root, already_has_synapse)
        await _run_startup_repair(project_root)
        wiki_init_registered = _register_init_wiki_prompt_if_needed(project_root)
        setup_registered = _register_setup_if_needed(project_root)
        await _notify_prompt_list_changed_if_needed(
            ctx, (not already_has_synapse) or setup_registered or wiki_init_registered
        )


# Module-level singleton — shared across all list_prompts calls in one server
# process.
registry = LazyPromptRegistry()


async def ensure_prompts_registered(ctx: MCPContext | None) -> None:
    """Module-level entry point used by the list_prompts hook in server.py."""
    await registry.ensure_registered(ctx)
