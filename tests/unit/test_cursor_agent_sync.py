"""
Tests for sync_cursor_agents() in src/cortex/tools/synapse/prompts.py.

Verifies:
- Agents are copied from source to target on first run
- Files are not rewritten when content is unchanged (idempotent)
- Files are updated when content changes
- Missing source directory is handled gracefully
- Target directory is created if absent
"""

from pathlib import Path

import pytest

from cortex.tools.synapse.prompts import sync_cursor_agents


class TestSyncCursorAgents:
    """Tests for sync_cursor_agents() via public interface."""

    def _make_source(self, tmp_path: Path) -> Path:
        """Create a .cortex/synapse/cursor-agents/ source directory."""
        source = tmp_path / ".cortex" / "synapse" / "cursor-agents"
        source.mkdir(parents=True)
        return source

    def _expected_target(self, source: Path) -> Path:
        """Resolve .cursor/agents/ target from source."""
        # source is <root>/.cortex/synapse/cursor-agents → target is <root>/.cursor/agents
        return source.parent.parent.parent / ".cursor" / "agents"

    def test_syncs_all_agent_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All .md files in source are written to target."""
        # Arrange
        source = self._make_source(tmp_path)
        _ = (source / "agent-a.md").write_text("agent A", encoding="utf-8")
        _ = (source / "agent-b.md").write_text("agent B", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts._get_cursor_agents_source", lambda: source
        )
        target = self._expected_target(source)

        # Act
        sync_cursor_agents()

        # Assert
        assert (target / "agent-a.md").read_text() == "agent A"
        assert (target / "agent-b.md").read_text() == "agent B"

    def test_creates_target_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Target directory is created when absent."""
        # Arrange
        source = self._make_source(tmp_path)
        _ = (source / "agent.md").write_text("content", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts._get_cursor_agents_source", lambda: source
        )
        target = self._expected_target(source)
        assert not target.exists()

        # Act
        sync_cursor_agents()

        # Assert
        assert target.is_dir()

    def test_no_source_no_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing source directory is handled gracefully (no exception)."""
        # Arrange
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts._get_cursor_agents_source", lambda: None
        )

        # Act / Assert: no exception raised
        sync_cursor_agents()

    def test_idempotent_unchanged_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Second sync with unchanged content does not rewrite the file."""
        # Arrange
        source = self._make_source(tmp_path)
        _ = (source / "agent.md").write_text("content", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts._get_cursor_agents_source", lambda: source
        )

        sync_cursor_agents()
        target = self._expected_target(source)
        mtime_before = (target / "agent.md").stat().st_mtime

        # Act: second sync, same content
        sync_cursor_agents()
        mtime_after = (target / "agent.md").stat().st_mtime

        # Assert: file was not rewritten
        assert mtime_before == mtime_after

    def test_updates_changed_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """File is overwritten when source content changes."""
        # Arrange
        source = self._make_source(tmp_path)
        agent = source / "agent.md"
        _ = agent.write_text("old content", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts._get_cursor_agents_source", lambda: source
        )

        sync_cursor_agents()
        target = self._expected_target(source)

        # Act: update source and re-sync
        _ = agent.write_text("new content", encoding="utf-8")
        sync_cursor_agents()

        # Assert
        assert (target / "agent.md").read_text() == "new content"

    def test_non_md_files_not_synced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only .md files are synced; other files are ignored."""
        # Arrange
        source = self._make_source(tmp_path)
        _ = (source / "agent.md").write_text("content", encoding="utf-8")
        _ = (source / "README.txt").write_text("readme", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts._get_cursor_agents_source", lambda: source
        )
        target = self._expected_target(source)

        # Act
        sync_cursor_agents()

        # Assert
        assert (target / "agent.md").exists()
        assert not (target / "README.txt").exists()
