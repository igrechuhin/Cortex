"""Unit tests for CSharpAdapter detection behavior."""

import tempfile
from pathlib import Path

from cortex.services.framework_adapters.csharp_adapter import CSharpAdapter


def test_detect_returns_none_without_dotnet_markers() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        result = CSharpAdapter.detect(Path(tmpdir))
        assert result is None


def test_detect_recognizes_csproj_project() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _ = (root / "Example.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk"></Project>\n'
        )

        result = CSharpAdapter.detect(root)

        assert result is not None
        assert result.language == "csharp"
        assert result.build_tool == "dotnet"
        assert result.test_framework == "dotnet test"
