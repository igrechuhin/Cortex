"""Adapter, session, and dashboard tests for the agentic eval harness.

Fully mocked: the Anthropic SDK is replaced by local stub objects and no
network call is made.
"""

from __future__ import annotations

import asyncio
from typing import cast

import pytest
from fastmcp.tools import Tool

from cortex.tools.evaluation._agentic_models import (
    AgenticSkipReason,
    AgenticSummary,
    AgentLoopOutcome,
    EvalTaskKind,
    ModelMessage,
    ModelToolCall,
    ModelToolSchema,
    ParsedAgentOutput,
)
from cortex.tools.evaluation._agentic_scoring import (
    build_scorecard,
    collect_feedback,
    score_task,
)
from cortex.tools.evaluation._agentic_suite import build_skipped_outcome
from cortex.tools.evaluation._anthropic_client import (
    AnthropicModelClient,
    normalize_response,
    to_api_messages,
    to_api_tools,
)
from cortex.tools.evaluation._local_session import (
    UNAVAILABLE_TEMPLATE,
    LocalToolSession,
    build_local_session,
    load_registered_tool_schemas,
    missing_published_tools,
    to_tool_schema,
)
from cortex.tools.evaluation._models import EvalTask
from cortex.tools.evaluation.evaluation_dashboard_helpers import (
    format_agentic_section,
)


def _positive_task(task_id: str = "pos-1") -> EvalTask:
    return EvalTask(
        id=task_id,
        name="Positive",
        description="Create a plan",
        expected_tools=["plan"],
        expected_outcome="A plan exists",
    )


def _control_task(task_id: str = "ctl-1") -> EvalTask:
    return EvalTask(
        id=task_id,
        name="Control",
        description="Rename a variable",
        kind=EvalTaskKind.CONTROL,
        expected_outcome="Renamed",
    )


def _near_miss_task(task_id: str = "nm-1") -> EvalTask:
    return EvalTask(
        id=task_id,
        name="Near miss",
        description="Write a plan file",
        kind=EvalTaskKind.NEAR_MISS,
        expected_tools=["manage_file"],
        covered_by="plan",
        expected_outcome="Plan tool used",
    )


def _outcome(tools: list[str], response: str = "Done.") -> AgentLoopOutcome:
    return AgentLoopOutcome(
        tools_called=tools,
        turns=1,
        parsed=ParsedAgentOutput(summary="s", feedback="f", response=response),
    )


class TextBlock:
    """Stub of an Anthropic text content block."""

    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class ToolUseBlock:
    """Stub of an Anthropic tool_use content block."""

    def __init__(self, block_id: str, name: str, payload: object) -> None:
        self.type = "tool_use"
        self.id = block_id
        self.name = name
        self.input = payload


class OtherBlock:
    """Stub of a content block the adapter should ignore."""

    def __init__(self) -> None:
        self.type = "thinking"


class FakeResponse:
    """Stub of an Anthropic messages response."""

    def __init__(
        self, content: list[object] | None = None, stop_reason: str = ""
    ) -> None:
        if content is not None:
            self.content = content
        self.stop_reason = stop_reason


class FakeMessagesApi:
    """Stub ``messages`` sub-API capturing the request kwargs."""

    def __init__(self) -> None:
        self.captured: dict[str, object] = {}

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> object:
        self.captured = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "tools": tools,
        }
        return FakeResponse(content=[TextBlock("done")])


def test_normalize_response_splits_text_and_tool_calls() -> None:
    raw = FakeResponse(
        content=[
            TextBlock("hello"),
            ToolUseBlock("1", "plan", {"a": 1}),
            OtherBlock(),
        ],
        stop_reason="tool_use",
    )
    turn = normalize_response(raw)
    assert turn.text == "hello"
    assert turn.tool_calls == [
        ModelToolCall(call_id="1", tool_name="plan", arguments={"a": 1})
    ]
    assert turn.stop_reason == "tool_use"


def test_normalize_response_tolerates_missing_content() -> None:
    turn = normalize_response(FakeResponse())
    assert turn.text == "" and turn.tool_calls == []


def test_to_api_messages_and_tools_render_blocks() -> None:
    messages = [
        ModelMessage(role="user", text="hi"),
        ModelMessage(
            role="assistant",
            tool_calls=[ModelToolCall(call_id="1", tool_name="plan")],
        ),
        ModelMessage(role="user"),
    ]
    rendered = to_api_messages(messages)
    assert len(rendered) == 2
    tools = to_api_tools([ModelToolSchema(name="plan", description="d")])
    assert tools[0]["input_schema"] == {"type": "object", "properties": {}}


def test_anthropic_client_complete_normalizes() -> None:
    # Arrange
    messages_api = FakeMessagesApi()
    client = AnthropicModelClient(messages_api)
    # Act
    turn = asyncio.run(
        client.complete(
            [ModelMessage(role="user", text="hi")],
            [ModelToolSchema(name="plan", description="d")],
        )
    )
    # Assert
    assert turn.text == "done"
    assert messages_api.captured["model"]


