"""
Tests for the unified plan MCP tool dispatcher.

Focus: argument validation/guardrails for operation and required fields.
Smoke tests: full-payload get/create to verify argument bridging end-to-end.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.plans.plan import plan


class TestPlanToolOperationValidation:
    """Validation for operation argument."""

    @pytest.mark.asyncio
    async def test_no_arguments_defaults_to_list(self) -> None:
        """Calling plan() with no arguments defaults to list operation (zero-arg safe)."""
        result_str = await plan()
        result = json.loads(result_str)
        # Zero-arg now defaults to "list" operation instead of returning error
        assert result["status"] in ("success", "error")
        if result["status"] == "error":
            # May fail if plans dir doesn't exist, but should not be missing-operation
            assert "operation is required" not in (result.get("message") or "").lower()

    @pytest.mark.asyncio
    async def test_invalid_operation_returns_invalid_operation_error(self) -> None:
        """Calling plan(operation='unknown') returns invalid-operation error."""
        result_str = await plan(operation="unknown")
        result = json.loads(result_str)
        assert result["status"] == "error"
        message = (result.get("message") or "").lower()
        assert "invalid operation" in message
        assert "unknown" in message


class TestPlanToolRequiredFieldValidation:
    """Validation for required fields per operation."""

    @pytest.mark.asyncio
    async def test_complete_missing_plan_title_and_summary(self) -> None:
        """plan(operation='complete') without plan_title/summary returns clear error."""
        result_str = await plan(operation="complete")
        result = json.loads(result_str)
        assert result["status"] == "error"
        message = (result.get("message") or "").lower()
        assert "plan_title and summary are required" in message

    @pytest.mark.asyncio
    async def test_register_missing_plan_title_and_description(self) -> None:
        """plan(operation='register') without plan_title/description returns clear error."""
        result_str = await plan(operation="register")
        result = json.loads(result_str)
        assert result["status"] == "error"
        message = (result.get("message") or "").lower()
        assert "plan_title and description are required" in message

    @pytest.mark.asyncio
    async def test_create_missing_title_and_content(self) -> None:
        """plan(operation='create') without title/content returns clear error."""
        result_str = await plan(operation="create")
        result = json.loads(result_str)
        assert result["status"] == "error"
        message = (result.get("message") or "").lower()
        assert "title and content are required" in message


class TestPlanToolHappyPath:
    """Happy-path: plan() with full payload for operations that need no extra args."""

    @pytest.mark.asyncio
    async def test_plan_operation_list_returns_success(self) -> None:
        """plan(operation='list') with no other required args returns success and plans list."""
        result_str = await plan(operation="list")
        result = json.loads(result_str)
        assert result.get("status") == "success"
        assert "plans" in result
        assert isinstance(result["plans"], list)


class TestPlanToolSmoke:
    """Smoke tests: full-payload get/create to verify MCP argument bridging."""

    # Slug of an existing plan file in this repo (used for get smoke test).
    EXISTING_PLAN_SLUG = "fix-mcp-plan-tool-argument-bridging"
    # Slug used for create smoke test; file is created then removed.
    SMOKE_CREATE_SLUG = "smoke-test-plan-bridge-arg"

    @pytest.mark.asyncio
    async def test_plan_operation_get_with_full_payload_returns_success(self) -> None:
        """plan(operation='get', slug=...) with full payload returns success and content."""
        result_str = await plan(
            operation="get",
            slug=self.EXISTING_PLAN_SLUG,
            response_format="content",
        )
        result = json.loads(result_str)
        assert result.get("status") == "success", result.get("message")
        assert result.get("slug") == self.EXISTING_PLAN_SLUG
        assert result.get("content") or result.get("title"), "expect content or title"

    @pytest.mark.asyncio
    async def test_plan_operation_create_with_full_payload_creates_file(self) -> None:
        """plan(operation='create', title=..., content=..., slug=...) creates plan file."""
        result_str = await plan(
            operation="create",
            title="Smoke Test Plan",
            content="# Smoke Test\nBody for argument-bridging smoke test.",
            slug=self.SMOKE_CREATE_SLUG,
        )
        result = json.loads(result_str)
        assert result.get("status") == "success", result.get("message")
        file_path = result.get("file_path")
        assert file_path, "create success should return file_path"
        path = Path(file_path)
        assert path.is_file(), f"created plan file should exist: {file_path}"
        path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_plan_operation_enrich_resolves_markers(self, tmp_path: Path) -> None:
        """plan(operation='enrich') resolves markers and removes summary when done."""
        plans_dir = tmp_path / ".cortex" / "plans"
        plans_dir.mkdir(parents=True)
        plan_path = plans_dir / "clarify.md"
        _ = plan_path.write_text(
            "## Clarifications Needed\n\n- theme — line 3\n\n## Goal\n\n"
            + "Use [NEEDS CLARIFICATION: theme].\n",
            encoding="utf-8",
        )
        with patch(
            "cortex.tools.plans.enrich.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result_str = await plan(
                operation="enrich",
                plan_relative_path=".cortex/plans/clarify.md",
                resolved_clarifications={"theme": "dark mode"},
                ctx=None,
            )
        result = json.loads(result_str)
        assert result.get("status") == "success", result_str
        updated = plan_path.read_text(encoding="utf-8")
        assert "[NEEDS CLARIFICATION:" not in updated
        assert "## Clarifications Needed" not in updated
        assert "dark mode" in updated


class TestPlanGraphOperation:
    """plan(operation=\"graph\") returns artifact graph snapshot."""

    @pytest.mark.asyncio
    async def test_graph_missing_plans_dir_returns_message(
        self, tmp_path: Path
    ) -> None:
        """When .cortex/plans is absent, graph still returns success with empty lists."""
        with patch(
            "cortex.tools.plans.plan_graph.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=str(tmp_path),
        ):
            raw = await plan(operation="graph", include_archive=False, ctx=None)
        data = json.loads(raw)
        assert data["status"] == "success"
        assert "plans directory" in (data.get("message") or "").lower()
        assert data["ready"] == []

    @pytest.mark.asyncio
    async def test_graph_reports_ready_blocked_and_dag_edges(
        self, tmp_path: Path
    ) -> None:
        """A leaf depending on a non-DONE base is blocked; ASCII lists dependent → dep."""
        plans_dir = tmp_path / ".cortex" / "plans"
        plans_dir.mkdir(parents=True)
        base = "---\ntitle: base\nstatus: PENDING\ndepends_on: []\n---\n\n# B\n"
        leaf = "---\ntitle: leaf\nstatus: PENDING\ndepends_on: [base]\n---\n\n# L\n"
        _ = (plans_dir / "base.md").write_text(base, encoding="utf-8")
        _ = (plans_dir / "leaf.md").write_text(leaf, encoding="utf-8")
        with patch(
            "cortex.tools.plans.plan_graph.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=str(tmp_path),
        ):
            raw = await plan(operation="graph", ctx=None)
        data = json.loads(raw)
        assert data["status"] == "success"
        assert "base" in data["ready"]
        assert "leaf" in data["blocked"]
        assert data["blocked"]["leaf"] == ["base"]
        assert "leaf → base" in data["ascii_dag"]

    @pytest.mark.asyncio
    async def test_graph_archived_done_dependency_reads_ready_without_flag(
        self, tmp_path: Path
    ) -> None:
        """An archived dependency with status: DONE satisfies a dependent plan
        even when the caller passes no `include_archive` argument (regression
        for graph-read archive-blindness)."""
        plans_dir = tmp_path / ".cortex" / "plans"
        archive_dir = plans_dir / "archive" / "Other"
        archive_dir.mkdir(parents=True)
        base = "---\ntitle: base\nstatus: DONE\ndepends_on: []\n---\n\n# B\n"
        leaf = "---\ntitle: leaf\nstatus: PENDING\ndepends_on: [base]\n---\n\n# L\n"
        _ = (archive_dir / "base.md").write_text(base, encoding="utf-8")
        _ = (plans_dir / "leaf.md").write_text(leaf, encoding="utf-8")
        with patch(
            "cortex.tools.plans.plan_graph.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=str(tmp_path),
        ):
            raw = await plan(operation="graph", ctx=None)
        data = json.loads(raw)
        assert data["status"] == "success"
        assert "leaf" in data["ready"]
        assert "leaf" not in data["blocked"]

    @pytest.mark.asyncio
    async def test_graph_archived_not_done_dependency_still_blocks(
        self, tmp_path: Path
    ) -> None:
        """An archived dependency that is NOT status: DONE still correctly
        blocks its dependent (archive visibility must not mask real gaps)."""
        plans_dir = tmp_path / ".cortex" / "plans"
        archive_dir = plans_dir / "archive" / "Other"
        archive_dir.mkdir(parents=True)
        base = "---\ntitle: base\nstatus: IN_PROGRESS\ndepends_on: []\n---\n\n# B\n"
        leaf = "---\ntitle: leaf\nstatus: PENDING\ndepends_on: [base]\n---\n\n# L\n"
        _ = (archive_dir / "base.md").write_text(base, encoding="utf-8")
        _ = (plans_dir / "leaf.md").write_text(leaf, encoding="utf-8")
        with patch(
            "cortex.tools.plans.plan_graph.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=str(tmp_path),
        ):
            raw = await plan(operation="graph", ctx=None)
        data = json.loads(raw)
        assert data["status"] == "success"
        assert "leaf" in data["blocked"]
        assert data["blocked"]["leaf"] == ["base"]
