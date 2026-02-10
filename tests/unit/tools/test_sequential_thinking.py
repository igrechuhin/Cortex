"""Unit tests for sequential thinking tool and core.

Covers SequentialThinkingCore.process_thought, output shape, edge cases,
and handler response. Target ≥95% coverage for sequential_thinking module.
"""

import json
import os
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field

from cortex.tools.sequential_thinking import (
    SequentialThinkingCore,
    SequentialThinkingInput,
    reset_core_for_testing,
    sequentialthinking,
)


def _input(
    thought: str,
    next_thought_needed: bool,
    thought_number: int,
    total_thoughts: int,
    *,
    is_revision: bool = False,
    revises_thought: int | None = None,
    branch_from_thought: int | None = None,
    branch_id: str | None = None,
    needs_more_thoughts: bool = False,
) -> SequentialThinkingInput:
    """Build SequentialThinkingInput with optional params defaulted."""
    return SequentialThinkingInput(
        thought=thought,
        next_thought_needed=next_thought_needed,
        thought_number=thought_number,
        total_thoughts=total_thoughts,
        is_revision=is_revision,
        revises_thought=revises_thought,
        branch_from_thought=branch_from_thought,
        branch_id=branch_id,
        needs_more_thoughts=needs_more_thoughts,
    )


# Response model with camelCase aliases for validating tool JSON output
class SequentialThinkingResponse(BaseModel):
    """Tool JSON response shape (camelCase keys)."""

    thoughtNumber: int = Field(..., alias="thoughtNumber")
    totalThoughts: int = Field(..., alias="totalThoughts")
    nextThoughtNeeded: bool = Field(..., alias="nextThoughtNeeded")
    branches: list[str] = Field(..., alias="branches")
    thoughtHistoryLength: int = Field(..., alias="thoughtHistoryLength")

    model_config = {"populate_by_name": True}


# =============================================================================
# Core: process_thought
# =============================================================================


class TestSequentialThinkingCoreFirstThought:
    """First thought and basic append."""

    def test_process_thought_first_thought_appends_to_history(self):
        core = SequentialThinkingCore()
        inp = _input("First step", True, 1, 3)
        out = core.process_thought(inp)
        assert out.thought_number == 1
        assert out.total_thoughts == 3
        assert out.next_thought_needed is True
        assert out.branches == []
        assert out.thought_history_length == 1

    def test_process_thought_second_thought_increases_history_length(self):
        core = SequentialThinkingCore()
        _ = core.process_thought(_input("One", True, 1, 2))
        out = core.process_thought(_input("Two", False, 2, 2))
        assert out.thought_history_length == 2
        assert out.thought_number == 2
        assert out.next_thought_needed is False


class TestSequentialThinkingCoreTotalThoughtsAdjustment:
    """When thought_number > total_thoughts, total is adjusted."""

    def test_process_thought_adjusts_total_when_thought_number_exceeds(self):
        core = SequentialThinkingCore()
        inp = _input("Step 5", True, 5, 3)
        out = core.process_thought(inp)
        assert out.total_thoughts == 5
        assert out.thought_number == 5
        assert out.thought_history_length == 1


class TestSequentialThinkingCoreBranches:
    """Branch recording: both branch_from_thought and branch_id required."""

    def test_process_thought_records_branch_when_both_branch_params_set(self):
        core = SequentialThinkingCore()
        _ = core.process_thought(_input("Base", True, 1, 2))
        out = core.process_thought(
            _input("Branch A", False, 2, 2, branch_from_thought=1, branch_id="alt")
        )
        assert "alt" in out.branches
        assert out.thought_history_length == 2

    def test_process_thought_ignores_branch_when_only_branch_id_set(self):
        core = SequentialThinkingCore()
        out = core.process_thought(
            _input("No branch point", False, 1, 1, branch_id="orphan")
        )
        assert out.branches == []

    def test_process_thought_ignores_branch_when_only_branch_from_thought_set(self):
        core = SequentialThinkingCore()
        out = core.process_thought(
            _input("No branch id", False, 1, 1, branch_from_thought=1)
        )
        assert out.branches == []

    def test_process_thought_multiple_branches_sorted_in_output(self):
        core = SequentialThinkingCore()
        _ = core.process_thought(_input("Root", True, 1, 3))
        _ = core.process_thought(
            _input("Z-branch", False, 2, 3, branch_from_thought=1, branch_id="z")
        )
        out = core.process_thought(
            _input("A-branch", False, 2, 3, branch_from_thought=1, branch_id="a")
        )
        assert out.branches == ["a", "z"]

    def test_process_thought_same_branch_twice_appends_both_entries(self):
        core = SequentialThinkingCore()
        _ = core.process_thought(_input("Root", True, 1, 3))
        _ = core.process_thought(
            _input("Branch first", False, 2, 3, branch_from_thought=1, branch_id="b")
        )
        out = core.process_thought(
            _input("Branch second", False, 3, 3, branch_from_thought=1, branch_id="b")
        )
        assert out.branches == ["b"]
        assert out.thought_history_length == 3


