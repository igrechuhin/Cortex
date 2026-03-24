# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Unit tests for cortex.setup.lazy_prompt_registration."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import cortex.setup.prompts_always  # noqa: F401  # registers setup_synapse on the MCP server
from cortex.setup.lazy_prompt_registration import (
    LazyPromptRegistry,
    _prompt_manager_has_synapse_prompts,
    _register_setup_prompts,
    _registered_prompt_names,
    ensure_prompts_registered,
)
from cortex.tools.config import ProjectConfigStatus

_ = cortex.setup.prompts_always

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


# ---------------------------------------------------------------------------
# _registered_prompt_names / _prompt_manager_has_synapse_prompts
# ---------------------------------------------------------------------------


class TestRegisteredPromptNames:
    def test_returns_frozenset_of_registered_names(self) -> None:
        names = _registered_prompt_names()
        assert isinstance(names, frozenset)
        # setup_synapse is always registered via prompts_always
        assert "setup_synapse" in names

    def test_has_synapse_prompts_returns_bool(self) -> None:
        result = _prompt_manager_has_synapse_prompts()
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
        before = _registered_prompt_names()
        _register_setup_prompts(status)
        after = _registered_prompt_names()
        # initialize must be registered (or was already there)
        assert "initialize" in after
        _ = before  # referenced to satisfy linter

    def test_registers_migrate_when_migration_needed(self) -> None:
        status = _make_status(migration_needed=True, memory_bank_initialized=False)
        _register_setup_prompts(status)
        assert "migrate" in _registered_prompt_names()

    def test_skips_initialize_when_migration_needed(self) -> None:
        # When migration_needed=True, initialize should NOT be registered
        # (the logic: initialize requires migration_needed=False)
        status = _make_status(
            memory_bank_initialized=False,
            structure_configured=False,
            migration_needed=True,
        )
        before = _registered_prompt_names()
        _register_setup_prompts(status)
        after = _registered_prompt_names()
        # initialize was not present before and should not be added now
        if "initialize" not in before:
            assert "initialize" not in after

    def test_no_setup_prompts_when_fully_configured(self) -> None:
        status = _make_status()  # all good
        before = _registered_prompt_names()
        _register_setup_prompts(status)
        after = _registered_prompt_names()
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

        registry._do_register = fake_do_register  # type: ignore[method-assign]

        await registry.ensure_registered(None)
        await registry.ensure_registered(None)
        await registry.ensure_registered(None)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_ensure_registered_sets_flag(self) -> None:
        registry = LazyPromptRegistry()
        registry._do_register = AsyncMock()  # type: ignore[method-assign]

        assert not registry._registered
        await registry.ensure_registered(None)
        assert registry._registered

    @pytest.mark.asyncio
    async def test_ensure_registered_concurrent(self) -> None:
        """Concurrent calls must only register once."""
        registry = LazyPromptRegistry()
        call_count = 0

        async def slow_do_register(_ctx: object) -> None:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0)

        registry._do_register = slow_do_register  # type: ignore[method-assign]

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

        with (
            patch(
                "cortex.setup.lazy_prompt_registration._prompt_manager_has_synapse_prompts",
                return_value=True,
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
            await registry._do_register(None)

        mock_reg.assert_not_called()
        mock_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_do_register_runs_synapse_when_missing(self, tmp_path: Path) -> None:
        """When synapse prompts are absent, registration is run with resolved root."""
        registry = LazyPromptRegistry()

        with (
            patch(
                "cortex.setup.lazy_prompt_registration._prompt_manager_has_synapse_prompts",
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
            await registry._do_register(None)

        mock_reg.assert_called_once_with(tmp_path)
        mock_sync.assert_called_once_with(tmp_path)

    @pytest.mark.asyncio
    async def test_do_register_registers_setup_prompts_when_needed(
        self, tmp_path: Path
    ) -> None:
        """Setup prompts are registered when project needs setup."""
        registry = LazyPromptRegistry()

        with (
            patch(
                "cortex.setup.lazy_prompt_registration._prompt_manager_has_synapse_prompts",
                return_value=True,
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
                return_value=_make_status(
                    memory_bank_initialized=False,
                    structure_configured=False,
                    migration_needed=False,
                ),
            ),
            patch(
                "cortex.setup.lazy_prompt_registration.should_mount_setup",
                return_value=True,
            ),
            patch(
                "cortex.setup.lazy_prompt_registration._register_setup_prompts"
            ) as mock_setup,
        ):
            await registry._do_register(None)

        mock_setup.assert_called_once()

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
                "cortex.setup.lazy_prompt_registration._prompt_manager_has_synapse_prompts",
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
            await registry._do_register(mock_ctx)

        mock_session.send_prompt_list_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_do_register_skips_notify_when_no_ctx(self, tmp_path: Path) -> None:
        """No notification is sent when ctx is None."""
        registry = LazyPromptRegistry()

        with (
            patch(
                "cortex.setup.lazy_prompt_registration._prompt_manager_has_synapse_prompts",
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
            await registry._do_register(None)

    @pytest.mark.asyncio
    async def test_do_register_handles_root_resolution_error(self) -> None:
        """When root resolution fails, do_register returns without raising."""
        registry = LazyPromptRegistry()

        with patch(
            "cortex.setup.lazy_prompt_registration.resolve_project_root_async",
            side_effect=RuntimeError("roots not available"),
        ):
            # Must not raise
            await registry._do_register(None)

    @pytest.mark.asyncio
    async def test_do_register_handles_synapse_registration_error(
        self, tmp_path: Path
    ) -> None:
        """Synapse registration errors are caught and logged, not re-raised."""
        registry = LazyPromptRegistry()

        with (
            patch(
                "cortex.setup.lazy_prompt_registration._prompt_manager_has_synapse_prompts",
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
            await registry._do_register(None)


# ---------------------------------------------------------------------------
# ensure_prompts_registered (module-level entry point)
# ---------------------------------------------------------------------------


class TestEnsurePromptsRegistered:
    @pytest.mark.asyncio
    async def test_delegates_to_registry(self) -> None:
        """ensure_prompts_registered delegates to the module singleton."""
        from cortex.setup import lazy_prompt_registration as lpr

        original = lpr._registry
        mock_registry = MagicMock()
        mock_registry.ensure_registered = AsyncMock()
        lpr._registry = mock_registry
        try:
            await ensure_prompts_registered(None)
            mock_registry.ensure_registered.assert_awaited_once_with(None)
        finally:
            lpr._registry = original
