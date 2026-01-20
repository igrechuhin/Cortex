#!/usr/bin/env python3
"""Optimization protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for context optimization,
relevance scoring, progressive loading, and content summarization.
"""

from typing import Protocol


class RelevanceScorerProtocol(Protocol):
    """Protocol for relevance scoring operations using structural subtyping (PEP 544).

    This protocol defines the interface for scoring files and sections by their
    relevance to a given task description. Relevance scoring enables intelligent
    context selection and prioritization. Any class implementing these methods
    automatically satisfies this protocol.

    Used by:
        - RelevanceScorer: TF-IDF and keyword-based relevance scoring
        - ContextOptimizer: For selecting most relevant files within budget
        - ProgressiveLoader: For loading files in relevance order
        - MCP Tools: For context optimization queries

    Example implementation:
        ```python
        from sklearn.feature_extraction.text import TfidfVectorizer

        class SimpleRelevanceScorer:
            async def score_files(
                self,
                task_description: str,
                files_content: dict[str, str],
                files_metadata: dict[str, dict[str, object]],
                quality_scores: dict[str, float] | None = None,
            ) -> dict[str, dict[str, float | str]]:
                vectorizer = TfidfVectorizer()
                corpus = [task_description] + list(files_content.values())
                tfidf_matrix = vectorizer.fit_transform(corpus)

                # Calculate cosine similarity
                scores = {}
                for idx, (file_name, _) in enumerate(files_content.items(), 1):
                    similarity = cosine_similarity(tfidf_matrix[0], tfidf_matrix[idx])[0][0]
                    quality = quality_scores.get(file_name, 1.0) if quality_scores else 1.0
                    scores[file_name] = {
                        "relevance_score": similarity * quality,
                        "tfidf_score": similarity,
                        "quality_boost": quality,
                    }
                return scores

            async def score_sections(
                self, task_description: str, file_name: str, content: str
            ) -> list[dict[str, object]]:
                # Parse and score sections
                sections = self._parse_sections(content)
                return sorted(
                    [
                        {
                            "title": s["title"],
                            "score": self._score_section(task_description, s),
                            "start_line": s["start_line"],
                            "end_line": s["end_line"],
                        }
                        for s in sections
                    ],
                    key=lambda x: x["score"],
                    reverse=True,
                )

        # SimpleRelevanceScorer automatically satisfies RelevanceScorerProtocol
        ```

    Note:
        - TF-IDF provides keyword-based relevance
        - Quality scores can boost high-quality files
        - Section-level scoring enables fine-grained context selection
    """

    async def score_files(
        self,
        task_description: str,
        files_content: dict[str, str],
        files_metadata: dict[str, dict[str, object]],
        quality_scores: dict[str, float] | None = None,
    ) -> dict[str, dict[str, float | str]]:
        """Score files by relevance to task.

        Args:
            task_description: Description of the task
            files_content: Dict mapping file names to content
            files_metadata: Dict mapping file names to metadata
            quality_scores: Optional dict mapping file names to quality scores

        Returns:
            Dict mapping file names to score breakdown
        """
        ...

    async def score_sections(
        self, task_description: str, file_name: str, content: str
    ) -> list[dict[str, object]]:
        """Score sections within a file.

        Args:
            task_description: Description of the task
            file_name: Name of file
            content: File content

        Returns:
            List of section score dictionaries
        """
        ...


class ContextOptimizerProtocol(Protocol):
    """Protocol for context optimization operations using structural subtyping (PEP 544).

    This protocol defines the interface for optimizing context selection within
    token budgets using various strategies (relevance-based, dependency-based,
    or hybrid). Context optimization ensures the most valuable information fits
    within model context limits. Any class implementing these methods
    automatically satisfies this protocol.

    Used by:
        - ContextOptimizer: Multi-strategy context optimizer with token budgeting
        - MCP Tools: For load_context operations
        - ProgressiveLoader: For budget-aware context loading
        - Client Applications: For intelligent context management

    Example implementation:
        ```python
        class SimpleContextOptimizer:
            async def optimize(
                self,
                task_description: str,
                files_content: dict[str, str],
                files_metadata: dict[str, dict[str, object]],
                strategy: str = "hybrid",
                token_budget: int | None = None,
                mandatory_files: list[str] | None = None,
            ) -> dict[str, object]:
                # Score files by relevance
                scored = await self.scorer.score_files(task_description, files_content, files_metadata)
                sorted_files = sorted(scored.items(), key=lambda x: x[1]["relevance_score"], reverse=True)

                # Select files within budget
                selected = {}
                total_tokens = 0

                # Mandatory files first
                for fname in (mandatory_files or []):
                    selected[fname] = files_content[fname]
                    total_tokens += self.token_counter.count_tokens(files_content[fname])

                # Add by relevance
                for fname, _ in sorted_files:
                    if fname in selected:
                        continue
                    tokens = self.token_counter.count_tokens(files_content[fname])
                    if token_budget and (total_tokens + tokens) > token_budget:
                        break
                    selected[fname] = files_content[fname]
                    total_tokens += tokens

                return {"selected_files": selected, "total_tokens": total_tokens}

        # SimpleContextOptimizer automatically satisfies ContextOptimizerProtocol
        ```

    Note:
        - Multiple strategies: relevance, dependency, hybrid
        - Mandatory files always included
        - Token budget enforced strictly
    """

    async def optimize(
        self,
        task_description: str,
        files_content: dict[str, str],
        files_metadata: dict[str, dict[str, object]],
        strategy: str = "hybrid",
        token_budget: int | None = None,
        mandatory_files: list[str] | None = None,
    ) -> dict[str, object]:
        """Optimize context within token budget.

        Args:
            task_description: Description of task
            files_content: Available files content
            files_metadata: Files metadata
            strategy: Optimization strategy
            token_budget: Max tokens allowed
            mandatory_files: Files that must be included

        Returns:
            Optimization result dictionary
        """
        ...


__all__ = [
    "RelevanceScorerProtocol",
    "ContextOptimizerProtocol",
]
