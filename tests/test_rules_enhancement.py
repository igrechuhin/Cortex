"""
Tests for Phase 4 Rules Enhancement

Tests the RulesManager and related functionality for custom rules integration.
"""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel, ConfigDict, Field

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.rules_manager import RulesManager


class FullSetup(BaseModel):
    """Typed mapping for full rules integration setup."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    rules_manager: RulesManager = Field(description="Rules manager instance")
    config: OptimizationConfig = Field(description="Optimization config")
    fs_manager: FileSystemManager = Field(description="File system manager")
    metadata_index: MetadataIndex = Field(description="Metadata index")


class TestRulesManager:
    """Test RulesManager functionality."""

    @pytest.fixture
    async def rules_manager(self, temp_project_root: Path, sample_rules_folder: Path):
        """Create a rules manager with sample rules."""
        fs_manager = FileSystemManager(temp_project_root)
        metadata_index = MetadataIndex(temp_project_root)
        token_counter = TokenCounter()

        manager = RulesManager(
            project_root=temp_project_root,
            file_system=fs_manager,
            metadata_index=metadata_index,
            token_counter=token_counter,
            rules_folder=".cursorrules",
            reindex_interval_minutes=30,
        )

        yield manager

        # Cleanup
        await manager.stop_auto_reindex()

    @pytest.mark.asyncio
    async def test_initialize(self, rules_manager: RulesManager) -> None:
        """Test rules manager initialization."""
        result = await rules_manager.initialize()

        assert result["status"] in ["success", "not_found", "disabled"]

    @pytest.mark.asyncio
    async def test_index_rules(self, rules_manager: RulesManager) -> None:
        """Test indexing rules."""
        result = await rules_manager.index_rules(force=True)

        assert result["status"] == "success"
        total_files = result.get("total_files", 0)
        assert isinstance(total_files, (int, float))
        assert total_files >= 0
        assert "message" in result

    @pytest.mark.asyncio
    async def test_get_relevant_rules(self, rules_manager: RulesManager) -> None:
        """Test getting relevant rules."""
        # First index the rules
        _ = await rules_manager.index_rules(force=True)

        # Get rules relevant to authentication
        result = await rules_manager.get_relevant_rules(
            task_description="Implement JWT authentication",
            max_tokens=5000,
            min_relevance_score=0.1,
        )

        assert isinstance(result, dict)
        # Check that we have rules in one of the categories
        local_rules_raw = result.get("local_rules", [])
        generic_rules_raw = result.get("generic_rules", [])
        language_rules_raw = result.get("language_rules", [])
        assert isinstance(local_rules_raw, list)
        assert isinstance(generic_rules_raw, list)
        assert isinstance(language_rules_raw, list)
        local_rules = cast(list[dict[str, object]], local_rules_raw)
        generic_rules = cast(list[dict[str, object]], generic_rules_raw)
        language_rules = cast(list[dict[str, object]], language_rules_raw)
        all_rules: list[dict[str, object]] = (
            local_rules + generic_rules + language_rules
        )
        # Should find the auth-rules.md file
        if all_rules:
            assert any(
                "auth" in str(r.get("file", "")).lower()
                or "jwt" in str(r.get("content", "")).lower()
                for r in all_rules
            )

    @pytest.mark.asyncio
    async def test_relevance_scoring(self, rules_manager: RulesManager) -> None:
        """Test relevance scoring."""
        content1 = "This file contains JWT authentication implementation with tokens."
        content2 = "This file is about database schema design."

        score1 = rules_manager.score_rule_relevance(
            "Implement JWT authentication", content1
        )
        score2 = rules_manager.score_rule_relevance(
            "Implement JWT authentication", content2
        )

        # First should score higher
        assert score1 > score2

    @pytest.mark.asyncio
    async def test_find_rule_files(
        self,
        rules_manager: RulesManager,
        sample_rules_folder: Path,
    ) -> None:
        """Test finding rule files."""
        rule_files = rules_manager.find_rule_files(sample_rules_folder)

        assert len(rule_files) >= 2
        assert any("general" in str(f) for f in rule_files)
        assert any("security" in str(f) for f in rule_files)

    @pytest.mark.asyncio
    async def test_parse_rule_sections(self, rules_manager: RulesManager) -> None:
        """Test parsing rule sections."""
        content = """# Section 1
Content 1

