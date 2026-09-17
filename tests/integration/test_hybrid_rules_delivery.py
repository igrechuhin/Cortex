"""Real Synapse files must survive hybrid selection and the public rules resource."""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.session_config import SessionConfig
from cortex.core.token_counter import TokenCounter
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.models import (
    DetectedContextModel,
    OptimizationRuleCategory,
    RulesResultModel,
    ScoredRuleModel,
)
from cortex.optimization.rules_hybrid import RulesHybridMixin
from cortex.optimization.rules_manager import RulesManager
from cortex.rules.models import (
    CategoryInfo,
    LoadedRule,
    RuleMetadataEntry,
    RulesManifestModel,
)
from cortex.rules.synapse_manager import SynapseManager
from cortex.tools.synapse.rules_operations import invalidate_rules_resource_cache
from tests.integration.resource_test_helpers import read_resource_text

SHARED_RULE_FIXTURES = (
    LoadedRule(
        category="generic",
        file="generic.mdc",
        path="",
        content="python common generic policy",
        priority=90,
    ),
    LoadedRule(
        category="general",
        file="general.mdc",
        path="",
        content="python common general policy",
        priority=85,
    ),
    LoadedRule(
        category="general",
        file="nested/override.mdc",
        path="",
        content="python shared override policy",
        priority=70,
    ),
    LoadedRule(
        category="python",
        file="style.mdc",
        path="",
        content="python formatting language policy",
        priority=80,
    ),
)
LOCAL_RULE_CONTENTS = {
    "nested/override.mdc": "python local override policy",
    "other/override.mdc": "python distinct local policy",
}
AI_COMMENT_GOVERNANCE = "Record meaningful assumptions. " * 30
COMMUNICATION_GOVERNANCE = "Report verified facts concisely. " * 30


class DeliveredRulesPayload(BaseModel):
    """Relevant public fields; unrelated resource envelope fields are ignored."""

    rules: list[ScoredRuleModel]
    rules_count: int
    total_tokens: int
    max_tokens: int
    reflection_checklist: str
    ai_code_comments_rule: str
    agent_internal_communication_rule: str


