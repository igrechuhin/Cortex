"""
Scoring and budget-selection logic for RulesManager.

Provides keyword-based relevance scoring and token-budget selection as a mixin.
"""

from __future__ import annotations

from cortex.core.token_counter import TokenCounter

from .models import ScoredRuleModel
from .rules_matching import (
    filter_rules_by_score,
    score_rules_if_needed,
    select_rules_within_budget,
)

_STOP_WORDS: frozenset[str] = frozenset(
    {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
)


class RulesScoringMixin:
    """Mixin providing relevance scoring and budget selection."""

    token_counter: TokenCounter | None = None

    def _require_token_counter(self) -> TokenCounter:
        """Return token_counter or raise a clear configuration error."""
        if self.token_counter is None:
            raise RuntimeError(
                "token_counter is required but was not configured; pass token_counter to RulesManager.__init__"
            )
        return self.token_counter

    # ---- public scoring ----------------------------------------------------

    def score_rule_relevance(self, task_description: str, rule_content: str) -> float:
        """
        Score rule relevance to task description.

        Args:
            task_description: Task description
            rule_content: Rule content

        Returns:
            Relevance score (0.0 - 1.0)
        """
        task_lower = task_description.lower()
        rule_lower = rule_content.lower()

        task_words = {
            w for w in task_lower.split() if len(w) > 2 and w not in _STOP_WORDS
        }
        if not task_words:
            return 0.0

        matches = sum(1 for word in task_words if word in rule_lower)
        return min(matches / len(task_words), 1.0)

    # ---- budget selection ---------------------------------------------------

    async def select_within_budget(
        self,
        rules: list[ScoredRuleModel],
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
    ) -> list[ScoredRuleModel]:
        """
        Select rules within token budget with relevance scoring.

        Args:
            rules: List of rules to select from
            task_description: Task description for scoring
            max_tokens: Maximum token budget
            min_relevance_score: Minimum relevance score

        Returns:
            Selected rules within budget
        """
        return await self._select_within_budget_models(
            rules, task_description, max_tokens, min_relevance_score
        )

    async def _select_within_budget_models(
        self,
        rules: list[ScoredRuleModel],
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
    ) -> list[ScoredRuleModel]:
        """Select rules within budget returning typed models (internal)."""
        score_rules_if_needed(rules, task_description)
        filtered_rules = filter_rules_by_score(rules, min_relevance_score)
        filtered_rules.sort(
            key=lambda rule: (rule.priority, rule.relevance_score),
            reverse=True,
        )
        return select_rules_within_budget(
            self._require_token_counter(), filtered_rules, max_tokens
        )
