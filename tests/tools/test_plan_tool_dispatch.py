"""
Tests for the unified plan MCP tool dispatcher.

Focus: argument validation/guardrails for operation and required fields.
Smoke tests: full-payload get/create to verify argument bridging end-to-end.
"""

import json
from pathlib import Path

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
