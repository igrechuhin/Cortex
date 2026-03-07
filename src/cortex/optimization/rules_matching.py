from __future__ import annotations

from cortex.core.token_counter import TokenCounter

from .models import ScoredRuleModel


def score_rule_relevance(task_description: str, rule_content: str) -> float:
    """
    Score rule relevance to task description.

    Args:
        task_description: Task description
        rule_content: Rule content

    Returns:
        Relevance score in the range [0.0, 1.0]
    """
    task_lower = task_description.lower()
    rule_lower = rule_content.lower()

    task_words = set(task_lower.split())

    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
    }
    filtered_words = {
        word for word in task_words if len(word) > 2 and word not in stop_words
    }

    if not filtered_words:
        return 0.0

    matches = sum(1 for word in filtered_words if word in rule_lower)
    score = matches / len(filtered_words)

    return min(score, 1.0)


def score_rules_if_needed(
    rules: list[ScoredRuleModel],
    task_description: str,
) -> None:
    """Ensure all rules have a relevance score."""
    for rule in rules:
        if rule.relevance_score == 0.0:
            rule.relevance_score = score_rule_relevance(task_description, rule.content)


def filter_rules_by_score(
    rules: list[ScoredRuleModel],
    min_relevance_score: float,
) -> list[ScoredRuleModel]:
    """Filter rules by minimum relevance score."""
    return [rule for rule in rules if rule.relevance_score >= min_relevance_score]


def select_rules_within_budget(
    token_counter: TokenCounter,
    filtered_rules: list[ScoredRuleModel],
    max_tokens: int,
) -> list[ScoredRuleModel]:
    """Select rules within the provided token budget."""
    selected_rules: list[ScoredRuleModel] = []
    total_tokens = 0

    for rule in filtered_rules:
        rule_tokens = rule.tokens

        if rule_tokens == 0:
            rule_tokens = token_counter.count_tokens(rule.content)
            rule.tokens = rule_tokens

        if total_tokens + rule_tokens <= max_tokens:
            selected_rules.append(rule)
            total_tokens += rule_tokens
        else:
            break

    return selected_rules