def _write_hybrid_rule_fixture(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(content, encoding="utf-8")


def _write_hybrid_shared_fixture(root: Path) -> None:
    rules = get_cortex_path(root, CortexResourceType.SYNAPSE) / "rules"
    manifest = RulesManifestModel()
    for rule in SHARED_RULE_FIXTURES:
        category = manifest.categories.setdefault(rule.category, CategoryInfo())
        category.rules.append(RuleMetadataEntry(file=rule.file, priority=rule.priority))
        _write_hybrid_rule_fixture(rules / rule.category / rule.file, rule.content)
    _write_hybrid_rule_fixture(
        rules / "rules-manifest.json", manifest.model_dump_json()
    )
    _write_hybrid_rule_fixture(
        rules / "general" / "ai-code-comments.mdc", AI_COMMENT_GOVERNANCE
    )
    _write_hybrid_rule_fixture(
        rules / "general" / "agent-internal-communication.mdc", COMMUNICATION_GOVERNANCE
    )


@pytest.fixture
async def hybrid_rules_manager(tmp_path: Path) -> AsyncIterator[RulesManager]:
    """Use the real manifest loader, context detector, indexer, merger, and scorer."""
    _write_hybrid_shared_fixture(tmp_path)
    local = get_cortex_path(tmp_path, CortexResourceType.RULES)
    for relative, content in LOCAL_RULE_CONTENTS.items():
        _write_hybrid_rule_fixture(local / relative, content)
    manager = RulesManager(
        tmp_path,
        FileSystemManager(tmp_path),
        MetadataIndex(tmp_path),
        TokenCounter(),
        rules_folder=local.relative_to(tmp_path).as_posix(),
        synapse_manager=SynapseManager(tmp_path, auto_sync=False),
    )
    _ = await manager.index_rules()
    try:
        yield manager
    finally:
        await manager.stop_auto_reindex()


def _isolate_hybrid_rule_context(
    root: Path,
    managers: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scope transport initialization, session defaults, and telemetry to the fixture."""
    for module in ("mcp_stability_usage", "usage_context"):
        monkeypatch.setattr(
            f"cortex.core.{module}.get_current_managers", lambda: managers
        )
    for module in ("usage_context", "mcp_tool_telemetry"):
        monkeypatch.setattr(
            f"cortex.core.{module}.get_current_project_root", lambda: root
        )
    monkeypatch.setattr(
        "cortex.tools.synapse.rules_operations.get_managers",
        AsyncMock(return_value=managers),
    )
    monkeypatch.setattr(
        "cortex.tools.synapse.rules_operations.resolve_project_root_async",
        AsyncMock(return_value=root),
    )
    monkeypatch.setattr(
        "cortex.core.session_config.read_session_config",
        lambda: SessionConfig(task_description="python"),
    )


@pytest.fixture
async def public_hybrid_rules(
    hybrid_rules_manager: RulesManager,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[OptimizationConfig]:
    """Inject real managers while keeping wrappers and telemetry in the temp root."""
    root = hybrid_rules_manager.project_root
    config = OptimizationConfig(root)
    _ = config.set("rules.enabled", True)
    _ = config.set("rules.rules_folder", hybrid_rules_manager.rules_folder)
    _ = config.set("rules.min_relevance_score", 0.0)
    managers: dict[str, object] = {
        "rules_manager": hybrid_rules_manager,
        "optimization_config": config,
    }
    _isolate_hybrid_rule_context(root, managers, monkeypatch)
    invalidate_rules_resource_cache()
    try:
        yield config
    finally:
        invalidate_rules_resource_cache()


def _delivered_hybrid_rules(result: RulesResultModel) -> list[ScoredRuleModel]:
    return result.generic_rules + result.language_rules + result.local_rules


def _expected_hybrid_contents(shared_override: bool = False) -> dict[str, str]:
    expected = {rule.file: rule.content for rule in SHARED_RULE_FIXTURES}
    expected.update(LOCAL_RULE_CONTENTS)
    if shared_override:
        expected["nested/override.mdc"] = "python shared override policy"
    return expected


def _constrained_hybrid_budget(manager: RulesManager) -> int:
    expected = _expected_hybrid_contents()
    _ = expected.pop("other/override.mdc")
    counter = manager.token_counter
    assert counter is not None
    return sum(counter.count_tokens(content) for content in expected.values())


@pytest.mark.parametrize("shared_override", [False, True])
async def test_real_hybrid_selection_preserves_categories_and_nested_overrides(
    hybrid_rules_manager: RulesManager,
    shared_override: bool,
) -> None:
    # Arrange / Act
    priority = "shared_overrides_local" if shared_override else "local_overrides_shared"
    result = RulesResultModel.model_validate(
        await hybrid_rules_manager.get_relevant_rules("python", rule_priority=priority)
    )
    delivered = _delivered_hybrid_rules(result)

    # Assert
    assert len(delivered) == 5
    assert {rule.file: rule.content for rule in delivered} == _expected_hybrid_contents(
        shared_override
    )
    assert {rule.file for rule in result.language_rules} == {"style.mdc"}
    assert {rule.file for rule in result.generic_rules} == {
        "generic.mdc",
        "general.mdc",
        "nested/override.mdc",
        "other/override.mdc",
    }
    assert result.total_tokens == sum(rule.tokens for rule in delivered)
    assert result.source == "hybrid"


@pytest.mark.parametrize("empty_budget", [False, True])
async def test_real_hybrid_selection_accounts_only_for_delivered_budget(
    hybrid_rules_manager: RulesManager,
    empty_budget: bool,
) -> None:
    # Arrange
    budget = 0 if empty_budget else _constrained_hybrid_budget(hybrid_rules_manager)
    expected: dict[str, str] = {} if empty_budget else _expected_hybrid_contents()
    _ = expected.pop("other/override.mdc", None)

    # Act
    result = RulesResultModel.model_validate(
        await hybrid_rules_manager.get_relevant_rules("python", max_tokens=budget)
    )
    delivered = _delivered_hybrid_rules(result)

    # Assert
    assert len(delivered) == len(expected)
    assert {rule.file: rule.content for rule in delivered} == expected
    assert result.total_tokens == sum(rule.tokens for rule in delivered) == budget


@pytest.mark.parametrize("category", ["generic", "general"])
async def test_real_shared_category_alias_delivers_each_file_once(
    hybrid_rules_manager: RulesManager,
    category: str,
) -> None:
    # Arrange
    synapse = hybrid_rules_manager.synapse_manager
    assert synapse is not None
    rule = RuleMetadataEntry(file="common.mdc")
    manifest = RulesManifestModel(categories={category: CategoryInfo(rules=[rule])})
    _write_hybrid_rule_fixture(
        synapse.rules_path / category / rule.file, "python alias common rule"
    )
    _write_hybrid_rule_fixture(
        synapse.rules_path / "rules-manifest.json", manifest.model_dump_json()
    )

    # Act
    result = RulesResultModel.model_validate(
        await hybrid_rules_manager.get_relevant_rules("python")
    )
    shared = [
        rule for rule in _delivered_hybrid_rules(result) if rule.source == "shared"
    ]

    # Assert
    assert [(rule.file, rule.content) for rule in shared] == [
        ("common.mdc", "python alias common rule")
    ]
    assert result.total_tokens == sum(
        rule.tokens for rule in _delivered_hybrid_rules(result)
    )


@pytest.mark.parametrize("category", list(OptimizationRuleCategory))
@pytest.mark.parametrize("source", ["shared", "local"])
def test_every_selected_rule_has_exactly_one_bucket(
    category: OptimizationRuleCategory,
    source: str,
) -> None:
    # Arrange
    rule = ScoredRuleModel(
        file="selected.mdc",
        content="policy",
        tokens=1,
        category=category,
        source=source,
    )
    result = RulesResultModel()
    context = DetectedContextModel(detected_languages=["python"])

    # Act
    RulesHybridMixin().categorize_rules(result, [rule], context)

    # Assert
    assert _delivered_hybrid_rules(result) == [rule]
    if category == OptimizationRuleCategory.PYTHON:
        assert result.language_rules == [rule]
    elif source == "local" and category in {
        OptimizationRuleCategory.SWIFT,
        OptimizationRuleCategory.MARKDOWN,
    }:
        assert result.local_rules == [rule]
    else:
        assert result.generic_rules == [rule]


@pytest.mark.parametrize("constrained", [False, True])
async def test_public_zero_arg_rules_delivers_real_selection_stably(
    hybrid_rules_manager: RulesManager,
    public_hybrid_rules: OptimizationConfig,
    constrained: bool,
) -> None:
    # Arrange
    expected = _expected_hybrid_contents()
    budget = 5000
    if constrained:
        budget = _constrained_hybrid_budget(hybrid_rules_manager)
        _ = expected.pop("other/override.mdc")
    _ = public_hybrid_rules.set("rules.max_rules_tokens", budget)

    # Act
    first = await read_resource_text("cortex://rules")
    invalidate_rules_resource_cache()
    second = await read_resource_text("cortex://rules")
    result = DeliveredRulesPayload.model_validate_json(first)

    # Assert
    assert first == second
    assert result.rules_count == len(result.rules) == len(expected) > 0
    assert {rule.file: rule.content for rule in result.rules} == expected
    assert result.total_tokens == sum(rule.tokens for rule in result.rules) <= budget
    assert result.max_tokens == budget
    assert result.reflection_checklist
    assert result.ai_code_comments_rule == AI_COMMENT_GOVERNANCE
    assert result.agent_internal_communication_rule == COMMUNICATION_GOVERNANCE
    assert "last_indexed" not in first


async def test_public_rules_recounts_stale_positive_selected_total(
    hybrid_rules_manager: RulesManager,
    public_hybrid_rules: OptimizationConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    selected = await hybrid_rules_manager.get_relevant_rules("python")
    selected["total_tokens"] = 999999
    monkeypatch.setattr(
        hybrid_rules_manager, "get_relevant_rules", AsyncMock(return_value=selected)
    )

    # Act
    result = DeliveredRulesPayload.model_validate_json(
        await read_resource_text("cortex://rules")
    )

    # Assert
    assert result.rules_count == len(result.rules) == 5
    assert result.total_tokens == sum(rule.tokens for rule in result.rules) < 999999
    assert result.max_tokens == public_hybrid_rules.get_rules_max_tokens()
