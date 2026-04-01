"""Parametrized tests for framework adapters (consolidated init patterns)."""

import tempfile
from pathlib import Path

import pytest

from cortex.services.framework_adapters.base import FrameworkAdapter
from cortex.services.framework_adapters.csharp_adapter import CSharpAdapter
from cortex.services.framework_adapters.go_adapter import GoAdapter
from cortex.services.framework_adapters.java_adapter import JavaAdapter
from cortex.services.framework_adapters.javascript_adapter import JavaScriptAdapter
from cortex.services.framework_adapters.kotlin_adapter import KotlinAdapter
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.rust_adapter import RustAdapter
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.services.framework_adapters.typescript_adapter import TypeScriptAdapter

# All framework adapters; order matches plan (Python, Java, Kotlin, TypeScript, Go, Rust, Swift) + JavaScript.
_ADAPTERS: list[tuple[str, type[FrameworkAdapter]]] = [
    ("python", PythonAdapter),
    ("java", JavaAdapter),
    ("kotlin", KotlinAdapter),
    ("typescript", TypeScriptAdapter),
    ("go", GoAdapter),
    ("rust", RustAdapter),
    ("swift", SwiftAdapter),
    ("javascript", JavaScriptAdapter),
    ("csharp", CSharpAdapter),
]


class TestFrameworkAdapterInitParametrized:
    """Parametrized init tests shared across all framework adapters."""

    @pytest.mark.parametrize(
        "language,adapter_cls",
        _ADAPTERS,
        ids=[a[0] for a in _ADAPTERS],
    )
    def test_init_with_project_root(
        self, language: str, adapter_cls: type[FrameworkAdapter]
    ) -> None:
        """Adapter initializes with given project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = adapter_cls(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    @pytest.mark.parametrize(
        "language,adapter_cls",
        _ADAPTERS,
        ids=[a[0] for a in _ADAPTERS],
    )
    def test_init_without_project_root(
        self, language: str, adapter_cls: type[FrameworkAdapter]
    ) -> None:
        """Adapter initializes with cwd when project_root is None."""
        adapter = adapter_cls()
        assert adapter.project_root == Path.cwd()
