# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Startup repair — idempotent structure validation and repair on server start.

Called once per server session (from the lazy prompt registry) after the
project root is resolved via MCP ``roots/list``.  Repairs drift silently;
never raises — failures are collected in the report and logged by the caller.

What is repaired
----------------
- Missing or partial ``.cortex/`` directory structure (dirs + config file).
- Broken or missing ``.cursor/`` symlinks.
- Missing Cortex transient-file entries in ``.gitignore`` (git repos only).

What is NOT repaired (requires human intent)
--------------------------------------------
- Missing memory-bank core files  → use ``/cortex/initialize`` prompt.
- Legacy layout migration          → use ``/cortex/migrate`` prompt.
- Tiktoken cache                   → use ``/cortex/populate_tiktoken_cache``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.structure.lifecycle.setup import StructureSetup
from cortex.structure.lifecycle.symlinks import CursorSymlinkManager
from cortex.structure.structure_config import StructureConfig
from cortex.tools.config.status import (
    check_cursor_integration,
    check_structure_configured,
)

logger = logging.getLogger(__name__)

GITIGNORE_MARKER = ".cortex/.session/"
AGENT_SYNC_MARKER = ".claude/"
_GITIGNORE_BLOCK = (
    "\n# Cortex MCP (transient/generated files)\n"
    ".cortex/.session/\n"
    ".cortex/.cache/\n"
    ".cortex/history/\n"
    ".cortex-backup-*/\n"
    "\n# Cortex agent sync outputs (generated at MCP startup — do not commit)\n"
    ".claude/\n"
    ".cursor/agents/\n"
)


class StartupRepairReport(BaseModel):
    """Result of a startup repair pass."""

    model_config = ConfigDict(extra="forbid")

    structure_repaired: bool = Field(
        default=False, description="Dirs/config were created or restored."
    )
    symlinks_repaired: bool = Field(
        default=False, description="Cursor symlinks were recreated."
    )
    gitignore_updated: bool = Field(
        default=False, description="Cortex entries appended to .gitignore."
    )
    errors: list[str] = Field(
        default_factory=list, description="Non-fatal errors encountered."
    )
    skipped: bool = Field(
        default=False,
        description="True when everything was already healthy; no changes made.",
    )


def _needs_structure(project_root: Path) -> bool:
    cortex_dir = project_root / ".cortex"
    return not check_structure_configured(cortex_dir)


def _needs_symlinks(project_root: Path) -> bool:
    cortex_dir = project_root / ".cortex"
    cursor_dir = project_root / ".cursor"
    return not check_cursor_integration(cursor_dir, cortex_dir)


def _needs_gitignore(project_root: Path) -> bool:
    """Return True if the project is a git repo and .gitignore is missing entries."""
    if not (project_root / ".git").exists():
        return False
    gitignore = project_root / ".gitignore"
    if not gitignore.is_file():
        return True
    text = gitignore.read_text(encoding="utf-8")
    return GITIGNORE_MARKER not in text or AGENT_SYNC_MARKER not in text


async def _repair_structure(project_root: Path, report: StartupRepairReport) -> None:
    try:
        config = StructureConfig(project_root)
        setup = StructureSetup(config)
        result = await setup.create_structure()
        if result.created_directories or result.created_files:
            report.structure_repaired = True
            logger.debug(
                "startup_repair: structure created dirs=%s files=%s",
                result.created_directories,
                result.created_files,
            )
        report.errors.extend(result.errors)
    except Exception as exc:
        report.errors.append(f"structure repair failed: {exc}")


def _repair_symlinks(project_root: Path, report: StartupRepairReport) -> None:
    try:
        config = StructureConfig(project_root)
        manager = CursorSymlinkManager(config)
        result = manager.setup_cursor_integration()
        if result.symlinks_created:
            report.symlinks_repaired = True
            logger.debug(
                "startup_repair: symlinks recreated: %s",
                [s.link for s in result.symlinks_created],
            )
        report.errors.extend(result.errors)
    except Exception as exc:
        report.errors.append(f"symlink repair failed: {exc}")


def _repair_gitignore(project_root: Path, report: StartupRepairReport) -> None:
    try:
        gitignore = project_root / ".gitignore"
        existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
        _ = gitignore.write_text(existing + _GITIGNORE_BLOCK, encoding="utf-8")
        report.gitignore_updated = True
        logger.debug("startup_repair: appended Cortex entries to .gitignore")
    except Exception as exc:
        report.errors.append(f"gitignore repair failed: {exc}")


async def repair_project_setup(project_root: Path) -> StartupRepairReport:
    """Validate and repair Cortex project setup.

    Idempotent — safe to call on every server start.  Never raises.

    Args:
        project_root: Resolved project root path.

    Returns:
        :class:`StartupRepairReport` describing what (if anything) was changed.
    """
    report = StartupRepairReport()

    needs_structure = _needs_structure(project_root)
    needs_symlinks = _needs_symlinks(project_root)
    needs_gitignore = _needs_gitignore(project_root)

    if not needs_structure and not needs_symlinks and not needs_gitignore:
        report.skipped = True
        return report

    if needs_structure:
        try:
            await _repair_structure(project_root, report)
        except Exception as exc:
            report.errors.append(f"structure repair failed: {exc}")

    if needs_symlinks:
        try:
            _repair_symlinks(project_root, report)
        except Exception as exc:
            report.errors.append(f"symlink repair failed: {exc}")

    if needs_gitignore:
        try:
            _repair_gitignore(project_root, report)
        except Exception as exc:
            report.errors.append(f"gitignore repair failed: {exc}")

    return report
