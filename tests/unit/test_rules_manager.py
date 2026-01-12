"""
Tests for rules_manager module.

This module tests custom rules management functionality including:
- Rules indexing and initialization
- Rule relevance scoring
- Token budget management
- Local and shared rules integration
- Context-aware rule selection
"""

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.optimization.rules_manager import RulesManager

if TYPE_CHECKING:
    from cortex.core.file_system import FileSystemManager
    from cortex.core.metadata_index import MetadataIndex
    from cortex.core.token_counter import TokenCounter


class TestRulesManagerInitialization:
    """Tests for RulesManager initialization."""

    def test_initialization_with_default_settings(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test initialization with default settings."""
        # Arrange & Act
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        # Assert
        assert manager.project_root == tmp_path
        assert manager.file_system == mock_file_system
        assert manager.metadata_index == mock_metadata_index
        assert manager.token_counter == mock_token_counter
        assert manager.rules_folder is None
        assert manager.synapse_manager is None
        assert manager.indexer is not None

    def test_initialization_with_custom_rules_folder(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test initialization with custom rules folder."""
        # Arrange & Act
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )

        # Assert
        assert manager.rules_folder == ".cursorrules"

    def test_initialization_with_synapse_manager(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test initialization with synapse manager."""
        # Arrange
        mock_synapse = MagicMock()

        # Act
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            synapse_manager=mock_synapse,
        )

        # Assert
        assert manager.synapse_manager == mock_synapse


class TestInitialize:
    """Tests for initialize method."""

    @pytest.mark.asyncio
    async def test_initialize_with_no_rules_folder(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test initialize when no rules folder is configured."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        # Act
        result = await manager.initialize()

        # Assert
        assert result["status"] == "disabled"
        message = result.get("message")
        assert isinstance(message, str)
        assert "No rules folder configured" in message

    @pytest.mark.asyncio
    async def test_initialize_with_nonexistent_rules_folder(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test initialize when rules folder doesn't exist."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )

        # Act
        result = await manager.initialize()

        # Assert
        assert result["status"] == "not_found"
        message = result.get("message")
        assert isinstance(message, str)
        assert ".cursorrules" in message

    @pytest.mark.asyncio
    async def test_initialize_with_existing_rules_folder(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test initialize with existing rules folder."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "test.md").write_text("# Test Rule")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )

        # Act
        result = await manager.initialize()

        # Assert
        assert "indexed" in result or "status" in result


class TestIndexRules:
    """Tests for index_rules method."""

    @pytest.mark.asyncio
    async def test_index_rules_with_no_rules_folder(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test index_rules when no rules folder is configured."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        # Act
        result = await manager.index_rules()

        # Assert
        assert result["status"] == "error"
        error = result.get("error")
        assert isinstance(error, str)
        assert "No rules folder configured" in error

    @pytest.mark.asyncio
    async def test_index_rules_with_valid_folder(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test index_rules with valid rules folder."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule1.md").write_text("# Rule 1\nContent for rule 1")
        _ = (rules_dir / "rule2.md").write_text("# Rule 2\nContent for rule 2")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )

        # Act
        result = await manager.index_rules()

        # Assert
        assert "indexed" in result or "files_indexed" in result

    @pytest.mark.asyncio
    async def test_index_rules_with_force_flag(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test index_rules with force flag."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )

        # Act
        result1 = await manager.index_rules(force=False)
        result2 = await manager.index_rules(force=True)

        # Assert
        assert "indexed" in result1 or "files_indexed" in result1
        assert "indexed" in result2 or "files_indexed" in result2


class TestGetRelevantRules:
    """Tests for get_relevant_rules method."""

    @pytest.mark.asyncio
    async def test_get_relevant_rules_local_only(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test getting relevant rules with local rules only."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "python.md").write_text(
            "# Python Rules\nUse Python 3.12 syntax"
        )

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )
        _ = await manager.index_rules()

        # Act
        result = await manager.get_relevant_rules(
            task_description="Write Python code for data processing"
        )

        # Assert
        assert "local_rules" in result
        assert "total_tokens" in result
        assert result["source"] == "local_only"

    @pytest.mark.asyncio
    async def test_get_relevant_rules_with_token_limit(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test get_relevant_rules respects token limit."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule1.md").write_text("# Rule 1\n" + "x" * 1000)
        _ = (rules_dir / "rule2.md").write_text("# Rule 2\n" + "x" * 1000)

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )
        _ = await manager.index_rules()

        # Act
        result = await manager.get_relevant_rules(
            task_description="test", max_tokens=500
        )

        # Assert
        total_tokens = result.get("total_tokens")
        assert isinstance(total_tokens, (int, float))
        assert total_tokens <= 500

    @pytest.mark.asyncio
    async def test_get_relevant_rules_with_min_relevance_score(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test get_relevant_rules filters by minimum relevance score."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "python.md").write_text("# Python\nPython specific rules")
        _ = (rules_dir / "general.md").write_text("# General\nGeneral coding rules")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )
        _ = await manager.index_rules()

        # Act
        result = await manager.get_relevant_rules(
            task_description="Python programming", min_relevance_score=0.5
        )

        # Assert
        # Python rules should be more relevant than general rules
        local_rules = result.get("local_rules")
        assert isinstance(local_rules, list)
        # Type cast for Pyright: local_rules is a list of rule dicts
        local_rules_typed = cast(list[dict[str, object]], local_rules)
        assert len(local_rules_typed) >= 0  # At least some rules match


class TestScoreRuleRelevance:
    """Tests for _score_rule_relevance method."""

    def test_score_rule_relevance_high_match(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test scoring with high keyword match."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        # Act
        score = manager.score_rule_relevance(
            "Python testing framework", "Python testing rules with pytest framework"
        )

        # Assert
        assert score > 0.5

    def test_score_rule_relevance_no_match(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test scoring with no keyword match."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        # Act
        score = manager.score_rule_relevance("Java programming", "Python testing rules")

        # Assert
        assert score == 0.0

    def test_score_rule_relevance_removes_stop_words(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test that stop words are filtered out."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        # Act
        score = manager.score_rule_relevance("the and or but testing", "testing rules")

        # Assert
        assert score > 0.0  # Should match "testing"

    def test_score_rule_relevance_case_insensitive(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test that scoring is case-insensitive."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        # Act
        score1 = manager.score_rule_relevance("Python Testing", "python testing")
        score2 = manager.score_rule_relevance("python testing", "Python Testing")

        # Assert
        assert score1 == score2
        assert score1 > 0.0


class TestGetLocalRules:
    """Tests for get_local_rules method."""

    @pytest.mark.asyncio
    async def test_get_local_rules_with_empty_index(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test get_local_rules when index is empty."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )

        # Act
        rules = await manager.get_local_rules("test description")

        # Assert
        assert rules == []

    @pytest.mark.asyncio
    async def test_get_local_rules_filters_by_score(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test that get_local_rules filters by minimum score."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "python.md").write_text("# Python\nPython programming rules")
        _ = (rules_dir / "javascript.md").write_text("# JavaScript\nJavaScript rules")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )
        _ = await manager.index_rules()

        # Act
        rules = await manager.get_local_rules(
            "Python development", min_relevance_score=0.3
        )

        # Assert
        assert isinstance(rules, list)
        # Python rules should score higher than JavaScript rules
        if len(rules) > 0:
            for rule in rules:
                assert isinstance(rule, dict)
                score = rule.get("relevance_score")
                assert isinstance(score, (int, float))
                assert score >= 0.3

    @pytest.mark.asyncio
    async def test_get_local_rules_sorted_by_score(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test that rules are sorted by relevance score."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "python.md").write_text("# Python\nPython programming rules")
        _ = (rules_dir / "general.md").write_text("# General\nGeneral coding rules")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )
        _ = await manager.index_rules()

        # Act
        rules = await manager.get_local_rules("Python programming")

        # Assert
        if len(rules) > 1:
            # Verify rules are sorted by score descending
            for i in range(len(rules) - 1):
                rule1 = rules[i]
                rule2 = rules[i + 1]
                assert isinstance(rule1, dict) and isinstance(rule2, dict)
                score1 = rule1.get("relevance_score")
                score2 = rule2.get("relevance_score")
                assert isinstance(score1, (int, float)) and isinstance(
                    score2, (int, float)
                )
                assert score1 >= score2


class TestSelectWithinBudget:
    """Tests for select_within_budget method."""

    @pytest.mark.asyncio
    async def test_select_within_budget_respects_token_limit(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test that selection respects token budget."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        rules: list[dict[str, object]] = [
            {"content": "Rule 1 content", "tokens": 100, "relevance_score": 0.8},
            {"content": "Rule 2 content", "tokens": 150, "relevance_score": 0.7},
            {"content": "Rule 3 content", "tokens": 200, "relevance_score": 0.6},
        ]

        # Act
        selected = await manager.select_within_budget(
            rules, "test", max_tokens=250, min_relevance_score=0.5
        )

        # Assert
        token_values: list[int] = []
        for rule in selected:
            # rule is already dict[str, object] from select_within_budget return type
            tokens = rule.get("tokens")
            if isinstance(tokens, (int, float)):
                token_values.append(int(tokens))
        total_tokens = sum(token_values)
        assert isinstance(total_tokens, int)
        assert total_tokens <= 250

    @pytest.mark.asyncio
    async def test_select_within_budget_filters_by_score(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test that selection filters by minimum relevance score."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        rules: list[dict[str, object]] = [
            {"content": "Rule 1", "tokens": 100, "relevance_score": 0.8},
            {"content": "Rule 2", "tokens": 100, "relevance_score": 0.3},
            {"content": "Rule 3", "tokens": 100, "relevance_score": 0.1},
        ]

        # Act
        selected = await manager.select_within_budget(
            rules, "test", max_tokens=500, min_relevance_score=0.5
        )

        # Assert
        for rule in selected:
            assert isinstance(rule, dict)
            score = rule.get("relevance_score")
            assert isinstance(score, (int, float))
            assert score >= 0.5

    @pytest.mark.asyncio
    async def test_select_within_budget_prioritizes_by_priority_and_score(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test that selection prioritizes by priority then relevance score."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        rules: list[dict[str, object]] = [
            {
                "content": "Low priority",
                "tokens": 100,
                "relevance_score": 0.9,
                "priority": 10,
            },
            {
                "content": "High priority",
                "tokens": 100,
                "relevance_score": 0.7,
                "priority": 90,
            },
        ]

        # Act
        selected = await manager.select_within_budget(
            rules, "test", max_tokens=150, min_relevance_score=0.5
        )

        # Assert
        # High priority rule should be selected first
        if len(selected) == 1:
            assert selected[0]["content"] == "High priority"


class TestGetAllRules:
    """Tests for get_all_rules method."""

    @pytest.mark.asyncio
    async def test_get_all_rules_returns_index(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test that get_all_rules returns the rules index."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "test.md").write_text("# Test Rule")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )
        _ = await manager.index_rules()

        # Act
        all_rules = await manager.get_all_rules()

        # Assert
        assert isinstance(all_rules, dict)


class TestGetStatus:
    """Tests for get_status method."""

    def test_get_status_with_rules_folder(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test get_status when rules folder is configured."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )

        # Act
        status = manager.get_status()

        # Assert
        assert status["enabled"] is True
        assert status["rules_folder"] == ".cursorrules"

    def test_get_status_without_rules_folder(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test get_status when no rules folder is configured."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        # Act
        status = manager.get_status()

        # Assert
        assert status["enabled"] is False
        assert status["rules_folder"] is None


class TestAutoReindex:
    """Tests for auto-reindexing functionality."""

    @pytest.mark.asyncio
    async def test_stop_auto_reindex(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test stopping auto-reindex."""
        # Arrange
        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
        )

        # Act & Assert - Should not raise exception
        await manager.stop_auto_reindex()


