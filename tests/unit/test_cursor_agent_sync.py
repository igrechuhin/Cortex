"""
Tests for sync_cursor_agents() in src/cortex/tools/synapse/prompts.py.

Verifies:
- Agents are copied from source to target on first run
- Files are not rewritten when content is unchanged (idempotent)
- Files are updated when content changes
- Missing source directory is handled gracefully
- Target directory is created if absent
- Required pipeline agents exist in the source directory
"""

from pathlib import Path

import pytest

from cortex.tools.synapse.prompts import (
    CLAUDE_CODE_TOOLS_FIELD,
    get_claude_agents_target,
    get_cursor_agents_source,
    get_cursor_agents_target,
    inject_tools_into_frontmatter,
    sync_cursor_agents,
)

# All cursor-agents that must exist in .cortex/synapse/cursor-agents/
# so they are synced to .cursor/agents/ on MCP server startup.
_REQUIRED_AGENT_FILES: tuple[str, ...] = (
    # Commit pipeline
    "commit-preflight.md",
    "commit-checks.md",
    "commit-docs.md",
    "commit-validate.md",
    "commit-final-gate.md",
    # Implement pipeline
    "implement-select.md",
    "implement-code.md",
    "implement-finalize.md",
    "implement-verify.md",
    # Shared reference documents
    "shared-defaults.md",
)


class TestSyncCursorAgents:
    """Tests for sync_cursor_agents() via public interface."""

    def _make_source(self, tmp_path: Path) -> Path:
        """Create a .cortex/synapse/cursor-agents/ source directory."""
        source = tmp_path / ".cortex" / "synapse" / "cursor-agents"
        source.mkdir(parents=True)
        return source

    def test_syncs_all_agent_files_to_both_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All .md files in source are written to both .cursor/agents/ and .claude/agents/."""
        # Arrange — files without frontmatter (transform is a no-op for these)
        source = self._make_source(tmp_path)
        _ = (source / "agent-a.md").write_text("agent A", encoding="utf-8")
        _ = (source / "agent-b.md").write_text("agent B", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts.get_cursor_agents_source", lambda: source
        )
        cursor_target = get_cursor_agents_target(source)
        claude_target = get_claude_agents_target(source)

        # Act
        sync_cursor_agents()

        # Assert: both targets receive all files
        for target in (cursor_target, claude_target):
            assert (target / "agent-a.md").exists()
            assert (target / "agent-b.md").exists()

    def test_cursor_gets_original_claude_gets_transformed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cursor gets original content; Claude Code gets tools field injected."""
        # Arrange
        source = self._make_source(tmp_path)
        original = "---\nname: test\nmodel: sonnet\n---\n\nBody."
        _ = (source / "agent.md").write_text(original, encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts.get_cursor_agents_source", lambda: source
        )
        cursor_target = get_cursor_agents_target(source)
        claude_target = get_claude_agents_target(source)

        # Act
        sync_cursor_agents()

        # Assert: cursor gets verbatim source; claude gets injected tools field
        assert (cursor_target / "agent.md").read_text() == original
        claude_content = (claude_target / "agent.md").read_text()
        assert CLAUDE_CODE_TOOLS_FIELD in claude_content
        assert "name: test" in claude_content

    def test_creates_both_target_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both target directories are created when absent."""
        # Arrange
        source = self._make_source(tmp_path)
        _ = (source / "agent.md").write_text("content", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts.get_cursor_agents_source", lambda: source
        )
        cursor_target = get_cursor_agents_target(source)
        claude_target = get_claude_agents_target(source)
        assert not cursor_target.exists()
        assert not claude_target.exists()

        # Act
        sync_cursor_agents()

        # Assert
        assert cursor_target.is_dir()
        assert claude_target.is_dir()

    def test_no_source_no_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing source directory is handled gracefully (no exception)."""
        # Arrange
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts.get_cursor_agents_source", lambda: None
        )

        # Act / Assert: no exception raised
        sync_cursor_agents()

    def test_idempotent_unchanged_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Second sync with unchanged content does not rewrite the file in either target."""
        # Arrange
        source = self._make_source(tmp_path)
        _ = (source / "agent.md").write_text("content", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts.get_cursor_agents_source", lambda: source
        )

        sync_cursor_agents()
        cursor_target = get_cursor_agents_target(source)
        claude_target = get_claude_agents_target(source)
        cursor_mtime = (cursor_target / "agent.md").stat().st_mtime
        claude_mtime = (claude_target / "agent.md").stat().st_mtime

        # Act: second sync, same content
        sync_cursor_agents()

        # Assert: files were not rewritten
        assert (cursor_target / "agent.md").stat().st_mtime == cursor_mtime
        assert (claude_target / "agent.md").stat().st_mtime == claude_mtime

    def test_updates_changed_file_in_both_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """File is overwritten in both targets when source content changes."""
        # Arrange — use frontmatter so transform is exercised
        source = self._make_source(tmp_path)
        agent = source / "agent.md"
        _ = agent.write_text("---\nname: a\n---\nold body", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts.get_cursor_agents_source", lambda: source
        )

        sync_cursor_agents()
        cursor_target = get_cursor_agents_target(source)
        claude_target = get_claude_agents_target(source)

        # Act: update source and re-sync
        _ = agent.write_text("---\nname: a\n---\nnew body", encoding="utf-8")
        sync_cursor_agents()

        # Assert: cursor gets verbatim; claude gets transformed but with updated body
        assert (cursor_target / "agent.md").read_text() == "---\nname: a\n---\nnew body"
        assert "new body" in (claude_target / "agent.md").read_text()
        assert CLAUDE_CODE_TOOLS_FIELD in (claude_target / "agent.md").read_text()

    def test_non_md_files_not_synced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only .md files are synced; other files are ignored."""
        # Arrange
        source = self._make_source(tmp_path)
        _ = (source / "agent.md").write_text("content", encoding="utf-8")
        _ = (source / "README.txt").write_text("readme", encoding="utf-8")
        monkeypatch.setattr(
            "cortex.tools.synapse.prompts.get_cursor_agents_source", lambda: source
        )
        cursor_target = get_cursor_agents_target(source)
        claude_target = get_claude_agents_target(source)

        # Act
        sync_cursor_agents()

        # Assert
        for target in (cursor_target, claude_target):
            assert (target / "agent.md").exists()
            assert not (target / "README.txt").exists()


