"""
Tests for rules_indexer module.

This module tests rule file indexing functionality including:
- File scanning and discovery
- Content parsing and section extraction
- Change detection and incremental updates
- Automatic reindexing
"""

from datetime import timedelta
from pathlib import Path

import pytest

from cortex.core.token_counter import TokenCounter
from cortex.optimization.rules_indexer import RulesIndexer


class TestRulesIndexerInitialization:
    """Tests for RulesIndexer initialization."""

    def test_initialization_with_default_interval(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test initialization with default reindex interval."""
        # Arrange & Act
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Assert
        assert indexer.project_root == tmp_path
        assert indexer.token_counter == mock_token_counter
        assert indexer.reindex_interval == timedelta(minutes=30)
        assert indexer.rules_index == {}
        assert indexer.last_index_time is None
        assert indexer.rules_content_hashes == {}

    def test_initialization_with_custom_interval(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test initialization with custom reindex interval."""
        # Arrange & Act
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
            reindex_interval_minutes=60,
        )

        # Assert
        assert indexer.reindex_interval == timedelta(minutes=60)


class TestIndexRules:
    """Tests for index_rules method."""

    @pytest.mark.asyncio
    async def test_index_rules_with_nonexistent_folder(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test indexing when rules folder doesn't exist."""
        # Arrange
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        result = await indexer.index_rules(".cursorrules")

        # Assert
        assert result["status"] == "error"
        error_msg = result.get("error")
        assert isinstance(error_msg, str)
        assert "not found" in error_msg

    @pytest.mark.asyncio
    async def test_index_rules_with_empty_folder(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test indexing an empty rules folder."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        rules_dir.mkdir()

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        result = await indexer.index_rules(".cursorrules")

        # Assert
        assert result["status"] == "success"
        assert result["total_files"] == 0
        assert result["indexed"] == 0

    @pytest.mark.asyncio
    async def test_index_rules_with_valid_files(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test indexing valid rule files."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule1.md").write_text("# Rule 1\nContent for rule 1")
        _ = (rules_dir / "rule2.txt").write_text("# Rule 2\nContent for rule 2")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        result = await indexer.index_rules(".cursorrules")

        # Assert
        assert result["status"] == "success"
        assert result["total_files"] == 2
        assert result["indexed"] == 2
        assert result["updated"] == 0
        assert result["unchanged"] == 0

    @pytest.mark.asyncio
    async def test_index_rules_skips_when_recently_indexed(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test that indexing is skipped when recently indexed."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
            reindex_interval_minutes=60,
        )

        # Act
        result1 = await indexer.index_rules(".cursorrules")
        result2 = await indexer.index_rules(".cursorrules", force=False)

        # Assert
        assert result1["status"] == "success"
        assert result2["status"] == "skipped"
        message = result2.get("message")
        assert isinstance(message, str)
        assert "Recently indexed" in message

    @pytest.mark.asyncio
    async def test_index_rules_with_force_flag(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test that force flag bypasses skip logic."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
            reindex_interval_minutes=60,
        )

        # Act
        result1 = await indexer.index_rules(".cursorrules")
        result2 = await indexer.index_rules(".cursorrules", force=True)

        # Assert
        assert result1["status"] == "success"
        assert result2["status"] == "success"

    @pytest.mark.asyncio
    async def test_index_rules_detects_changed_files(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test that changed files are detected."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        rule_file = rules_dir / "rule.md"
        _ = rule_file.write_text("# Rule\nOriginal content")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
            reindex_interval_minutes=0,  # Allow immediate reindex
        )

        # First index
        _ = await indexer.index_rules(".cursorrules")

        # Modify file
        _ = rule_file.write_text("# Rule\nModified content")

        # Act
        result = await indexer.index_rules(".cursorrules", force=True)

        # Assert
        assert result["status"] == "success"
        assert result["updated"] == 1
        assert result["unchanged"] == 0

    @pytest.mark.asyncio
    async def test_index_rules_detects_unchanged_files(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test that unchanged files are detected."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule\nContent")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
            reindex_interval_minutes=0,
        )

        # First index
        _ = await indexer.index_rules(".cursorrules")

        # Act - reindex without changes
        result = await indexer.index_rules(".cursorrules", force=True)

        # Assert
        assert result["status"] == "success"
        assert result["updated"] == 0
        assert result["unchanged"] == 1

    @pytest.mark.asyncio
    async def test_index_rules_stores_metadata(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test that rule metadata is correctly stored."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule\nContent")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        _ = await indexer.index_rules(".cursorrules")

        # Assert
        rule_index = indexer.get_index()
        assert len(rule_index) == 1

        rule_key = list(rule_index.keys())[0]
        rule_data = rule_index[rule_key]

        assert "content" in rule_data
        assert "token_count" in rule_data
        assert "sections" in rule_data
        assert "indexed_at" in rule_data
        assert "file_size" in rule_data


class TestFindRuleFiles:
    """Tests for find_rule_files method."""

    def test_find_rule_files_in_empty_directory(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test finding rule files in empty directory."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        files = indexer.find_rule_files(rules_dir)

        # Assert
        assert files == []

    def test_find_rule_files_with_markdown_files(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test finding markdown rule files."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule1.md").write_text("# Rule 1")
        _ = (rules_dir / "rule2.md").write_text("# Rule 2")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        files = indexer.find_rule_files(rules_dir)

        # Assert
        assert len(files) == 2
        assert all(f.suffix == ".md" for f in files)

    def test_find_rule_files_with_text_files(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test finding text rule files."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.txt").write_text("Rule content")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        files = indexer.find_rule_files(rules_dir)

        # Assert
        assert len(files) == 1
        assert files[0].suffix == ".txt"

    def test_find_rule_files_in_subdirectories(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test finding rule files in subdirectories."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        subdir = rules_dir / "python"
        _ = subdir.mkdir()
        _ = (subdir / "python_rules.md").write_text("# Python Rules")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        files = indexer.find_rule_files(rules_dir)

        # Assert
        assert len(files) == 1
        assert "python_rules.md" in str(files[0])

    def test_find_rule_files_removes_duplicates(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test that duplicate files are removed."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / ".cursorrules").write_text("Cursor rules")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        files = indexer.find_rule_files(rules_dir)

        # Assert
        # File matches multiple patterns but should only appear once
        assert len(files) == len(set(files))


class TestParseRuleSections:
    """Tests for parse_rule_sections method."""

    def test_parse_rule_sections_with_no_sections(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test parsing content with no sections."""
        # Arrange
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )
        content = "Just plain text without any sections"

        # Act
        sections = indexer.parse_rule_sections(content)

        # Assert
        assert sections == []

    def test_parse_rule_sections_with_single_section(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test parsing content with a single section."""
        # Arrange
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )
        content = """# Rule Name
This is the content of the rule.
Multiple lines of content.
"""

        # Act
        sections = indexer.parse_rule_sections(content)

        # Assert
        assert len(sections) == 1
        section = sections[0]
        assert section.name == "Rule Name"
        assert "This is the content" in section.content
        assert section.line_count > 0

    def test_parse_rule_sections_with_multiple_sections(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test parsing content with multiple sections."""
        # Arrange
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )
        content = """# Section 1
Content for section 1.

## Section 2
Content for section 2.

### Section 3
Content for section 3.
"""

        # Act
        sections = indexer.parse_rule_sections(content)

        # Assert
        assert len(sections) == 3
        assert sections[0].name == "Section 1"
        assert sections[1].name == "Section 2"
        assert sections[2].name == "Section 3"

    def test_parse_rule_sections_with_varying_heading_levels(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test parsing with different heading levels."""
        # Arrange
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )
        content = """# H1 Heading
Content 1

#### H4 Heading
Content 2
"""

        # Act
        sections = indexer.parse_rule_sections(content)

        # Assert
        assert len(sections) == 2
        assert sections[0].name == "H1 Heading"
        assert sections[1].name == "H4 Heading"


class TestAutoReindex:
    """Tests for automatic reindexing functionality."""

    @pytest.mark.asyncio
    async def test_start_auto_reindex(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test starting automatic reindexing."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
            reindex_interval_minutes=1,
        )
        _ = await indexer.index_rules(".cursorrules")

        # Act
        await indexer.start_auto_reindex(".cursorrules")

        # Assert
        assert indexer.reindex_task is not None
        assert not indexer.reindex_task.done()

        # Cleanup
        await indexer.stop_auto_reindex()

    @pytest.mark.asyncio
    async def test_start_auto_reindex_idempotent(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test that starting auto-reindex multiple times doesn't create multiple tasks."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )
        _ = await indexer.index_rules(".cursorrules")

        # Act
        await indexer.start_auto_reindex(".cursorrules")
        task1 = indexer.reindex_task
        await indexer.start_auto_reindex(".cursorrules")
        task2 = indexer.reindex_task

        # Assert
        assert task1 is task2  # Same task

        # Cleanup
        await indexer.stop_auto_reindex()

    @pytest.mark.asyncio
    async def test_stop_auto_reindex(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test stopping automatic reindexing."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )
        _ = await indexer.index_rules(".cursorrules")
        await indexer.start_auto_reindex(".cursorrules")

        # Act
        await indexer.stop_auto_reindex()

        # Assert
        assert indexer.reindex_task is not None
        assert indexer.reindex_task.done() or indexer.reindex_task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_auto_reindex_when_not_running(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test stopping auto-reindex when it's not running."""
        # Arrange
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act & Assert - Should not raise exception
        await indexer.stop_auto_reindex()


class TestGetIndex:
    """Tests for get_index method."""

    @pytest.mark.asyncio
    async def test_get_index_returns_empty_when_not_indexed(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test get_index returns empty dict when nothing is indexed."""
        # Arrange
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        index = indexer.get_index()

        # Assert
        assert index == {}

    @pytest.mark.asyncio
    async def test_get_index_returns_indexed_rules(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test get_index returns indexed rules."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )
        _ = await indexer.index_rules(".cursorrules")

        # Act
        index = indexer.get_index()

        # Assert
        assert len(index) == 1
        assert all(hasattr(v, "model_dump") for v in index.values())


class TestGetStatus:
    """Tests for get_status method."""

    def test_get_status_before_indexing(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test get_status before any indexing."""
        # Arrange
        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )

        # Act
        status = indexer.get_status()

        # Assert
        assert status["indexed_files"] == 0
        assert status["last_indexed"] is None
        assert status["auto_reindex_enabled"] is False
        assert status["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_get_status_after_indexing(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test get_status after indexing."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule\nContent")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
            reindex_interval_minutes=45,
        )
        _ = await indexer.index_rules(".cursorrules")

        # Act
        status = indexer.get_status()

        # Assert
        assert status["indexed_files"] == 1
        assert status["last_indexed"] is not None
        assert status["reindex_interval_minutes"] == 45
        total_tokens = status.get("total_tokens")
        assert isinstance(total_tokens, (int, float))
        assert total_tokens > 0

    @pytest.mark.asyncio
    async def test_get_status_with_auto_reindex_enabled(
        self, tmp_path: Path, mock_token_counter: TokenCounter
    ):
        """Test get_status with auto-reindex enabled."""
        # Arrange
        rules_dir = tmp_path / ".cursorrules"
        _ = rules_dir.mkdir()
        _ = (rules_dir / "rule.md").write_text("# Rule")

        indexer = RulesIndexer(
            project_root=tmp_path,
            token_counter=mock_token_counter,
        )
        _ = await indexer.index_rules(".cursorrules")
        await indexer.start_auto_reindex(".cursorrules")

        # Act
        status = indexer.get_status()

        # Assert
        assert status["auto_reindex_enabled"] is True

        # Cleanup
        await indexer.stop_auto_reindex()
