"""Regression tests for Cortex server startup stability."""

import importlib


def test_import_cortex_server_does_not_raise() -> None:
    """Importing cortex.server should not fail at module import time."""
    module = importlib.import_module("cortex.server")
    assert module is not None


def test_server_registers_phase3_middlewares() -> None:
    """Server startup should include lazy, disconnect, and response-limit middleware."""
    server_module = importlib.import_module("cortex.server")
    middleware_names = [
        type(middleware).__name__ for middleware in server_module.mcp.middleware
    ]

    assert "_LazyPromptsMiddleware" in middleware_names
    assert "_RootsChangedMiddleware" in middleware_names
    assert "DisconnectMiddleware" in middleware_names
    assert "ResponseLimitingMiddleware" in middleware_names
