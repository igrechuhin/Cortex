"""Tests for RulesLoader category-name aliasing."""

import json
from pathlib import Path

import pytest

from cortex.rules.rules_loader import RulesLoader


def _write_manifest(rules_path: Path, category: str) -> None:
    """Write a one-rule manifest plus its rule file under the given category."""
    (rules_path / category).mkdir(parents=True)
    _ = (rules_path / category / "rule.mdc").write_text("# Rule", encoding="utf-8")
    manifest: dict[
        str, str | dict[str, dict[str, str | list[dict[str, str | int | list[str]]]]]
    ] = {
        "version": "1.0",
        "categories": {
            category: {
                "description": "test",
                "rules": [{"file": "rule.mdc", "priority": 90, "keywords": []}],
            }
        },
    }
    _ = (rules_path / "rules-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


class TestCategoryAliases:
    """Synapse names the shared bucket 'general'; Cortex asks for 'generic'."""

    @pytest.mark.asyncio
    async def test_generic_request_loads_general_category(self, tmp_path: Path) -> None:
        """Test that requesting 'generic' finds a manifest's 'general' rules."""
        # Arrange
        _write_manifest(tmp_path, "general")
        loader = RulesLoader(tmp_path)

        # Act
        rules = await loader.load_category("generic")

        # Assert
        assert len(rules) == 1

    @pytest.mark.asyncio
    async def test_general_request_loads_generic_category(self, tmp_path: Path) -> None:
        """Test that the alias also resolves in the opposite direction."""
        # Arrange
        _write_manifest(tmp_path, "generic")
        loader = RulesLoader(tmp_path)

        # Act
        rules = await loader.load_category("general")

        # Assert
        assert len(rules) == 1

    @pytest.mark.asyncio
    async def test_unknown_category_returns_empty(self, tmp_path: Path) -> None:
        """Test that an unrelated category name still resolves to nothing."""
        # Arrange
        _write_manifest(tmp_path, "general")
        loader = RulesLoader(tmp_path)

        # Act
        rules = await loader.load_category("cobol")

        # Assert
        assert rules == []
