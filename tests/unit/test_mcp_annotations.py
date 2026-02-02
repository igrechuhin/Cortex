"""Unit tests for MCP tool annotations helpers.

Tests verify that:
- read_only_annotations, safe_write_annotations, destructive_annotations,
  and external_annotations return ToolAnnotations with expected values
- Optional parameters (open_world, idempotent) are respected
"""

from mcp.types import ToolAnnotations

from cortex.core.mcp_annotations import (
    destructive_annotations,
    external_annotations,
    read_only_annotations,
    safe_write_annotations,
)


class TestReadOnlyAnnotations:
    """Test read_only_annotations helper."""

    def test_returns_tool_annotations(self) -> None:
        """Helper returns ToolAnnotations instance."""
        out = read_only_annotations("Get Stats")
        assert isinstance(out, ToolAnnotations)

    def test_defaults(self) -> None:
        """Default: readOnly True, idempotent True, openWorld False."""
        out = read_only_annotations("Get Stats")
        assert out.title == "Get Stats"
        assert out.readOnlyHint is True
        assert out.destructiveHint is False
        assert out.idempotentHint is True
        assert out.openWorldHint is False

    def test_idempotent_false(self) -> None:
        """idempotent=False is reflected."""
        out = read_only_annotations("Check Health", idempotent=False)
        assert out.idempotentHint is False

    def test_open_world_true(self) -> None:
        """open_world=True sets openWorldHint True."""
        out = read_only_annotations("Get Rules", open_world=True)
        assert out.openWorldHint is True


class TestSafeWriteAnnotations:
    """Test safe_write_annotations helper."""

    def test_returns_tool_annotations(self) -> None:
        """Helper returns ToolAnnotations instance."""
        out = safe_write_annotations("Manage File")
        assert isinstance(out, ToolAnnotations)

    def test_defaults(self) -> None:
        """Safe write: readOnly False, destructive False, idempotent False."""
        out = safe_write_annotations("Manage File")
        assert out.title == "Manage File"
        assert out.readOnlyHint is False
        assert out.destructiveHint is False
        assert out.idempotentHint is False
        assert out.openWorldHint is False

    def test_open_world_true(self) -> None:
        """open_world=True sets openWorldHint True."""
        out = safe_write_annotations("Fix Quality", open_world=True)
        assert out.openWorldHint is True


class TestDestructiveAnnotations:
    """Test destructive_annotations helper."""

    def test_returns_tool_annotations(self) -> None:
        """Helper returns ToolAnnotations instance."""
        out = destructive_annotations("Rollback Version")
        assert isinstance(out, ToolAnnotations)

    def test_defaults(self) -> None:
        """Destructive: readOnly False, destructive True, idempotent False."""
        out = destructive_annotations("Rollback Version")
        assert out.title == "Rollback Version"
        assert out.readOnlyHint is False
        assert out.destructiveHint is True
        assert out.idempotentHint is False
        assert out.openWorldHint is False


class TestExternalAnnotations:
    """Test external_annotations helper."""

    def test_returns_tool_annotations(self) -> None:
        """Helper returns ToolAnnotations instance."""
        out = external_annotations("Get Synapse Rules", read_only=True)
        assert isinstance(out, ToolAnnotations)

    def test_read_only_true(self) -> None:
        """read_only=True sets readOnlyHint True, openWorldHint always True."""
        out = external_annotations("Get Synapse Rules", read_only=True)
        assert out.title == "Get Synapse Rules"
        assert out.readOnlyHint is True
        assert out.openWorldHint is True
        assert out.destructiveHint is False
        assert out.idempotentHint is False

    def test_read_only_false_destructive_false(self) -> None:
        """read_only=False, destructive=False for external write tools."""
        out = external_annotations(
            "Execute Pre-Commit Checks",
            read_only=False,
            destructive=False,
            idempotent=False,
        )
        assert out.readOnlyHint is False
        assert out.destructiveHint is False
        assert out.idempotentHint is False
        assert out.openWorldHint is True
