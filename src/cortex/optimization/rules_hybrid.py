"""
Hybrid rules loading for RulesManager.

Handles detection of context, loading shared/local rules, merging, and
categorisation into generic / language / local buckets.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from cortex.core.models import ModelDict
from cortex.core.protocols.token import TokenCounterProtocol
from cortex.optimization.models import OptimizationRuleCategory
from cortex.rules.synapse_manager import SynapseManager

from .models import (
    DetectedContextModel,
    RulesResultModel,
    ScoredRuleModel,
)

logger = logging.getLogger(__name__)


def _coerce_rule_category(raw_category: object) -> OptimizationRuleCategory:
    """Convert untyped category payloads to the scoring model enum."""
    if isinstance(raw_category, OptimizationRuleCategory):
        return raw_category
    if isinstance(raw_category, str):
        try:
            return OptimizationRuleCategory(raw_category)
        except ValueError:
            return OptimizationRuleCategory.UNKNOWN
    return OptimizationRuleCategory.UNKNOWN


class RulesHybridMixin:
    """Mixin providing hybrid (shared + local) rules resolution."""

    def _require_synapse_manager(self) -> SynapseManager:
        """Return synapse_manager or raise a clear configuration error."""
        synapse_manager: SynapseManager | None = getattr(self, "synapse_manager", None)
        if synapse_manager is None:
            raise RuntimeError(
                "synapse_manager is required for hybrid rules but was not configured; pass synapse_manager to RulesManager.__init__"
            )
        return synapse_manager

    # ---- hybrid entry-point ------------------------------------------------

    async def _get_hybrid_rules(
        self,
        result: RulesResultModel,
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
        project_files: list[Path] | None,
        rule_priority: str,
    ) -> RulesResultModel:
        """Get rules using hybrid (shared + local) approach."""
        context = await self._detect_and_load_context(
            result, task_description, project_files
        )

        selected_rules = await self._load_and_merge_rules(
            task_description, max_tokens, min_relevance_score, rule_priority, context
        )

        self._categorize_rules(result, selected_rules, context)
        result.total_tokens = self._calculate_total_tokens(selected_rules)
        return result

    # ---- context detection --------------------------------------------------

    async def _detect_and_load_context(
        self,
        result: RulesResultModel,
        task_description: str,
        project_files: list[Path] | None,
    ) -> DetectedContextModel:
        """Detect context and update result structure."""
        sm = self._require_synapse_manager()
        context_dict = await sm.detect_context(task_description, project_files)
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

    # ---- load & merge -------------------------------------------------------

    async def _load_and_merge_rules(
        self,
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
        rule_priority: str,
        context: DetectedContextModel,
    ) -> list[ScoredRuleModel]:
        """Load shared and local rules, merge them, select within budget."""
        shared_rules = await self._load_shared_rules(context)

        local_rules = await self._get_tagged_local_rules(
            task_description, min_relevance_score
        )

        sm = self._require_synapse_manager()
        shared_rules_dicts: list[ModelDict] = [
            cast(ModelDict, rule.model_dump(mode="json")) for rule in shared_rules
        ]
        local_rules_dicts: list[ModelDict] = [
            cast(ModelDict, rule.model_dump(mode="json")) for rule in local_rules
        ]
        merged_rule_dicts = await sm.merge_rules(
            shared_rules=shared_rules_dicts,
            local_rules=local_rules_dicts,
            priority=rule_priority,
        )
        merged_rules = [
            ScoredRuleModel.model_validate(rule) for rule in merged_rule_dicts
        ]

        return await self._select_within_budget_models(
            merged_rules, task_description, max_tokens, min_relevance_score
        )

    async def _load_shared_rules(
        self, context: DetectedContextModel
    ) -> list[ScoredRuleModel]:
        """Load shared rules based on detected context."""
        sm = self._require_synapse_manager()
        categories = await sm.get_relevant_categories(
            cast(ModelDict, context.model_dump(mode="json"))
        )

        shared_rules: list[ScoredRuleModel] = []
        for category in categories:
            category_rules = await sm.load_category(category)
            for loaded_rule in category_rules:
                try:
                    shared_rule = self._build_shared_rule(loaded_rule)
                except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
                    logger.debug("_load_shared_rules: skip invalid rule: %s", exc)
                    continue
                if shared_rule is not None:
                    shared_rules.append(shared_rule)

        return shared_rules

    def _build_shared_rule(self, loaded_rule: object) -> ScoredRuleModel | None:
        """Build a scored shared rule from a loaded rule object."""
        token_counter_obj = getattr(self, "token_counter", None)
        if token_counter_obj is None:
            raise RuntimeError(
                "token_counter is required but was not configured; pass token_counter to RulesManager.__init__"
            )

        token_counter = cast("TokenCounterProtocol", token_counter_obj)

        content = getattr(loaded_rule, "content", None)
        file = getattr(loaded_rule, "file", None)
        if content is None or file is None:
            raise ValueError("loaded_rule is missing required attributes")

        tokens = token_counter.count_tokens(content)

        return ScoredRuleModel(
            file=file,
            name=file,
            content=content,
            tokens=tokens,
            relevance_score=0.0,
            sections=[],
            source="shared",
            priority=getattr(loaded_rule, "priority", 0),
            category=_coerce_rule_category(getattr(loaded_rule, "category", "")),
        )

    async def _get_tagged_local_rules(
        self, task_description: str, min_relevance_score: float
    ) -> list[ScoredRuleModel]:
        """Get local rules and tag them with source."""
        local_rules = self._get_local_rules_models(
            task_description, min_relevance_score
        )
        for rule in local_rules:
            rule.source = "local"
        return local_rules

    # ---- categorisation -----------------------------------------------------

    def _categorize_rules(
        self,
        result: RulesResultModel,
        selected_rules: list[ScoredRuleModel],
        context: DetectedContextModel,
    ) -> None:
        """Categorize selected rules into generic, language, local."""
        generic_rules: list[ScoredRuleModel] = []
        language_rules: list[ScoredRuleModel] = []
        local_rules: list[ScoredRuleModel] = []

        for rule in selected_rules:
            if rule.category == OptimizationRuleCategory.UNKNOWN:
                generic_rules.append(rule)
                continue
            self._categorize_non_generic_rule(
                rule, context, language_rules, local_rules
            )

        result.generic_rules = generic_rules
        result.language_rules = language_rules
        result.local_rules = local_rules

    def _categorize_non_generic_rule(
        self,
        rule: ScoredRuleModel,
        context: DetectedContextModel,
        language_rules: list[ScoredRuleModel],
        local_rules: list[ScoredRuleModel],
    ) -> None:
        """Categorize a non-generic rule into language or local."""
        if rule.category in context.detected_languages:
            language_rules.append(rule)
        elif rule.source == "local":
            local_rules.append(rule)

    def _calculate_total_tokens(self, rules: list[ScoredRuleModel]) -> int:
        """Calculate total tokens from rules."""
        return sum(rule.tokens for rule in rules)

    # ---- helpers required by mixin (implemented in RulesScoringMixin/RulesManager) ----

    def _get_local_rules_models(
        self, task_description: str, min_relevance_score: float
    ) -> list[ScoredRuleModel]:
        """Stub — implemented in RulesManager."""
        raise NotImplementedError(
            "RulesHybridMixin requires _get_local_rules_models(...) to be implemented by RulesManager (hybrid owner contract)."
        )  # pragma: no cover

    async def _select_within_budget_models(
        self,
        rules: list[ScoredRuleModel],
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
    ) -> list[ScoredRuleModel]:
        """Stub — implemented in RulesScoringMixin."""
        raise NotImplementedError(
            "RulesHybridMixin requires _select_within_budget_models(...) to be implemented by RulesScoringMixin (hybrid owner contract)."
        )  # pragma: no cover