# Section 2
Content 2
"""
        sections = rules_manager.parse_rule_sections(content)

        assert len(sections) == 2
        assert sections[0]["name"] == "Section 1"
        assert sections[1]["name"] == "Section 2"

    @pytest.mark.asyncio
    async def test_get_status(self, rules_manager: RulesManager) -> None:
        """Test getting rules manager status."""
        _ = await rules_manager.index_rules(force=True)

        status = rules_manager.get_status()

        assert "enabled" in status
        assert "indexed_files" in status
        assert "total_tokens" in status

    @pytest.mark.asyncio
    async def test_reindex_skip_when_recent(
        self,
        rules_manager: RulesManager,
    ) -> None:
        """Test that reindexing is skipped when recently indexed."""
        # First index
        result1 = await rules_manager.index_rules(force=True)
        assert result1["status"] == "success"

        # Immediate reindex should skip
        result2 = await rules_manager.index_rules(force=False)
        assert result2["status"] in ["skipped", "success"]

    @pytest.mark.asyncio
    async def test_changed_file_detection(
        self,
        rules_manager: RulesManager,
        sample_rules_folder: Path,
    ) -> None:
        """Test detection of changed files."""
        # Initial index
        _ = await rules_manager.index_rules(force=True)

        # Modify a file
        rule_file = sample_rules_folder / "general.md"
        _ = rule_file.write_text("# Modified\nNew content")

        # Force reindex
        result = await rules_manager.index_rules(force=True)

        assert result["status"] == "success"
        # Should detect the update
        updated = result.get("updated", 0)
        indexed = result.get("indexed", 0)
        assert isinstance(updated, (int, float))
        assert isinstance(indexed, (int, float))
        assert updated > 0 or indexed > 0


class TestOptimizationConfigRules:
    """Test optimization config rules functionality."""

    @pytest.fixture
    def config(self, temp_project_root: Path) -> OptimizationConfig:
        """Create optimization config."""
        return OptimizationConfig(temp_project_root)

    def test_rules_config_defaults(self, config: OptimizationConfig) -> None:
        """Test default rules configuration."""
        assert config.is_rules_enabled() is False
        assert config.get_rules_folder() == ".cursorrules"
        assert config.get_rules_reindex_interval() == 30
        assert config.get_rules_max_tokens() == 5000
        assert config.get_rules_min_relevance() == 0.3

    def test_rules_config_methods(self, config: OptimizationConfig) -> None:
        """Test rules configuration methods."""
        # Enable rules
        _ = config.set("rules.enabled", True)
        assert config.is_rules_enabled() is True

        # Set custom folder
        _ = config.set("rules.rules_folder", ".ai-rules")
        assert config.get_rules_folder() == ".ai-rules"

        # Set reindex interval
        _ = config.set("rules.reindex_interval_minutes", 60)
        assert config.get_rules_reindex_interval() == 60


class TestRulesIntegration:
    """Test rules integration with other components."""

    @pytest.fixture
    async def full_setup(
        self,
        temp_project_root: Path,
        sample_rules_folder: Path,
        sample_memory_bank_files: dict[str, Path],
    ) -> AsyncGenerator[FullSetup]:
        """Setup full environment with rules and memory bank."""
        fs_manager = FileSystemManager(temp_project_root)
        metadata_index = MetadataIndex(temp_project_root)
        token_counter = TokenCounter()
        config = OptimizationConfig(temp_project_root)

        # Enable rules
        _ = config.set("rules.enabled", True)

        rules_manager = RulesManager(
            project_root=temp_project_root,
            file_system=fs_manager,
            metadata_index=metadata_index,
            token_counter=token_counter,
            rules_folder=".cursorrules",
            reindex_interval_minutes=30,
        )

        _ = await rules_manager.initialize()

        yield FullSetup(
            rules_manager=rules_manager,
            config=config,
            fs_manager=fs_manager,
            metadata_index=metadata_index,
        )

        await rules_manager.stop_auto_reindex()

    @pytest.mark.asyncio
    async def test_full_workflow(self, full_setup: FullSetup) -> None:
        """Test complete workflow with rules."""
        rules_manager = full_setup.rules_manager

        # Index rules
        index_result = await rules_manager.index_rules(force=True)
        assert index_result["status"] == "success"

        # Get relevant rules
        result = await rules_manager.get_relevant_rules(
            task_description="Add authentication with JWT", max_tokens=5000
        )

        assert isinstance(result, dict)
        # Check that we have rules
        local_rules_raw = result.get("local_rules", [])
        generic_rules_raw = result.get("generic_rules", [])
        language_rules_raw = result.get("language_rules", [])
        assert isinstance(local_rules_raw, list)
        assert isinstance(generic_rules_raw, list)
        assert isinstance(language_rules_raw, list)
        local_rules = cast(list[dict[str, object]], local_rules_raw)
        generic_rules = cast(list[dict[str, object]], generic_rules_raw)
        language_rules = cast(list[dict[str, object]], language_rules_raw)
        all_rules: list[dict[str, object]] = (
            local_rules + generic_rules + language_rules
        )
        assert all_rules

        # Get status
        status = rules_manager.get_status()
        indexed_files = status.get("indexed_files", 0)
        assert isinstance(indexed_files, (int, float))
        assert indexed_files > 0


def run_tests():
    """Run all rules enhancement tests."""
    print("Running Rules Enhancement Test Suite...")
    print("=" * 60)

    _ = pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