# --- Local session ----------------------------------------------------------


def _tool(name: str, description: str | None, parameters: dict[str, object]) -> Tool:
    """Build a registered FastMCP tool with the attributes the adapter reads."""
    return Tool(name=name, description=description, parameters=parameters)


def test_to_tool_schema_projects_registered_tool() -> None:
    schema = to_tool_schema(_tool("plan", None, {"type": "object"}))
    assert schema.name == "plan" and schema.description == ""


def test_local_session_returns_placeholder_for_unregistered_tool() -> None:
    session = LocalToolSession([ModelToolSchema(name="plan", description="d")])
    assert asyncio.run(session.list_tool_schemas())[0].name == "plan"
    output = asyncio.run(session.call_tool("plan", {}))
    assert output == UNAVAILABLE_TEMPLATE.format(name="plan")


# --- Dashboard --------------------------------------------------------------


def test_dashboard_omits_accuracy_for_unpaired_run() -> None:
    card = build_scorecard([score_task(_positive_task(), _outcome(["plan"]))])
    text = "\n".join(format_agentic_section(AgenticSummary(scorecard=card)))
    assert "not reported" in text
    assert "%" not in text.split("Control")[0]


def test_dashboard_reports_paired_scorecard_and_feedback() -> None:
    results = [
        score_task(_positive_task(), _outcome(["plan"])),
        score_task(_control_task(), _outcome([])),
        score_task(_near_miss_task(), _outcome(["plan"])),
    ]
    summary = AgenticSummary(
        scorecard=build_scorecard(results),
        results=results,
        feedback=collect_feedback(_positive_task(), _outcome(["plan"])),
    )
    text = "\n".join(format_agentic_section(summary))
    assert "Selection Accuracy:** 100.0%" in text
    assert "Near-Miss False Positives" in text
    assert "Model Feedback on Tool Descriptions" in text


def test_dashboard_reports_skip() -> None:
    outcome = build_skipped_outcome(
        [_positive_task()], AgenticSkipReason.API_KEY_MISSING
    )
    text = "\n".join(format_agentic_section(outcome.summary))
    assert "Skipped: api_key_missing" in text
    assert format_agentic_section(None) == []


class FakeMcp:
    """Stub FastMCP instance exposing the real `list_tools` shape (a list)."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools = tools

    async def list_tools(self) -> list[Tool]:
        return self._tools


def test_load_registered_tool_schemas_projects_live_list_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: `list_tools()` returns a list, not a dict (no `.items()`)."""
    # Arrange
    tools = [
        _tool("session", "Session lifecycle", {}),
        _tool("plan", "Plan lifecycle", {"type": "object"}),
    ]
    monkeypatch.setattr("cortex.server.mcp", FakeMcp(tools))
    # Act
    schemas = asyncio.run(load_registered_tool_schemas())
    # Assert
    assert [s.name for s in schemas] == ["plan", "session"]
    assert schemas[0].input_schema == {"type": "object"}
    assert schemas[1].description == "Session lifecycle"


def test_load_registered_tool_schemas_against_the_real_server() -> None:
    """Regression guard: the live FastMCP tool API keeps the shape we call.

    This exercises the real `cortex.server.mcp.list_tools()` in process (no
    network). It is the check that would have caught `get_tools()` not existing.
    """
    # Arrange / Act
    schemas = asyncio.run(load_registered_tool_schemas())
    # Assert
    assert schemas, "live server exposed no tools"
    names = [s.name for s in schemas]
    assert names == sorted(names)
    assert "session" in names and "plan" in names
    for schema in schemas:
        assert schema.description, f"{schema.name} has no description"
        assert isinstance(schema.input_schema, dict)


def test_missing_published_tools_reports_visibility_gated_tools() -> None:
    # Arrange
    schemas = asyncio.run(load_registered_tool_schemas())
    # Act
    missing = missing_published_tools(schemas)
    # Assert: whatever is published but not visible must be named, never silent.
    exposed = {s.name for s in schemas}
    assert all(name not in exposed for name in missing)
    assert missing == sorted(missing)


def test_missing_published_tools_is_empty_when_all_exposed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    from cortex.discovery.published_inventory import published_inventory_payload

    raw_published = published_inventory_payload()["tool_names"]
    assert isinstance(raw_published, list)
    published = cast(list[str], raw_published)
    schemas = [ModelToolSchema(name=n, description="d") for n in published]
    # Act / Assert
    assert missing_published_tools(schemas) == []


def test_build_local_session_wraps_registered_schemas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setattr("cortex.server.mcp", FakeMcp([_tool("plan", "d", {})]))
    # Act
    session = asyncio.run(build_local_session())
    # Assert
    assert [s.name for s in asyncio.run(session.list_tool_schemas())] == ["plan"]