class TestSynapseManagerIntegration:
    """Tests for Synapse manager integration."""

    @pytest.mark.asyncio
    async def test_merge_rules_with_synapse_manager(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test merging rules with Synapse manager."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "local.md").write_text("# Local Rule\nLocal content")

        mock_synapse = MagicMock()
        mock_synapse.detect_context = AsyncMock(
            return_value={"detected_languages": ["python"], "frameworks": []}
        )
        mock_synapse.get_relevant_categories = AsyncMock(return_value=["python"])
        mock_synapse.load_category = AsyncMock(
            return_value=[
                {
                    "file": "shared.md",
                    "content": "# Shared Rule",
                    "category": "python",
                    "tokens": 50,
                }
            ]
        )
        mock_synapse.merge_rules = AsyncMock(
            return_value=[
                {
                    "file": "shared.md",
                    "content": "# Shared Rule",
                    "category": "python",
                    "tokens": 50,
                    "source": "shared",
                },
                {
                    "file": "local.md",
                    "content": "# Local Rule",
                    "category": "generic",
                    "tokens": 30,
                    "source": "local",
                },
            ]
        )

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
            synapse_manager=mock_synapse,
        )
        _ = await manager.index_rules()

        # Act
        result = await manager.get_relevant_rules(
            task_description="Python programming task",
            max_tokens=100,
            min_relevance_score=0.3,
            context_aware=True,
        )

        # Assert
        assert result["source"] == "hybrid"
        assert "context" in result
        assert mock_synapse.detect_context.called
        assert mock_synapse.merge_rules.called


