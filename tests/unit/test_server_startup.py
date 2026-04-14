"""Regression tests for Cortex server startup stability."""

import asyncio
import importlib
import inspect
from types import SimpleNamespace

import anyio
import pytest


def test_import_cortex_server_does_not_raise() -> None:
    """Importing cortex.server should not fail at module import time."""
    module = importlib.import_module("cortex.server")
    assert module is not None


def test_server_module_has_no_lowlevel_patch_access() -> None:
    """server.py should avoid direct mcp._mcp_server monkey-patching."""
    module = importlib.import_module("cortex.server")
    source = inspect.getsource(module)
    assert "mcp._mcp_server" not in source


def test_roots_notification_handler_registered_at_startup() -> None:
    """Startup wiring should install roots/list_changed invalidation handler."""
    main_module = importlib.import_module("cortex.main")
    server_module = importlib.import_module("cortex.server")
    mcp = server_module.mcp
    lowlevel = mcp._mcp_server  # type: ignore[attr-defined]
    handlers = lowlevel.notification_handlers.copy()
    try:
        lowlevel.notification_handlers.clear()
        main_module._register_roots_list_changed_notification_handler()
        from mcp.types import RootsListChangedNotification

        assert RootsListChangedNotification in lowlevel.notification_handlers
    finally:
        lowlevel.notification_handlers.clear()
        lowlevel.notification_handlers.update(handlers)


class _RaisingLowLevelServer:
    """Fake low-level server whose handler always raises ClosedResourceError."""

    async def _handle_request(
        self,
        message: object,
        req: object,
        session: object,
        lifespan_context: object,
        raise_exceptions: bool = False,
    ) -> None:
        _ = (message, req, session, lifespan_context, raise_exceptions)
        raise anyio.ClosedResourceError()


def test_handle_request_patch_absorbs_closed_resource_error() -> None:
    """The temporary shim should swallow ClosedResourceError from response writes."""
    main_module = importlib.import_module("cortex.main")
    fake_lowlevel = _RaisingLowLevelServer()
    original_lowlevel = main_module.mcp._mcp_server  # type: ignore[attr-defined]
    message = SimpleNamespace(request_id="req-123")
    try:
        main_module.mcp._mcp_server = fake_lowlevel  # type: ignore[attr-defined]
        main_module._patch_mcp_server_handle_request()
        patched_handler = getattr(fake_lowlevel, "_handle_request")
        asyncio.run(
            patched_handler(
                message=message,
                req=object(),
                session=object(),
                lifespan_context=object(),
                raise_exceptions=False,
            )
        )
    finally:
        main_module.mcp._mcp_server = original_lowlevel  # type: ignore[attr-defined]


def test_without_patch_closed_resource_error_bubbles() -> None:
    """Baseline behavior without shim still raises ClosedResourceError."""
    fake_lowlevel = _RaisingLowLevelServer()
    raw_handler = getattr(fake_lowlevel, "_handle_request")
    with pytest.raises(anyio.ClosedResourceError):
        asyncio.run(
            raw_handler(
                message=SimpleNamespace(request_id="req-123"),
                req=object(),
                session=object(),
                lifespan_context=object(),
                raise_exceptions=False,
            )
        )
