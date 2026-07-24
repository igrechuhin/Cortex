# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Cleanup of leftover ``.cursor/`` artifacts from older Cortex versions.

Cortex no longer generates or maintains a ``.cursor/`` workspace (Cursor IDE
integration was removed). Projects that adopted an earlier Cortex version may
still have Cortex-generated artifacts sitting under ``.cursor/``: symlinks
into ``.cortex/`` (``memory-bank``, ``plans``, ``synapse``), a synced
``agents/`` directory, and a generated ``mcp_config.json``/``mcp.json``.

This module removes only the specific items Cortex itself is known to have
created, so a project that separately uses Cursor IDE for unrelated reasons
does not have unrelated content deleted from under it:

- ``memory-bank``, ``plans``, ``synapse`` — removed only if they are symlinks
  (never a real directory, even if empty).
- ``agents/*.md`` — removed only for filenames matching Cortex's known
  Synapse agent set.
- ``mcp_config.json`` / ``mcp.json`` — removed only when the file parses as
  JSON whose only ``mcpServers`` entry is ``cortex`` (i.e. it was generated
  by Cortex's own setup prompt, not hand-authored for other MCP servers).

If ``.cursor/`` becomes empty after removing known artifacts, the directory
itself is removed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.path_resolver import get_legacy_cursor_dir_path
from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID

logger = logging.getLogger(__name__)

_LEGACY_SYMLINK_NAMES: tuple[str, ...] = ("memory-bank", "plans", "synapse")
_LEGACY_MCP_CONFIG_NAMES: tuple[str, ...] = ("mcp_config.json", "mcp.json")


class _McpServerConfig(BaseModel):
    """Minimal shape of a single ``mcpServers`` entry; fields are irrelevant here."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)


class _McpConfigFile(BaseModel):
    """Minimal shape of an ``mcp.json`` / ``mcp_config.json`` file."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    mcpServers: dict[str, _McpServerConfig] = Field(default_factory=dict)  # noqa: N815


class LegacyCursorCleanupReport(BaseModel):
    """Result of a legacy ``.cursor/`` artifact cleanup pass."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    removed_symlinks: list[str] = Field(
        default_factory=list, description="Cortex-generated symlinks removed."
    )
    removed_agent_files: list[str] = Field(
        default_factory=list, description="Synced agent files removed."
    )
    removed_mcp_configs: list[str] = Field(
        default_factory=list, description="Cortex-only mcp.json files removed."
    )
    removed_directory: bool = Field(
        default=False, description="True when the now-empty .cursor/ dir was removed."
    )
    errors: list[str] = Field(
        default_factory=list, description="Non-fatal errors encountered."
    )

    @property
    def changed(self) -> bool:
        """True when any artifact was actually removed."""
        return bool(
            self.removed_symlinks
            or self.removed_agent_files
            or self.removed_mcp_configs
            or self.removed_directory
        )


def _known_agent_file_names(cursor_dir: Path) -> frozenset[str]:
    """Return the set of agent filenames Cortex would have synced.

    Sourced from ``.cortex/synapse/claude-agents/`` (the Claude Code agent
    source of truth) so this stays correct without a second hardcoded list.
    """
    synapse_agents_dir = cursor_dir.parent / ".cortex" / "synapse" / "claude-agents"
    if not synapse_agents_dir.is_dir():
        return frozenset()
    return frozenset(f.name for f in synapse_agents_dir.glob("*.md"))


def _remove_legacy_symlinks(
    cursor_dir: Path, report: LegacyCursorCleanupReport
) -> None:
    for name in _LEGACY_SYMLINK_NAMES:
        candidate = cursor_dir / name
        if not candidate.is_symlink():
            continue
        try:
            candidate.unlink()
            report.removed_symlinks.append(str(candidate))
        except OSError as exc:
            report.errors.append(f"failed to remove symlink {candidate}: {exc}")


def _remove_legacy_agent_files(
    cursor_dir: Path, report: LegacyCursorCleanupReport
) -> None:
    agents_dir = cursor_dir / "agents"
    if not agents_dir.is_dir():
        return

    known_names = _known_agent_file_names(cursor_dir)
    for agent_file in sorted(agents_dir.glob("*.md")):
        if agent_file.name not in known_names:
            continue
        try:
            agent_file.unlink()
            report.removed_agent_files.append(str(agent_file))
        except OSError as exc:
            report.errors.append(f"failed to remove agent file {agent_file}: {exc}")

    try:
        if agents_dir.is_dir() and not any(agents_dir.iterdir()):
            agents_dir.rmdir()
    except OSError as exc:
        report.errors.append(f"failed to remove empty {agents_dir}: {exc}")


def _is_cortex_only_mcp_config(path: Path) -> bool:
    try:
        config = _McpConfigFile.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        return False
    return list(config.mcpServers.keys()) == ["cortex"]


def _remove_legacy_mcp_configs(
    cursor_dir: Path, report: LegacyCursorCleanupReport
) -> None:
    for name in _LEGACY_MCP_CONFIG_NAMES:
        candidate = cursor_dir / name
        if not candidate.is_file() or not _is_cortex_only_mcp_config(candidate):
            continue
        try:
            candidate.unlink()
            report.removed_mcp_configs.append(str(candidate))
        except OSError as exc:
            report.errors.append(f"failed to remove {candidate}: {exc}")


def _remove_directory_if_empty(
    cursor_dir: Path, report: LegacyCursorCleanupReport
) -> None:
    try:
        if cursor_dir.is_dir() and not any(cursor_dir.iterdir()):
            cursor_dir.rmdir()
            report.removed_directory = True
    except OSError as exc:
        report.errors.append(f"failed to remove empty {cursor_dir}: {exc}")


def cleanup_legacy_cursor_artifacts(project_root: Path) -> LegacyCursorCleanupReport:
    """Remove leftover Cortex-generated ``.cursor/`` artifacts, if any.

    Safe to call unconditionally and repeatedly: does nothing when no
    ``.cursor/`` directory exists, and only ever removes items Cortex is
    confident it generated itself (see module docstring).

    Args:
        project_root: Root directory of the host project.

    Returns:
        Report describing what (if anything) was removed.
    """
    report = LegacyCursorCleanupReport()
    cursor_dir = get_legacy_cursor_dir_path(project_root)

    if not cursor_dir.is_dir():
        return report

    _remove_legacy_symlinks(cursor_dir, report)
    _remove_legacy_agent_files(cursor_dir, report)
    _remove_legacy_mcp_configs(cursor_dir, report)
    _remove_directory_if_empty(cursor_dir, report)

    if report.changed:
        logger.info(
            "cleanup_legacy_cursor_artifacts: removed leftovers under %s: "
            + "symlinks=%s agents=%s mcp_configs=%s dir_removed=%s",
            cursor_dir,
            report.removed_symlinks,
            report.removed_agent_files,
            report.removed_mcp_configs,
            report.removed_directory,
        )

    return report
