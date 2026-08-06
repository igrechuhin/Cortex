"""Tests for the agentic tool-selection evaluation harness.

Fully mocked: no `anthropic` import, no network call, no live model. The model
client is a scripted stub implementing ``ModelClientProtocol``.
"""

from __future__ import annotations

import asyncio
import collections
import glob
import json
from pathlib import Path
from typing import cast

import pytest

from cortex.tools.evaluation._agent_loop import (
    build_task_prompt,
    parse_agent_output,
    run_agent_loop,
)
from cortex.tools.evaluation._agentic_models import (
    EvalTaskKind,
    ModelMessage,
    ModelToolCall,
    ModelToolSchema,
    ModelTurn,
    ParsedAgentOutput,
    enforce_kind_invariants,
)
from cortex.tools.evaluation._models import EvalTask

FINAL_TEXT = (
    "<summary>Called the tool.</summary>"
    "<feedback>plan: the description overlaps manage_file.</feedback>"
    "<response>Done.</response>"
)


class ScriptedClient:
    """Model client returning a fixed sequence of turns."""

    def __init__(self, turns: list[ModelTurn]) -> None:
        self._turns = list(turns)
        self.calls = 0

    async def complete(
        self, messages: list[ModelMessage], tools: list[ModelToolSchema]
    ) -> ModelTurn:
        self.calls += 1
        if self._turns:
            return self._turns.pop(0)
        return ModelTurn(text=FINAL_TEXT)


class LoopingClient:
    """Model client that never stops requesting tool calls."""

    async def complete(
        self, messages: list[ModelMessage], tools: list[ModelToolSchema]
    ) -> ModelTurn:
        return ModelTurn(
            text="working",
            tool_calls=[ModelToolCall(call_id="c", tool_name="plan", arguments={})],
        )


class RaisingClient:
    """Model client that fails on every request."""

    async def complete(
        self, messages: list[ModelMessage], tools: list[ModelToolSchema]
    ) -> ModelTurn:
        raise RuntimeError("boom")


