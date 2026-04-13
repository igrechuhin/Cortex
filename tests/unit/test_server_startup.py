"""Regression tests for Cortex server startup stability."""

import importlib


def test_import_cortex_server_does_not_raise() -> None:
    """Importing cortex.server should not fail at module import time."""
    module = importlib.import_module("cortex.server")
    assert module is not None
