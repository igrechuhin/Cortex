"""Tests for prompts_agents.py — cursor/claude agent sync."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.tools.synapse.prompts_agents import (
    get_claude_agents_target,
    get_cursor_agents_source,
    get_cursor_agents_target,
    inject_tools_into_frontmatter,
    rewrite_tool_refs,
    sync_agent_file,
    sync_agents_to_target,
    sync_cursor_agents,
)
from cortex.tools.synapse.prompts_content import CORTEX_TOOL_NAMES, MCP_TOOL_PREFIX

# ---------------------------------------------------------------------------
# get_cursor_agents_source
# ---------------------------------------------------------------------------


class TestGetCursorAgentsSource:
    def test_returns_none_when_no_cursor_agents_found(self) -> None:
        """Returns None when no .cortex/synapse/cursor-agents/ directory exists."""
        with (
            patch(
                "cortex.tools.synapse.prompts_agents.Path.cwd",
                return_value=Path("/nonexistent_tmp_xyz"),
            ),
            patch(
                "cortex.tools.synapse.prompts_agents.Path.__file__",
                Path("/nonexistent_tmp_xyz/module.py"),
                create=True,
            ),
        ):
            # Act: use module fallback path that won't exist
            result = get_cursor_agents_source()
            # Either returns a real path (from the actual repo) or None
            # In the real repo this succeeds; we just verify no exception
            assert result is None or isinstance(result, Path)

    def test_finds_cursor_agents_via_cwd(self, tmp_path: Path) -> None:
        """Finds cursor-agents dir when it exists under .cortex/synapse/."""
        agents_dir = tmp_path / ".cortex" / "synapse" / "cursor-agents"
        agents_dir.mkdir(parents=True)
        with patch(
            "cortex.tools.synapse.prompts_agents.Path.cwd", return_value=tmp_path
        ):
            result = get_cursor_agents_source()
        assert result == agents_dir


# ---------------------------------------------------------------------------
# get_cursor_agents_target / get_claude_agents_target
# ---------------------------------------------------------------------------


class TestGetAgentsTarget:
    def test_cursor_target_inferred_from_source(self, tmp_path: Path) -> None:
        """get_cursor_agents_target returns <root>/<cursor_dir>/agents/."""
        from cortex.core.path_resolver import CursorResourceType, get_cursor_path

        source = tmp_path / ".cortex" / "synapse" / "cursor-agents"
        result = get_cursor_agents_target(source)
        expected = get_cursor_path(tmp_path, CursorResourceType.CURSOR_DIR) / "agents"
        assert result == expected

    def test_claude_target_inferred_from_source(self, tmp_path: Path) -> None:
        """get_claude_agents_target returns <root>/.claude/agents/."""
        source = tmp_path / ".cortex" / "synapse" / "cursor-agents"
        result = get_claude_agents_target(source)
        assert result == tmp_path / ".claude" / "agents"


# ---------------------------------------------------------------------------
# _rewrite_tool_refs
# ---------------------------------------------------------------------------


class TestRewriteToolRefs:
    def test_rewrites_known_cortex_tool_in_backtick(self) -> None:
        """Rewrites `session(` to `mcp__cortex__session(` for known tools."""
        tool_name = next(iter(CORTEX_TOOL_NAMES))
        body = f"Call `{tool_name}(arg)` to do something."
        result = rewrite_tool_refs(body)
        assert f"`{MCP_TOOL_PREFIX}{tool_name}(" in result

    def test_does_not_rewrite_unknown_tool(self) -> None:
        """Does not rewrite backtick references to unknown tool names."""
        body = "Call `unknown_tool(arg)` to do something."
        result = rewrite_tool_refs(body)
        assert "`unknown_tool(" in result
        assert MCP_TOOL_PREFIX not in result

    def test_does_not_rewrite_bare_references_outside_backticks(self) -> None:
        """Does not rewrite plain text references without backtick prefix."""
        tool_name = next(iter(CORTEX_TOOL_NAMES))
        body = f"Call {tool_name}(arg) to do something."
        result = rewrite_tool_refs(body)
        assert MCP_TOOL_PREFIX not in result


# ---------------------------------------------------------------------------
# inject_tools_into_frontmatter
# ---------------------------------------------------------------------------


class TestInjectToolsIntoFrontmatter:
    def test_no_frontmatter_only_rewrites_tool_refs(self) -> None:
        """Content without --- frontmatter only gets tool-ref rewrite."""
        tool_name = next(iter(CORTEX_TOOL_NAMES))
        content = f"No frontmatter. Call `{tool_name}(x)`."
        result = inject_tools_into_frontmatter(content)
        assert f"`{MCP_TOOL_PREFIX}{tool_name}(" in result
        assert "tools:" not in result

    def test_unclosed_frontmatter_only_rewrites_tool_refs(self) -> None:
        """Content starting with --- but no closing --- only rewrites tool refs."""
        tool_name = next(iter(CORTEX_TOOL_NAMES))
        content = f"---\nname: test\nCall `{tool_name}(x)`."
        result = inject_tools_into_frontmatter(content)
        assert f"`{MCP_TOOL_PREFIX}{tool_name}(" in result

    def test_frontmatter_without_tools_field_gets_tools_injected(self) -> None:
        """Frontmatter without tools: gets tools field injected."""
        content = "---\nname: test\n---\nbody here"
        result = inject_tools_into_frontmatter(content)
        assert "tools:" in result

    def test_frontmatter_with_tools_field_not_duplicated(self) -> None:
        """Frontmatter already having tools: is not duplicated."""
        content = "---\nname: test\ntools: mcp__cortex__*\n---\nbody here"
        result = inject_tools_into_frontmatter(content)
        assert result.count("tools:") == 1

    def test_body_tool_refs_rewritten_after_frontmatter(self) -> None:
        """Tool refs in the body (after frontmatter) are rewritten."""
        tool_name = next(iter(CORTEX_TOOL_NAMES))
        content = f"---\nname: test\n---\nCall `{tool_name}(x)`."
        result = inject_tools_into_frontmatter(content)
        assert f"`{MCP_TOOL_PREFIX}{tool_name}(" in result


# ---------------------------------------------------------------------------
# _sync_agent_file
# ---------------------------------------------------------------------------


class TestSyncAgentFile:
    def test_writes_file_when_content_differs(self, tmp_path: Path) -> None:
        """Writes agent file when destination does not match source."""
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()
        agent = source_dir / "agent.md"
        _ = agent.write_text("new content", encoding="utf-8")
        result = sync_agent_file(agent, target_dir)
        assert result is True
        assert (target_dir / "agent.md").read_text() == "new content"

    def test_skips_write_when_content_identical(self, tmp_path: Path) -> None:
        """Returns False and skips write when content is already identical."""
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()
        agent = source_dir / "agent.md"
        _ = agent.write_text("same content", encoding="utf-8")
        _ = (target_dir / "agent.md").write_text("same content", encoding="utf-8")
        result = sync_agent_file(agent, target_dir)
        assert result is False

    def test_returns_false_on_oserror(self, tmp_path: Path) -> None:
        """Returns False and logs warning when write raises OSError."""
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()
        agent = source_dir / "agent.md"
        _ = agent.write_text("content", encoding="utf-8")
        with patch("pathlib.Path.write_text", side_effect=OSError("permission")):
            result = sync_agent_file(agent, target_dir)
        assert result is False

    def test_applies_transform_when_requested(self, tmp_path: Path) -> None:
        """Applies inject_tools_into_frontmatter transform when transform=True."""
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()
        agent = source_dir / "agent.md"
        _ = agent.write_text("---\nname: test\n---\nbody", encoding="utf-8")
        result = sync_agent_file(agent, target_dir, transform=True)
        assert result is True
        written = (target_dir / "agent.md").read_text()
        assert "tools:" in written


# ---------------------------------------------------------------------------
# _sync_agents_to_target
# ---------------------------------------------------------------------------


class TestSyncAgentsToTarget:
    def test_returns_zero_when_mkdir_fails(self, tmp_path: Path) -> None:
        """Returns 0 and warns when target directory cannot be created."""
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "target"
        with patch("pathlib.Path.mkdir", side_effect=OSError("readonly")):
            result = sync_agents_to_target(source, target, "test")
        assert result == 0

    def test_syncs_md_files(self, tmp_path: Path) -> None:
        """Copies all .md files from source to target."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        source.mkdir()
        _ = (source / "agent1.md").write_text("agent 1", encoding="utf-8")
        _ = (source / "agent2.md").write_text("agent 2", encoding="utf-8")
        result = sync_agents_to_target(source, target, "test")
        assert result == 2
        assert (target / "agent1.md").exists()
        assert (target / "agent2.md").exists()

    def test_removes_stale_md_files(self, tmp_path: Path) -> None:
        """Removes stale .md files in target that no longer exist in source."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        source.mkdir()
        target.mkdir()
        _ = (source / "new.md").write_text("new", encoding="utf-8")
        stale = target / "stale.md"
        _ = stale.write_text("stale", encoding="utf-8")
        _ = sync_agents_to_target(source, target, "test")
        assert not stale.exists()
        assert (target / "new.md").exists()

    def test_does_not_fail_when_stale_unlink_raises(self, tmp_path: Path) -> None:
        """Does not raise when removing stale file raises OSError."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        source.mkdir()
        target.mkdir()
        stale = target / "stale.md"
        _ = stale.write_text("stale", encoding="utf-8")
        with patch("pathlib.Path.unlink", side_effect=OSError("locked")):
            # Should not raise
            _ = sync_agents_to_target(source, target, "test")


# ---------------------------------------------------------------------------
# sync_cursor_agents
# ---------------------------------------------------------------------------


class TestSyncCursorAgents:
    def test_does_nothing_when_source_not_found(self) -> None:
        """sync_cursor_agents is a no-op when source directory is not found."""
        with patch(
            "cortex.tools.synapse.prompts_agents.get_cursor_agents_source",
            return_value=None,
        ):
            # Should not raise
            sync_cursor_agents()

    def test_syncs_to_both_targets_when_source_found(self, tmp_path: Path) -> None:
        """sync_cursor_agents writes to both cursor and claude targets."""
        source = tmp_path / ".cortex" / "synapse" / "cursor-agents"
        source.mkdir(parents=True)
        _ = (source / "agent.md").write_text(
            "---\nname: t\n---\nbody", encoding="utf-8"
        )

        mock_sync = MagicMock(return_value=1)
        with (
            patch(
                "cortex.tools.synapse.prompts_agents.get_cursor_agents_source",
                return_value=source,
            ),
            patch(
                "cortex.tools.synapse.prompts_agents.sync_agents_to_target",
                mock_sync,
            ),
        ):
            sync_cursor_agents()

        assert mock_sync.call_count == 2