class FakeSession:
    """In-memory ``ToolSessionProtocol`` stub."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.invoked: list[str] = []

    async def list_tool_schemas(self) -> list[ModelToolSchema]:
        return [ModelToolSchema(name="plan", description="Plan lifecycle")]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> str:
        self.invoked.append(name)
        if self.fail:
            raise RuntimeError("tool exploded")
        return "ok"


# --- Fixture validation -----------------------------------------------------


def test_near_miss_without_covered_by_is_rejected() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="requires a covered_by"):
        _ = EvalTask(
            id="x",
            name="x",
            description="d",
            kind=EvalTaskKind.NEAR_MISS,
            expected_tools=["plan"],
            expected_outcome="o",
        )


def test_control_with_covered_by_is_rejected() -> None:
    with pytest.raises(ValueError, match="only valid for near-miss"):
        _ = EvalTask(
            id="x",
            name="x",
            description="d",
            kind=EvalTaskKind.CONTROL,
            covered_by="plan",
            expected_outcome="o",
        )


def test_control_with_expected_tools_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not declare expected_tools"):
        _ = EvalTask(
            id="x",
            name="x",
            description="d",
            kind=EvalTaskKind.CONTROL,
            expected_tools=["plan"],
            expected_outcome="o",
        )


def test_near_miss_without_expected_tools_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty expected_tools"):
        enforce_kind_invariants(EvalTaskKind.NEAR_MISS, "plan", [])


def test_unknown_kind_is_a_validation_error() -> None:
    with pytest.raises(ValueError):
        _ = EvalTask.model_validate(
            {
                "id": "x",
                "name": "x",
                "description": "d",
                "kind": "sideways",
                "expected_outcome": "o",
            }
        )


def test_existing_fixtures_default_to_positive_and_have_unique_ids() -> None:
    # Arrange
    counter: collections.Counter[str] = collections.Counter()
    kinds: collections.Counter[str] = collections.Counter()
    # Act
    for path in sorted(glob.glob(".cortex/evals/tasks/*.json")):
        for raw in json.loads(Path(path).read_text(encoding="utf-8")):
            task = EvalTask.model_validate(raw)
            counter[task.id] += 1
            kinds[task.kind.value] += 1
    # Assert
    assert [tid for tid, n in counter.items() if n > 1] == []
    assert kinds["control"] >= 5
    assert kinds["near-miss"] >= 5
    assert kinds["positive"] >= 1


# --- Agent loop -------------------------------------------------------------


def test_parse_agent_output_extracts_all_blocks() -> None:
    parsed = parse_agent_output(FINAL_TEXT)
    assert parsed.summary == "Called the tool."
    assert "manage_file" in parsed.feedback
    assert parsed.response == "Done."


def test_parse_agent_output_tolerates_missing_and_malformed_blocks() -> None:
    parsed = parse_agent_output("<summary>only this<feedback>unclosed")
    assert parsed == ParsedAgentOutput(summary="", feedback="", response="")


def test_build_task_prompt_includes_task_fields() -> None:
    prompt = build_task_prompt("Do the thing", "It is done")
    assert "Do the thing" in prompt and "It is done" in prompt


def test_agent_loop_captures_called_tools() -> None:
    # Arrange
    session = FakeSession()
    client = ScriptedClient(
        [
            ModelTurn(
                tool_calls=[
                    ModelToolCall(call_id="1", tool_name="plan", arguments={"a": 1})
                ]
            ),
            ModelTurn(text=FINAL_TEXT),
        ]
    )
    # Act
    outcome = asyncio.run(run_agent_loop(session, client, "prompt"))
    # Assert
    assert outcome.tools_called == ["plan"]
    assert outcome.turns == 2
    assert outcome.parsed.response == "Done."
    assert session.invoked == ["plan"]


def test_agent_loop_records_tool_errors_without_crashing() -> None:
    session = FakeSession(fail=True)
    client = ScriptedClient(
        [
            ModelTurn(tool_calls=[ModelToolCall(call_id="1", tool_name="plan")]),
            ModelTurn(text=FINAL_TEXT),
        ]
    )
    outcome = asyncio.run(run_agent_loop(session, client, "p"))
    assert outcome.tools_called == ["plan"]
    assert outcome.error is None


def test_agent_loop_enforces_turn_cap() -> None:
    outcome = asyncio.run(
        run_agent_loop(FakeSession(), LoopingClient(), "p", max_turns=3)
    )
    assert outcome.turn_cap_reached is True
    assert outcome.turns == 3
    assert outcome.error is not None and "turn cap" in outcome.error


def test_agent_loop_records_model_error() -> None:
    outcome = asyncio.run(run_agent_loop(FakeSession(), RaisingClient(), "p"))
    assert outcome.error is not None and "boom" in outcome.error
    assert outcome.turns == 0


def test_agent_loop_handles_zero_tool_calls() -> None:
    outcome = asyncio.run(
        run_agent_loop(FakeSession(), ScriptedClient([ModelTurn(text="")]), "p")
    )
    assert outcome.tools_called == []
    assert outcome.parsed.response == ""


def _published_tool_names() -> set[str]:
    """The tool names Cortex publishes as its MCP surface."""
    import importlib

    from cortex.discovery.published_inventory import published_inventory_payload

    _ = importlib.import_module("cortex.tools")  # registers the tool decorators
    raw_names = published_inventory_payload()["tool_names"]
    assert isinstance(raw_names, list)
    return {str(name) for name in cast(list[object], raw_names)}


def _load_all_fixture_tasks() -> list[EvalTask]:
    """Validate every task in every fixture file."""
    tasks: list[EvalTask] = []
    for path in sorted(glob.glob(".cortex/evals/tasks/*.json")):
        for raw in json.loads(Path(path).read_text(encoding="utf-8")):
            tasks.append(EvalTask.model_validate(raw))
    return tasks


def test_negative_fixture_tool_references_are_registered_tools() -> None:
    """A negative case naming an unregistered tool can never fire."""
    # Arrange
    published = _published_tool_names()
    negatives = [
        task
        for task in _load_all_fixture_tasks()
        if task.kind is not EvalTaskKind.POSITIVE
    ]
    # Act
    unresolved = {
        task.id: sorted(
            name
            for name in [*task.expected_tools, *filter(None, [task.covered_by])]
            if name not in published
        )
        for task in negatives
    }
    # Assert
    assert {tid: miss for tid, miss in unresolved.items() if miss} == {}


def test_negative_fixture_counts_meet_the_paired_minimum() -> None:
    # Arrange
    tasks = _load_all_fixture_tasks()
    # Act
    controls = [t for t in tasks if t.kind is EvalTaskKind.CONTROL]
    near_misses = [t for t in tasks if t.kind is EvalTaskKind.NEAR_MISS]
    # Assert
    assert len(controls) >= 5
    assert len(near_misses) >= 5
    assert all(t.covered_by for t in near_misses)
    assert all(not t.expected_tools for t in controls)