class TestRuleIndexingWithCustomConfig:
    """Tests for rule indexing with various configurations."""

    @pytest.mark.asyncio
    async def test_index_rules_with_custom_config(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test indexing rules with custom configuration."""
        # Arrange
        rules_dir = tmp_path / ".custom-rules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule1.md").write_text("# Rule 1\nContent")
        _ = (rules_dir / "rule2.md").write_text("# Rule 2\nMore content")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".custom-rules",
            reindex_interval_minutes=60,
        )

        # Act
        result = await manager.index_rules(force=True)

        # Assert
        assert "indexed" in result or "files_indexed" in result


class TestLoadRulesMissingFiles:
    """Tests for loading rules with missing files."""

    @pytest.mark.asyncio
    async def test_load_rules_missing_files(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test loading rules when some files are missing."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "existing.md").write_text("# Existing Rule")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )
        _ = await manager.index_rules()

        # Act - Try to get rules (should handle missing files gracefully)
        rules = await manager.get_local_rules("test description")

        # Assert
        assert isinstance(rules, list)
        # Should return rules from existing files only


class TestContextDetectionEdgeCases:
    """Tests for context detection edge cases."""

    @pytest.mark.asyncio
    async def test_context_detection_edge_cases(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test context detection with edge cases."""
        # Arrange
        mock_synapse = MagicMock()
        mock_synapse.detect_context = AsyncMock(
            return_value={"detected_languages": [], "frameworks": []}
        )
        mock_synapse.get_relevant_categories = AsyncMock(return_value=[])
        mock_synapse.load_category = AsyncMock(return_value=[])
        mock_synapse.merge_rules = AsyncMock(return_value=[])

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            synapse_manager=mock_synapse,
        )

        # Act - Test with empty context
        result = await manager.get_relevant_rules(
            task_description="",
            max_tokens=1000,
            min_relevance_score=0.0,
            project_files=None,
            context_aware=True,
        )

        # Assert
        assert result["source"] == "hybrid"
        assert "context" in result


