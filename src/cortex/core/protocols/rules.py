#!/usr/bin/env python3
"""Rules management protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for custom rules management.
"""

from typing import Protocol

from cortex.optimization.models import (
    RelevantRulesResultModel,
    RulesIndexResultModel,
)


class RulesManagerProtocol(Protocol):
    """Protocol for rules management operations using structural subtyping (PEP 544).

    This protocol defines the interface for managing shared rules repositories,
    indexing rules, and retrieving relevant rules based on task context. Rules
    management enables cross-project rule sharing. A class implementing these
    methods automatically satisfies this protocol.

    Used by:
        - RulesManager: Manages rules from configured repositories
        - MCP Tools: For rules indexing and retrieval operations
        - ContextOptimizer: For including relevant rules in context
        - Client Applications: For rules-based assistance

    Example implementation:
        ```python
        class SimpleRulesManager:
            def __init__(self, rules_dir: Path):
                self.rules_dir = rules_dir
                self.rules_index = {}

            async def index_rules(self, force: bool = False) -> RulesIndexResultModel:
                if not force and self.rules_index:
                    return RulesIndexResultModel(
                        status="cached", rules_count=len(self.rules_index)
                    )

                self.rules_index = {}
                for rule_file in self.rules_dir.rglob("*.md"):
                    content = await self._read_file(rule_file)
                    self.rules_index[str(rule_file)] = {
                        "content": content,
                        "tokens": self.token_counter.count_tokens(content),
                        "keywords": self._extract_keywords(content),
                    }

                return RulesIndexResultModel(
                    status="indexed", rules_count=len(self.rules_index)
                )

            async def get_relevant_rules(
                self,
                task_description: str,
                max_tokens: int | None = None,
                min_relevance: float | None = None,
            ) -> RelevantRulesResultModel:
                scored_rules = []
                for rule_path, rule_data in self.rules_index.items():
                    relevance = self._calculate_relevance(
                        task_description, rule_data["keywords"]
                    )
                    if min_relevance is None or relevance >= min_relevance:
                        scored_rules.append((rule_path, rule_data, relevance))

                scored_rules.sort(key=lambda x: x[2], reverse=True)

                selected = []
                total_tokens = 0
                for rule_path, rule_data, relevance in scored_rules:
                    if max_tokens and (total_tokens + rule_data["tokens"]) > max_tokens:
                        break
                    selected.append({
                        "path": rule_path,
                        "content": rule_data["content"],
                        "relevance": relevance,
                    })
                    total_tokens += rule_data["tokens"]

                from cortex.optimization.models import RelevantRuleModel
                return RelevantRulesResultModel(
                    rules=[
                        RelevantRuleModel(
                            name=rule["path"],
                            content=rule["content"],
                            relevance_score=rule["relevance"],
                            tokens=rule_data["tokens"]
                        )
                        for rule in selected
                    ],
                    total_tokens=total_tokens
                )

        # SimpleRulesManager automatically satisfies RulesManagerProtocol
        ```

    Note:
        - Rules indexing for fast retrieval
        - Relevance-based rule selection
        - Token budget management
    """

    async def index_rules(self, force: bool = False) -> RulesIndexResultModel:
        """Index rules from configured folder.

        Args:
            force: Force re-indexing even if cache is fresh

        Returns:
            Indexing result model
        """
        ...

    async def get_relevant_rules(
        self,
        task_description: str,
        max_tokens: int | None = None,
        min_relevance: float | None = None,
    ) -> RelevantRulesResultModel:
        """Get rules relevant to a task.

        Args:
            task_description: Task description for relevance scoring
            max_tokens: Maximum tokens to return (no limit if None)
            min_relevance: Minimum relevance score (default from config if None)

        Returns:
            Relevant rules result model
        """
        ...


__all__ = [
    "RulesManagerProtocol",
]
