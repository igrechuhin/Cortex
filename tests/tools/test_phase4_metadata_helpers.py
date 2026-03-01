"""Tests for Phase 4 metadata helpers including role-based scoring."""

from cortex.core.models import ModelDict
from cortex.optimization.agent_roles import AgentRole
from cortex.tools.metadata_helpers import calculate_metadata_relevance_scores


class TestCalculateMetadataRelevanceScores:
    """Tests for calculate_metadata_relevance_scores function."""

    def test_basic_relevance_scoring_without_role(self) -> None:
        """Test basic relevance scoring without agent role."""
        # Arrange
        task_description = "Fix bug in authentication"
        files_metadata: dict[str, ModelDict] = {
            "activeContext.md": {
                "sections": [{"heading": "## Authentication", "level": 2}],
                "last_modified": "2026-02-17",
            },
            "progress.md": {
                "sections": [{"heading": "## Recent Work", "level": 2}],
                "last_modified": "2026-02-17",
            },
        }

        # Act
        scores = calculate_metadata_relevance_scores(
            task_description, files_metadata, agent_role=None
        )

        # Assert
        assert "activeContext.md" in scores
        assert "progress.md" in scores
        # activeContext should score higher due to "authentication" keyword match
        assert scores["activeContext.md"] > scores["progress.md"]

    def test_relevance_scoring_with_quality_role(self) -> None:
        """Test that quality role boosts techContext and systemPatterns."""
        # Arrange
        task_description = "Run quality checks"
        files_metadata: dict[str, ModelDict] = {
            "techContext.md": {
                "sections": [{"heading": "## Tech Stack", "level": 2}],
                "last_modified": "2026-02-17",
            },
            "systemPatterns.md": {
                "sections": [{"heading": "## Patterns", "level": 2}],
                "last_modified": "2026-02-17",
            },
            "productContext.md": {
                "sections": [{"heading": "## Product", "level": 2}],
                "last_modified": "2026-02-17",
            },
        }

        # Act
        scores_without_role = calculate_metadata_relevance_scores(
            task_description, files_metadata, agent_role=None
        )
        scores_with_role = calculate_metadata_relevance_scores(
            task_description, files_metadata, agent_role=AgentRole.QUALITY
        )

        # Assert
        # Quality role should boost techContext and systemPatterns
        assert (
            scores_with_role["techContext.md"] > scores_without_role["techContext.md"]
        )
        assert (
            scores_with_role["systemPatterns.md"]
            > scores_without_role["systemPatterns.md"]
        )
        # productContext should be slightly penalized (not in quality focus)
        assert (
            scores_with_role["productContext.md"]
            <= scores_without_role["productContext.md"]
        )

    def test_relevance_scoring_with_docs_role(self) -> None:
        """Test that docs role boosts projectBrief and productContext."""
        # Arrange
        task_description = "Update documentation"
        files_metadata: dict[str, ModelDict] = {
            "projectBrief.md": {
                "sections": [{"heading": "## Overview", "level": 2}],
                "last_modified": "2026-02-17",
            },
            "productContext.md": {
                "sections": [{"heading": "## Product", "level": 2}],
                "last_modified": "2026-02-17",
            },
            "techContext.md": {
                "sections": [{"heading": "## Tech", "level": 2}],
                "last_modified": "2026-02-17",
            },
        }

        # Act
        scores_without_role = calculate_metadata_relevance_scores(
            task_description, files_metadata, agent_role=None
        )
        scores_with_role = calculate_metadata_relevance_scores(
            task_description, files_metadata, agent_role=AgentRole.DOCS
        )

        # Assert
        # Docs role should boost projectBrief and productContext
        assert (
            scores_with_role["projectBrief.md"] > scores_without_role["projectBrief.md"]
        )
        assert (
            scores_with_role["productContext.md"]
            > scores_without_role["productContext.md"]
        )