class TestSequentialThinkingCoreOptionalParams:
    """Optional params omitted or set; revision fields do not change behavior."""

    def test_process_thought_with_revision_flags_still_appends(self):
        core = SequentialThinkingCore()
        out = core.process_thought(
            _input("Revised step", False, 2, 2, is_revision=True, revises_thought=1)
        )
        assert out.thought_history_length == 1
        assert out.thought_number == 2

    def test_process_thought_empty_thought_string_allowed(self):
        core = SequentialThinkingCore()
        out = core.process_thought(_input("", False, 1, 1))
        assert out.thought_history_length == 1


# =============================================================================
# Output shape (via handler; JSON uses camelCase)
# =============================================================================


@pytest.mark.asyncio
class TestSequentialthinkingHandler:
    """Handler returns valid JSON with expected shape and camelCase keys."""

    async def test_sequentialthinking_returns_json_with_camel_case_keys(self):
        with patch(
            "cortex.tools.sequential_thinking._get_core",
            return_value=SequentialThinkingCore(),
        ):
            result = await sequentialthinking(
                thought="Test",
                next_thought_needed=False,
                thought_number=1,
                total_thoughts=1,
            )
        data = json.loads(result)
        assert "thoughtNumber" in data
        assert "totalThoughts" in data
        assert "nextThoughtNeeded" in data
        assert "branches" in data
        assert "thoughtHistoryLength" in data
        parsed = SequentialThinkingResponse.model_validate(data)
        assert parsed.thoughtNumber == 1
        assert parsed.totalThoughts == 1
        assert parsed.thoughtHistoryLength == 1
        assert parsed.branches == []

    async def test_sequentialthinking_second_call_increases_history_length(self):
        with patch(
            "cortex.tools.sequential_thinking._get_core",
            return_value=SequentialThinkingCore(),
        ):
            await sequentialthinking(
                thought="First",
                next_thought_needed=True,
                thought_number=1,
                total_thoughts=2,
            )
            result = await sequentialthinking(
                thought="Second",
                next_thought_needed=False,
                thought_number=2,
                total_thoughts=2,
            )
        data = json.loads(result)
        assert data["thoughtHistoryLength"] == 2
        assert data["thoughtNumber"] == 2

    async def test_sequentialthinking_with_branch_records_branch(self):
        with patch(
            "cortex.tools.sequential_thinking._get_core",
            return_value=SequentialThinkingCore(),
        ):
            await sequentialthinking(
                thought="Root",
                next_thought_needed=True,
                thought_number=1,
                total_thoughts=2,
            )
            result = await sequentialthinking(
                thought="Branch",
                next_thought_needed=False,
                thought_number=2,
                total_thoughts=2,
                branch_from_thought=1,
                branch_id="my-branch",
            )
        data = json.loads(result)
        assert "my-branch" in data["branches"]
        assert data["thoughtHistoryLength"] == 2

    async def test_sequentialthinking_get_core_creates_core_when_none(self):
        reset_core_for_testing()
        result = await sequentialthinking(
            thought="First",
            next_thought_needed=False,
            thought_number=1,
            total_thoughts=1,
        )
        data = json.loads(result)
        assert data["thoughtHistoryLength"] == 1
        result2 = await sequentialthinking(
            thought="Second",
            next_thought_needed=False,
            thought_number=2,
            total_thoughts=2,
        )
        data2 = json.loads(result2)
        assert data2["thoughtHistoryLength"] == 2

    async def test_sequentialthinking_disabled_logging_skips_stderr(self):
        with patch(
            "cortex.tools.sequential_thinking._get_core",
            return_value=SequentialThinkingCore(),
        ):
            with patch.dict(os.environ, {"DISABLE_THOUGHT_LOGGING": "true"}):
                result = await sequentialthinking(
                    thought="No log",
                    next_thought_needed=False,
                    thought_number=1,
                    total_thoughts=1,
                )
        data = json.loads(result)
        assert data["thoughtNumber"] == 1

    async def test_sequentialthinking_log_oserror_handled(self):
        with patch(
            "cortex.tools.sequential_thinking._get_core",
            return_value=SequentialThinkingCore(),
        ):
            with patch("sys.stderr") as mock_stderr:
                mock_stderr.write.side_effect = OSError("stderr closed")
                result = await sequentialthinking(
                    thought="Oops",
                    next_thought_needed=False,
                    thought_number=1,
                    total_thoughts=1,
                )
        data = json.loads(result)
        assert data["thoughtHistoryLength"] == 1
