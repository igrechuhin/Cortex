"""Unit tests for compress package public exports."""

from __future__ import annotations

import cortex.tools.compress as compress_module


def test_compress_module_exports_required_symbols() -> None:
    """Step 7 API contract: required symbols are exposed from package root."""
    required_exports = {
        "compress_file",
        "compress_directory",
        "ValidationResult",
        "CompressResult",
        "detect_file_type",
    }

    exported_names = set(compress_module.__all__)
    assert required_exports.issubset(exported_names)

    for symbol_name in required_exports:
        assert hasattr(compress_module, symbol_name)
        assert getattr(compress_module, symbol_name) is not None
