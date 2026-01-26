import pytest

from cortex.rules.models import RulesManifestModel
from cortex.rules.rules_merger import RulesMerger


@pytest.mark.asyncio
async def test_merge_rules_when_local_overrides_shared_replaces_duplicates_and_sorts() -> (
    None
):
    # Arrange
    merger = RulesMerger()
    shared = [{"file": "a.md", "priority": 10}, {"file": "b.md", "priority": 5}]
    local = [{"file": "a.md", "priority": 99}, {"file": "c.md", "priority": 1}]

    # Act
    merged = await merger.merge_rules(shared, local, priority="local_overrides_shared")

    # Assert
    assert [r["file"] for r in merged] == ["a.md", "b.md", "c.md"]
    assert merged[0]["priority"] == 99


@pytest.mark.asyncio
async def test_merge_rules_when_shared_overrides_local_replaces_duplicates() -> None:
    # Arrange
    merger = RulesMerger()
    shared = [{"file": "a.md", "priority": 50}]
    local = [{"file": "a.md", "priority": 1}, {"file": "b.md", "priority": "bad"}]

    # Act
    merged = await merger.merge_rules(shared, local, priority="shared_overrides_local")

    # Assert
    assert [r["file"] for r in merged] == ["a.md", "b.md"]
    # "bad" priority should fall back to default 50 for sorting, but keep original value
    assert merged[1]["file"] == "b.md"


def test_add_rule_to_manifest_creates_category_and_normalizes_metadata() -> None:
    # Arrange
    merger = RulesMerger()
    manifest = RulesManifestModel()

    # Act
    updated = merger.add_rule_to_manifest(
        manifest,
        category="python",
        filename="style.mdc",
        metadata={"priority": 10.5, "keywords": "not-a-list", "description": None},
    )

    # Assert
    assert "python" in updated.categories
    assert len(updated.categories["python"].rules) == 1
    entry = updated.categories["python"].rules[0]
    assert entry.file == "style.mdc"
    assert entry.priority == 10
    assert entry.keywords == []
    assert entry.description == ""


def test_manifest_helpers_create_missing_containers() -> None:
    # Arrange
    merger = RulesMerger()
    manifest_dict: dict[str, object] = {"categories": "not-a-dict"}

    # Act
    categories = merger._get_or_create_categories(manifest_dict)  # noqa: SLF001
    merger._ensure_category_exists(categories, "general")  # noqa: SLF001
    rules_list = merger._get_or_create_rules_list(categories["general"])  # noqa: SLF001

    # Assert
    assert isinstance(categories, dict)
    assert "general" in categories
    assert isinstance(rules_list, list)
