"""Unit tests for execution_monitoring module."""

import json

import pytest

from cortex.tools.execution_monitoring import (
    log_apply_result,
    log_invalid_action_and_return,
    warn_suggestion_not_found_and_return,
)


class TestLogApplyResult:
    """Tests for log_apply_result."""

    @pytest.mark.asyncio
    async def test_returns_output_when_no_exception(self) -> None:
        """When exc is None, returns the output string."""
        result = await log_apply_result(ctx=None, out='{"status":"success"}', exc=None)
        assert json.loads(result)["status"] == "success"

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_out_none_and_no_exc(self) -> None:
        """When out is None and exc is None, returns empty string."""
        result = await log_apply_result(ctx=None, out=None, exc=None)
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_error_response_when_exception(self) -> None:
        """When exc is set, returns create_execution_error_response JSON."""
        exc = RuntimeError("Test failure")
        result = await log_apply_result(ctx=None, out=None, exc=exc)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "Test failure" in data["error"]
        assert data["error_type"] == "RuntimeError"


class TestLogInvalidActionAndReturn:
    """Tests for log_invalid_action_and_return."""

    @pytest.mark.asyncio
    async def test_returns_invalid_action_error_json(self) -> None:
        """Returns create_invalid_action_error JSON for invalid action."""
        result = await log_invalid_action_and_return(ctx=None, action="invalid_action")
        data = json.loads(result)
        assert data["status"] == "error"
        assert "invalid_action" in data.get("error", "")
        assert "available_options" in data


class TestWarnSuggestionNotFoundAndReturn:
    """Tests for warn_suggestion_not_found_and_return."""

    @pytest.mark.asyncio
    async def test_returns_suggestion_string_unchanged(self) -> None:
        """Returns the suggestion error JSON string unchanged."""
        error_json = '{"status":"error","error":"Suggestion \'x\' not found"}'
        result = await warn_suggestion_not_found_and_return(
            ctx=None, suggestion=error_json
        )
        assert result == error_json
        data = json.loads(result)
        assert data["status"] == "error"
        assert "not found" in data["error"]
