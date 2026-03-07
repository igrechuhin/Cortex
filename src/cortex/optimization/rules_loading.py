from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from cortex.core.models import ModelDict

from .models import (
    DetectedContextModel,
    IndexedRuleModel,
    RulesResultModel,
    ScoredRuleModel,
)
from .rules_matching import (
    filter_rules_by_score,
    score_rule_relevance,
    score_rules_if_needed,
    select_rules_within_budget,
)

if TYPE_CHECKING:
    from .rules_manager import RulesManager


logger = logging.getLogger(__name__)


async def detect_and_load_context(
    manager: RulesManager,
    result: RulesResultModel,
    task_description: str,
    project_files: list[Path] | None,
) -> DetectedContextModel:
    """Detect context via SynapseManager and update the result structure."""
    assert manager.synapse_manager is not None
    context_dict = await manager.synapse_manager.detect_context(
        task_description, project_files
    )

    if isinstance(context_dict, dict):
        normalized: ModelDict = dict(context_dict)
        if "frameworks" in normalized and "detected_frameworks" not in normalized:
            normalized["detected_frameworks"] = normalized.get("frameworks", [])
        _ = normalized.pop("frameworks", None)
        context = DetectedContextModel.model_validate(normalized)
    else:
        context = DetectedContextModel.model_validate(
            cast(ModelDict, context_dict.model_dump(mode="json"))
        )

    result.context = context
    result.source = "hybrid"
    return context


async def load_shared_rules(
    manager: RulesManager,
    context: DetectedContextModel,
) -> list[ScoredRuleModel]:
    """Load shared rules based on detected context."""
    assert manager.synapse_manager is not None
    categories = await manager.synapse_manager.get_relevant_categories(
        cast(ModelDict, context.model_dump(mode="json"))
    )

    shared_rules: list[ScoredRuleModel] = []
    for category in categories:
        category_rules = await manager.synapse_manager.load_category(category)
        for loaded_rule in category_rules:
            try:
                tokens = manager.token_counter.count_tokens(loaded_rule.content)
                shared_rules.append(
                    ScoredRuleModel(
                        file=loaded_rule.file,
                        name=loaded_rule.file,
                        content=loaded_rule.content,
                        tokens=tokens,
                        relevance_score=0.0,
                        sections=[],
                        source="shared",
                        priority=loaded_rule.priority,
                        category=loaded_rule.category,
                    )
                )
            except Exception as exc:
                logger.debug("load_shared_rules: skip invalid rule: %s", exc)
                continue

    return shared_rules


def _create_scored_rule(
    file_key: str,
    indexed_rule: IndexedRuleModel,
    score: float,
) -> ScoredRuleModel:
    return ScoredRuleModel(
        file=file_key,
        name=file_key,
        content=indexed_rule.content,
        tokens=indexed_rule.token_count,
        relevance_score=score,
        sections=indexed_rule.sections,
        source="local",
        priority=50,
        category="",
    )


def get_local_rules_models(
    manager: RulesManager,
    task_description: str,
    min_relevance_score: float,
) -> list[ScoredRuleModel]:
    """Internal local rules helper returning typed models."""
    rules_index = manager.indexer.get_index()
    if not rules_index:
        return []

    scored_rules: list[ScoredRuleModel] = []
    for file_key, rule_data in rules_index.items():
        try:
            indexed_rule = IndexedRuleModel.model_validate(rule_data)
            score = score_rule_relevance(task_description, indexed_rule.content)
            if score < min_relevance_score:
                continue
            scored_rules.append(_create_scored_rule(file_key, indexed_rule, score))
        except Exception as exc:
            logger.debug("get_local_rules_models: skip rule: %s", exc)
            continue

    scored_rules.sort(key=lambda rule: rule.relevance_score, reverse=True)
    return scored_rules


def get_tagged_local_rules(
    manager: RulesManager,
    task_description: str,
    min_relevance_score: float,
) -> list[ScoredRuleModel]:
    """Get local rules and tag them with a local source."""
    local_rules = get_local_rules_models(manager, task_description, min_relevance_score)
    for rule in local_rules:
        rule.source = "local"
    return local_rules


async def load_and_merge_rules(
    manager: RulesManager,
    task_description: str,
    max_tokens: int,
    min_relevance_score: float,
    rule_priority: str,
    context: DetectedContextModel,
) -> list[ScoredRuleModel]:
    """Load shared and local rules, merge them, and select within budget."""
    shared_rules = await load_shared_rules(manager, context)
    local_rules = get_tagged_local_rules(manager, task_description, min_relevance_score)

    assert manager.synapse_manager is not None
    shared_rules_dicts: list[ModelDict] = [
        cast(ModelDict, rule.model_dump(mode="json")) for rule in shared_rules
    ]
    local_rules_dicts: list[ModelDict] = [
        cast(ModelDict, rule.model_dump(mode="json")) for rule in local_rules
    ]
    merged_rule_dicts = await manager.synapse_manager.merge_rules(
        shared_rules=shared_rules_dicts,
        local_rules=local_rules_dicts,
        priority=rule_priority,
    )
    merged_rules = [ScoredRuleModel.model_validate(rule) for rule in merged_rule_dicts]

    score_rules_if_needed(merged_rules, task_description)
    filtered_rules = filter_rules_by_score(merged_rules, min_relevance_score)
    filtered_rules.sort(
        key=lambda rule: (rule.priority, rule.relevance_score),
        reverse=True,
    )
    return select_rules_within_budget(manager.token_counter, filtered_rules, max_tokens)


def categorize_rules(
    result: RulesResultModel,
    selected_rules: list[ScoredRuleModel],
    context: DetectedContextModel,
) -> None:
    """Categorize selected rules into generic, language, and local categories."""
    generic_rules: list[ScoredRuleModel] = []
    language_rules: list[ScoredRuleModel] = []
    local_rules: list[ScoredRuleModel] = []

    for rule in selected_rules:
        if rule.category == "generic":
            generic_rules.append(rule)
            continue

        if rule.category in context.detected_languages:
            language_rules.append(rule)

        if rule.source == "local":
            local_rules.append(rule)

    result.generic_rules = generic_rules
    result.language_rules = language_rules
    result.local_rules = local_rules


def calculate_total_tokens(rules: list[ScoredRuleModel]) -> int:
    """Calculate total tokens from rules."""
    return sum(rule.tokens for rule in rules)


async def get_local_only_rules(
    manager: RulesManager,
    result: RulesResultModel,
    task_description: str,
    max_tokens: int,
    min_relevance_score: float,
) -> RulesResultModel:
    """Get rules using the local-only (legacy) approach."""
    local_rules = get_local_rules_models(manager, task_description, min_relevance_score)

    selected_rules: list[ScoredRuleModel] = []
    total_tokens = 0

    for rule in local_rules:
        rule_tokens = rule.tokens
        if total_tokens + rule_tokens <= max_tokens:
            selected_rules.append(rule)
            total_tokens += rule_tokens
        else:
            break

    result.local_rules = selected_rules
    result.total_tokens = total_tokens
    result.source = "local_only"

    return result