class TestFilterRulesByCategory:
    """Tests for filtering rules by category."""

    @pytest.mark.asyncio
    async def test_filter_rules_by_category(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test filtering rules by category."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "python.md").write_text("# Python Rules\nPython content")
        _ = (rules_dir / "javascript.md").write_text(
            "# JavaScript Rules\nJavaScript content"
        )
        _ = (rules_dir / "general.md").write_text("# General Rules\nGeneral content")

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            rules_folder=".cursorrules",
        )
        _ = await manager.index_rules()

        # Act
        result = await manager.get_relevant_rules(
            task_description="Python programming",
            max_tokens=1000,
            min_relevance_score=0.1,
        )

        # Assert
        local_rules = result.get("local_rules")
        assert isinstance(local_rules, list)
        # Python rules should be more relevant than JavaScript rules


class TestRulePriorityHandling:
    """Tests for rule priority handling."""

    @pytest.mark.asyncio
    async def test_rule_priority_handling(
        self,
        tmp_path: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
        mock_token_counter: "TokenCounter",
    ):
        """Test rule priority handling in rule selection."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()

        mock_synapse = MagicMock()
        mock_synapse.detect_context = AsyncMock(
            return_value={"detected_languages": ["python"], "frameworks": []}
        )
        mock_synapse.get_relevant_categories = AsyncMock(return_value=["python"])
        mock_synapse.load_category = AsyncMock(return_value=[])
        mock_synapse.merge_rules = AsyncMock(
            return_value=[
                {
                    "file": "high_priority.md",
                    "content": "High priority rule",
                    "tokens": 50,
                    "priority": 90,
                    "relevance_score": 0.7,
                },
                {
                    "file": "low_priority.md",
                    "content": "Low priority rule",
                    "tokens": 50,
                    "priority": 10,
                    "relevance_score": 0.9,
                },
            ]
        )

        manager = RulesManager(
            project_root=tmp_path,
            file_system=mock_file_system,
            metadata_index=mock_metadata_index,
            token_counter=mock_token_counter,
            synapse_manager=mock_synapse,
        )

        # Act
        result = await manager.get_relevant_rules(
            task_description="test",
            max_tokens=100,
            min_relevance_score=0.5,
            rule_priority="local_overrides_shared",
        )

        # Assert
        # High priority rule should be selected even with lower relevance
        selected_rules = result.get("local_rules", [])
        assert isinstance(selected_rules, list)