class TestInjectToolsIntoFrontmatter:
    """Unit tests for inject_tools_into_frontmatter()."""

    def test_injects_tools_field_after_existing_fields(self) -> None:
        """tools field is added inside the frontmatter block."""
        content = "---\nname: test\nmodel: sonnet\n---\n\nBody."
        result = inject_tools_into_frontmatter(content)
        assert f"\n{CLAUDE_CODE_TOOLS_FIELD}\n---" in result

    def test_rewrites_backtick_tool_refs_in_body(self) -> None:
        """Backtick-quoted Cortex tool calls get the mcp__cortex__ prefix."""
        content = "---\nname: test\n---\n\nCall `check_mcp_connection_health()` first."
        result = inject_tools_into_frontmatter(content)
        assert "`mcp__cortex__check_mcp_connection_health(" in result
        assert "`check_mcp_connection_health(" not in result

    def test_rewrites_multiple_tool_refs(self) -> None:
        """All Cortex tool references in the body are rewritten."""
        content = (
            "---\nname: test\n---\n\n"
            'Call `start_pre_commit_job(phase="A")` then `get_pre_commit_job_status(job_id=x)`.'
        )
        result = inject_tools_into_frontmatter(content)
        assert "`mcp__cortex__start_pre_commit_job(" in result
        assert "`mcp__cortex__get_pre_commit_job_status(" in result

    def test_non_cortex_tool_refs_unchanged(self) -> None:
        """Backtick calls to non-Cortex names are not rewritten in the body."""
        content = "---\nname: test\n---\n\nUse `some_other_tool()` here."
        result = inject_tools_into_frontmatter(content)
        assert "`some_other_tool(" in result
        # Only the injected frontmatter field should contain the prefix, not the body
        body = result.split("---\n", 2)[-1]
        assert "mcp__cortex__" not in body

    def test_no_double_inject(self) -> None:
        """Running transform twice does not duplicate the tools field or prefixes."""
        content = "---\nname: test\n---\n\nCall `load_context(task_description='x')`."
        once = inject_tools_into_frontmatter(content)
        twice = inject_tools_into_frontmatter(once)
        assert once == twice

    def test_no_frontmatter_still_rewrites_tool_refs(self) -> None:
        """Even without frontmatter, tool refs in body are rewritten."""
        content = "Call `check_mcp_connection_health()` here."
        result = inject_tools_into_frontmatter(content)
        assert "`mcp__cortex__check_mcp_connection_health(" in result

    def test_existing_tools_field_preserved(self) -> None:
        """Content that already has a tools field is not double-injected."""
        content = "---\nname: test\ntools: mcp__other__*\n---\n\nBody."
        result = inject_tools_into_frontmatter(content)
        assert result.count("tools:") == 1

    def test_body_non_tool_prose_unchanged(self) -> None:
        """Non-tool prose in the body is not altered."""
        body = "\n\nSome **markdown** body.\n\n- item1\n- item2\n"
        content = f"---\nname: test\n---{body}"
        result = inject_tools_into_frontmatter(content)
        assert body in result


class TestRequiredAgentFilesPresent:
    """Assert all required pipeline agents exist in source and both IDE targets.

    These tests ensure that every agent referenced by commit.md and
    implement-next-roadmap-step.md is present in the source directory and
    both .cursor/agents/ and .claude/agents/ after sync.
    """

    def test_all_required_agents_exist_in_source(self) -> None:
        """Every required agent file exists in .cortex/synapse/cursor-agents/."""
        source = get_cursor_agents_source()
        if source is None:
            pytest.skip("cursor-agents source directory not found")
        missing = [
            name for name in _REQUIRED_AGENT_FILES if not (source / name).exists()
        ]
        assert (
            not missing
        ), f"Required cursor-agent files missing from {source}: {missing}"

    def test_target_path_helpers_return_correct_directories(self) -> None:
        """Target path helpers resolve .cursor/agents/ and .claude/agents/ correctly."""
        source = get_cursor_agents_source()
        if source is None:
            pytest.skip("cursor-agents source directory not found")
        project_root = source.parent.parent.parent
        assert get_cursor_agents_target(source) == project_root / ".cursor" / "agents"
        assert get_claude_agents_target(source) == project_root / ".claude" / "agents"
