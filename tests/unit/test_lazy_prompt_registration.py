# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Unit tests for cortex.setup.lazy_prompt_registration."""

from __future__ import annotations

import asyncio
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import cortex.setup.prompts_always  # noqa: F401  # registers setup_synapse on the MCP server
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.setup.lazy_prompt_registration import (
    LazyPromptRegistry,
    ensure_prompts_registered,
    prompt_manager_has_synapse_prompts,
    register_setup_prompts,
    registered_prompt_names,
)
from cortex.tools.config import ProjectConfigStatus
from cortex.wiki.layout import ensure_default_wiki_layout

_ = cortex.setup.prompts_always

_M = "cortex.setup.lazy_prompt_registration"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_status(
    *,
    memory_bank_initialized: bool = True,
    structure_configured: bool = True,
    cursor_integration_configured: bool = True,
    migration_needed: bool = False,
    tiktoken_cache_available: bool = True,
) -> ProjectConfigStatus:
    return ProjectConfigStatus(
        memory_bank_initialized=memory_bank_initialized,
        structure_configured=structure_configured,
        cursor_integration_configured=cursor_integration_configured,
        migration_needed=migration_needed,
        tiktoken_cache_available=tiktoken_cache_available,
    )


def _enter_lazy_root_patches(
    stack: ExitStack,
    tmp_path: Path,
    *,
    has_synapse: bool,
    mount_setup: bool,
    status: ProjectConfigStatus | None = None,
) -> None:
    st = status or _make_status()
    _ = stack.enter_context(
        patch(f"{_M}.prompt_manager_has_synapse_prompts", return_value=has_synapse)
    )
    _ = stack.enter_context(
        patch(
            f"{_M}.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        )
    )
    _ = stack.enter_context(patch(f"{_M}.get_project_config_status", return_value=st))
    _ = stack.enter_context(patch(f"{_M}.should_mount_setup", return_value=mount_setup))


def _write_init_wiki_fixture_under_cortex(cortex: Path) -> None:
    syn = cortex / "synapse" / "prompts"
    syn.mkdir(parents=True)
    _ = (syn / "init-wiki.md").write_text("# Init\n\nx.\n", encoding="utf-8")
    payload = {
        "version": "1.0",
        "categories": {
            "general": {
                "prompts": [
                    {
                        "file": "init-wiki.md",
                        "name": "Init Wiki",
                        "description": "Manifest desc",
                    }
                ]
            }
        },
    }
    _ = (syn / "prompts-manifest.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# _registered_prompt_names / _prompt_manager_has_synapse_prompts
# ---------------------------------------------------------------------------


class TestRegisteredPromptNames:
    def test_returns_frozenset_of_registered_names(self) -> None:
        names = registered_prompt_names()
        assert isinstance(names, frozenset)
        # setup_synapse is always registered via prompts_always
        assert "setup_synapse" in names

    def test_has_synapse_prompts_returns_bool(self) -> None:
        result = prompt_manager_has_synapse_prompts()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# _register_setup_prompts
# ---------------------------------------------------------------------------


class TestRegisterSetupPrompts:
    def test_registers_initialize_when_not_configured(self) -> None:
        status = _make_status(
            memory_bank_initialized=False,
            structure_configured=False,
            migration_needed=False,
        )
        before = registered_prompt_names()
        register_setup_prompts(status, Path.cwd())
        after = registered_prompt_names()
        # initialize must be registered (or was already there)
        assert "initialize" in after
        _ = before  # referenced to satisfy linter

    def test_registers_migrate_when_migration_needed(self) -> None:
        status = _make_status(migration_needed=True, memory_bank_initialized=False)
        register_setup_prompts(status, Path.cwd())
        assert "migrate" in registered_prompt_names()

    def test_skips_initialize_when_migration_needed(self) -> None:
        # When migration_needed=True, initialize should NOT be registered
        # (the logic: initialize requires migration_needed=False)
        status = _make_status(
            memory_bank_initialized=False,
            structure_configured=False,
            migration_needed=True,
        )
        before = registered_prompt_names()
        register_setup_prompts(status, Path.cwd())
        after = registered_prompt_names()
        # initialize was not present before and should not be added now
        if "initialize" not in before:
            assert "initialize" not in after

    def test_no_setup_prompts_when_fully_configured(self) -> None:
        status = _make_status()  # all good
        before = registered_prompt_names()
        register_setup_prompts(status, Path.cwd())
        after = registered_prompt_names()
        # Nothing new should be added
        assert after == before


# ---------------------------------------------------------------------------
# LazyPromptRegistry
# ---------------------------------------------------------------------------


class TestLazyPromptRegistry:
    @pytest.mark.asyncio
    async def test_ensure_registered_calls_do_register_once(self) -> None:
        """ensure_registered triggers _do_register exactly once."""
        registry = LazyPromptRegistry()
        call_count = 0

        async def fake_do_register(_ctx: object) -> None:
            nonlocal call_count
            call_count += 1

        registry.do_register = fake_do_register  # type: ignore[method-assign]

        await registry.ensure_registered(None)
        await registry.ensure_registered(None)
        await registry.ensure_registered(None)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_ensure_registered_sets_flag(self) -> None:
        registry = LazyPromptRegistry()
        registry.do_register = AsyncMock()  # type: ignore[method-assign]

        assert not registry.registered
        await registry.ensure_registered(None)
        assert registry.registered

    @pytest.mark.asyncio
    async def test_ensure_registered_concurrent(self) -> None:
        """Concurrent calls must only register once."""
        registry = LazyPromptRegistry()
        call_count = 0

        async def slow_do_register(_ctx: object) -> None:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0)

        registry.do_register = slow_do_register  # type: ignore[method-assign]

        _ = await asyncio.gather(
            registry.ensure_registered(None),
            registry.ensure_registered(None),
            registry.ensure_registered(None),
        )

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_do_register_skips_synapse_when_already_registered(
        self, tmp_path: Path
    ) -> None:
        """When synapse prompts are already present, synapse registration is skipped."""
        registry = LazyPromptRegistry()
        with ExitStack() as stack:
            _enter_lazy_root_patches(
                stack, tmp_path, has_synapse=True, mount_setup=False
            )
            mock_reg = stack.enter_context(patch(f"{_M}.register_synapse_prompts"))
            mock_sync = stack.enter_context(patch(f"{_M}.sync_cursor_agents"))
            await registry.do_register(None)
        mock_reg.assert_not_called()
        mock_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_do_register_runs_synapse_when_missing(self, tmp_path: Path) -> None:
        """When synapse prompts are absent, registration is run with resolved root."""
        registry = LazyPromptRegistry()

        with (
            patch(
                "cortex.setup.lazy_prompt_registration.prompt_manager_has_synapse_prompts",
                return_value=False,
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.register_synapse_prompts"
            ) as mock_reg,
            patch(
                "cortex.setup.lazy_prompt_registration.sync_cursor_agents"
            ) as mock_sync,
            patch(
                "cortex.setup.lazy_prompt_registration.get_project_config_status",
                return_value=_make_status(),
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.should_mount_setup",
                return_value=False,
            ),
        ):
            await registry.do_register(None)

        mock_reg.assert_called_once_with(tmp_path)
        mock_sync.assert_called_once_with(tmp_path)

    @pytest.mark.asyncio
    async def test_do_register_registers_setup_prompts_when_needed(
        self, tmp_path: Path
    ) -> None:
        """Setup prompts are registered when project needs setup."""
        registry = LazyPromptRegistry()
        st = _make_status(
            memory_bank_initialized=False,
            structure_configured=False,
            migration_needed=False,
        )
        with ExitStack() as stack:
            _enter_lazy_root_patches(
                stack, tmp_path, has_synapse=True, mount_setup=True, status=st
            )
            _ = stack.enter_context(patch(f"{_M}.register_synapse_prompts"))
            _ = stack.enter_context(patch(f"{_M}.sync_cursor_agents"))
            mock_setup = stack.enter_context(patch(f"{_M}.register_setup_prompts"))
            await registry.do_register(None)
        mock_setup.assert_called_once()
        status_arg, root_arg = mock_setup.call_args.args
        assert isinstance(status_arg, ProjectConfigStatus)
        assert status_arg.memory_bank_initialized is False
        assert status_arg.structure_configured is False
        assert status_arg.migration_needed is False
        assert root_arg == tmp_path

    @pytest.mark.asyncio
    async def test_do_register_sends_list_changed_when_prompts_added(
        self, tmp_path: Path
    ) -> None:
        """send_prompt_list_changed is called when new prompts were added."""
        registry = LazyPromptRegistry()

        mock_session = AsyncMock()
        mock_session.send_prompt_list_changed = AsyncMock()
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        with (
            patch(
                "cortex.setup.lazy_prompt_registration.prompt_manager_has_synapse_prompts",
                return_value=False,
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch("cortex.setup.lazy_prompt_registration.register_synapse_prompts"),
            patch("cortex.setup.lazy_prompt_registration.sync_cursor_agents"),
            patch(
                "cortex.setup.lazy_prompt_registration.get_project_config_status",
                return_value=_make_status(),
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.should_mount_setup",
                return_value=False,
            ),
        ):
            await registry.do_register(mock_ctx)

        mock_session.send_prompt_list_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_do_register_skips_notify_when_no_ctx(self, tmp_path: Path) -> None:
        """No notification is sent when ctx is None."""
        registry = LazyPromptRegistry()

        with (
            patch(
                "cortex.setup.lazy_prompt_registration.prompt_manager_has_synapse_prompts",
                return_value=False,
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch("cortex.setup.lazy_prompt_registration.register_synapse_prompts"),
            patch("cortex.setup.lazy_prompt_registration.sync_cursor_agents"),
            patch(
                "cortex.setup.lazy_prompt_registration.get_project_config_status",
                return_value=_make_status(),
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.should_mount_setup",
                return_value=False,
            ),
        ):
            # Should not raise even though ctx is None
            await registry.do_register(None)

    @pytest.mark.asyncio
    async def test_do_register_handles_root_resolution_error(self) -> None:
        """When root resolution fails, do_register returns without raising."""
        registry = LazyPromptRegistry()

        with patch(
            "cortex.setup.lazy_prompt_registration.resolve_project_root_async",
            side_effect=RuntimeError("roots not available"),
        ):
            # Must not raise
            await registry.do_register(None)

    @pytest.mark.asyncio
    async def test_do_register_handles_synapse_registration_error(
        self, tmp_path: Path
    ) -> None:
        """Synapse registration errors are caught and logged, not re-raised."""
        registry = LazyPromptRegistry()

        with (
            patch(
                "cortex.setup.lazy_prompt_registration.prompt_manager_has_synapse_prompts",
                return_value=False,
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.register_synapse_prompts",
                side_effect=RuntimeError("disk error"),
            ),
            patch("cortex.setup.lazy_prompt_registration.sync_cursor_agents"),
            patch(
                "cortex.setup.lazy_prompt_registration.get_project_config_status",
                return_value=_make_status(),
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.should_mount_setup",
                return_value=False,
            ),
        ):
            # Must not raise
            await registry.do_register(None)

    @pytest.mark.asyncio
    async def test_do_register_calls_create_prompt_for_empty_wiki(
        self, tmp_path: Path
    ) -> None:
        """When the wiki scaffold exists and has no pages, ``init_wiki`` is registered."""
        registry = LazyPromptRegistry()
        cortex = tmp_path / ".cortex"
        cortex.mkdir()
        _ = ensure_default_wiki_layout(tmp_path)
        _write_init_wiki_fixture_under_cortex(cortex)
        mock_create = MagicMock()
        with ExitStack() as stack:
            _enter_lazy_root_patches(
                stack, tmp_path, has_synapse=True, mount_setup=False
            )
            _ = stack.enter_context(patch(f"{_M}.register_synapse_prompts"))
            _ = stack.enter_context(patch(f"{_M}.sync_cursor_agents"))
            _ = stack.enter_context(patch(f"{_M}.create_prompt_function", mock_create))
            await registry.do_register(None)
        mock_create.assert_called_once()
        pos = mock_create.call_args[0]
        assert pos[0] == "init_wiki"
        assert pos[2] == "Manifest desc"
        assert pos[3] is None

    @pytest.mark.asyncio
    async def test_do_register_skips_init_wiki_when_wiki_has_pages(
        self, tmp_path: Path
    ) -> None:
        registry = LazyPromptRegistry()
        cortex = tmp_path / ".cortex"
        cortex.mkdir()
        _ = ensure_default_wiki_layout(tmp_path)
        wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
        _ = (wiki / "concepts" / "p.md").write_text("# P\n", encoding="utf-8")
        _write_init_wiki_fixture_under_cortex(cortex)
        mock_create = MagicMock()
        with ExitStack() as stack:
            _enter_lazy_root_patches(
                stack, tmp_path, has_synapse=True, mount_setup=False
            )
            _ = stack.enter_context(patch(f"{_M}.register_synapse_prompts"))
            _ = stack.enter_context(patch(f"{_M}.sync_cursor_agents"))
            _ = stack.enter_context(patch(f"{_M}.create_prompt_function", mock_create))
            await registry.do_register(None)
        mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# ensure_prompts_registered (module-level entry point)
# ---------------------------------------------------------------------------


class TestEnsurePromptsRegistered:
    @pytest.mark.asyncio
    async def test_delegates_to_registry(self) -> None:
        """ensure_prompts_registered delegates to the module singleton."""
        from cortex.setup import lazy_prompt_registration as lpr

        original = lpr.registry
        mock_registry = MagicMock()
        mock_registry.ensure_registered = AsyncMock()
        lpr.registry = mock_registry
        try:
            await ensure_prompts_registered(None)
            mock_registry.ensure_registered.assert_awaited_once_with(None)
        finally:
            lpr.registry = original
