"""Regression tests for Cortex server startup stability."""

import importlib
import inspect


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


def test_server_registers_phase3_middlewares() -> None:
    """Server startup should include lazy, disconnect, and response-limit middleware."""
    server_module = importlib.import_module("cortex.server")
    middleware_names = [
        type(middleware).__name__ for middleware in server_module.mcp.middleware
    ]

    assert "_LazyPromptsMiddleware" in middleware_names
    assert "DisconnectMiddleware" in middleware_names
    assert "ResponseLimitingMiddleware" in middleware_names


def test_main_module_has_no_handle_request_patch() -> None:
    """main.py should not patch private _handle_request anymore."""
    module = importlib.import_module("cortex.main")
    source = inspect.getsource(module)
    assert "_patch_mcp_server_handle_request" not in source
