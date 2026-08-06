"""Scoring, pairing enforcement, suite assembly, and dependency-gating tests.

Fully mocked: a scripted stub model client, no `anthropic` SDK, no network.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types

import pytest

from cortex.tools.evaluation._agentic_models import (
    AgenticScorecard,
    AgenticSkipReason,
    AgentLoopOutcome,
    EvalTaskKind,
    ModelMessage,
    ModelToolCall,
    ModelToolSchema,
    ModelTurn,
    ParsedAgentOutput,
    UnpairedReason,
)
from cortex.tools.evaluation._agentic_scoring import (
    build_scorecard,
    collect_feedback,
    score_task,
)
from cortex.tools.evaluation._agentic_suite import (
    build_skipped_outcome,
    run_agentic_suite,
    select_agentic_tasks,
)
from cortex.tools.evaluation._anthropic_client import (
    AnthropicModelClient,
    resolve_model_client,
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


class FakeSession:
    """In-memory ``ToolSessionProtocol`` stub over a configurable surface."""

    def __init__(self, exposed: list[str] | None = None) -> None:
        self.invoked: list[str] = []
        self.exposed = exposed if exposed is not None else ["plan", "manage_file"]

    async def list_tool_schemas(self) -> list[ModelToolSchema]:
        return [ModelToolSchema(name=n, description=f"{n} tool") for n in self.exposed]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> str:
        self.invoked.append(name)
        return "ok"


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


# --- Scoring ----------------------------------------------------------------


def test_positive_passes_on_superset_of_expected_tools() -> None:
    result = score_task(_positive_task(), _outcome(["plan", "session"]))
    assert result.passed is True and result.reason == ""


def test_positive_fails_on_disjoint_tools_with_reason() -> None:
    result = score_task(_positive_task(), _outcome(["manage_file"]))
    assert result.passed is False
    assert "expected tools not called" in result.reason


def test_positive_fails_on_empty_call_set() -> None:
    result = score_task(_positive_task(), _outcome([]))
    assert result.passed is False


def test_positive_fails_on_not_found_response() -> None:
    result = score_task(_positive_task(), _outcome(["plan"], response="NOT_FOUND"))
    assert result.passed is False and "NOT_FOUND" in result.reason


def test_control_passes_on_zero_tool_calls() -> None:
    assert score_task(_control_task(), _outcome([])).passed is True


def test_control_fails_on_any_tool_call() -> None:
    result = score_task(_control_task(), _outcome(["think"]))
    assert result.passed is False and "think" in result.reason


def test_near_miss_fails_when_tempting_tool_called() -> None:
    result = score_task(_near_miss_task(), _outcome(["manage_file"]))
    assert result.passed is False and "tempting tool" in result.reason


def test_near_miss_passes_when_covering_tool_used_instead() -> None:
    result = score_task(_near_miss_task(), _outcome(["plan"]))
    assert result.passed is True
    assert result.covered_by_used is True


def test_turn_cap_error_turns_a_pass_into_a_failure() -> None:
    outcome = _outcome(["plan"]).model_copy(update={"error": "turn cap of 3 reached"})
    assert score_task(_positive_task(), outcome).passed is False


def test_collect_feedback_attaches_text_to_each_expected_tool() -> None:
    records = collect_feedback(_positive_task(), _outcome(["plan"]))
    assert [r.tool_name for r in records] == ["plan"]
    assert records[0].feedback == "f"


def test_collect_feedback_is_empty_when_block_missing() -> None:
    outcome = AgentLoopOutcome(parsed=ParsedAgentOutput(feedback="  "))
    assert collect_feedback(_positive_task(), outcome) == []


def test_collect_feedback_for_control_task_uses_placeholder_tool() -> None:
    records = collect_feedback(_control_task(), _outcome([]))
    assert [r.tool_name for r in records] == ["<none>"]


# --- Pairing enforcement ----------------------------------------------------


def test_positives_only_run_emits_no_accuracy_figure() -> None:
    # Arrange
    results = [score_task(_positive_task(), _outcome(["plan"]))]
    # Act
    card = build_scorecard(results)
    # Assert
    assert card.paired is False
    assert card.selection_accuracy is None
    assert card.unpaired_reason is UnpairedReason.NO_NEGATIVE_TASKS
    assert "selection_accuracy" not in json.dumps(
        card.model_dump(mode="json", exclude_none=True)
    )


def test_missing_near_miss_alone_is_reported_as_unpaired() -> None:
    results = [
        score_task(_positive_task(), _outcome(["plan"])),
        score_task(_control_task(), _outcome([])),
    ]
    card = build_scorecard(results)
    assert card.unpaired_reason is UnpairedReason.NO_NEAR_MISS_TASKS


def test_missing_control_alone_is_reported_as_unpaired() -> None:
    results = [
        score_task(_positive_task(), _outcome(["plan"])),
        score_task(_near_miss_task(), _outcome(["plan"])),
    ]
    card = build_scorecard(results)
    assert card.unpaired_reason is UnpairedReason.NO_CONTROL_TASKS


def test_negatives_only_run_is_reported_as_unpaired() -> None:
    results = [
        score_task(_control_task(), _outcome([])),
        score_task(_near_miss_task(), _outcome(["plan"])),
    ]
    card = build_scorecard(results)
    assert card.unpaired_reason is UnpairedReason.NO_POSITIVE_TASKS


def test_paired_run_reports_accuracy_and_both_rates_separately() -> None:
    # Arrange
    results = [
        score_task(_positive_task(), _outcome(["plan"])),
        score_task(_positive_task("pos-2"), _outcome([])),
        score_task(_control_task(), _outcome(["think"])),
        score_task(_near_miss_task(), _outcome(["plan"])),
    ]
    # Act
    card = build_scorecard(results)
    # Assert
    assert card.paired is True
    assert card.selection_accuracy == 0.5
    assert card.control_false_positive_rate == 1.0
    assert card.near_miss_false_positive_rate == 0.0
    assert card.control_false_positive_rate != card.near_miss_false_positive_rate


def test_scorecard_model_forbids_accuracy_without_pairing() -> None:
    with pytest.raises(ValueError, match="must not carry selection_accuracy"):
        _ = AgenticScorecard(
            paired=False,
            unpaired_reason=UnpairedReason.NO_CONTROL_TASKS,
            selection_accuracy=1.0,
        )


def test_scorecard_model_requires_reason_when_unpaired() -> None:
    with pytest.raises(ValueError, match="must carry an unpaired_reason"):
        _ = AgenticScorecard(paired=False)


def test_scorecard_model_requires_accuracy_when_paired() -> None:
    with pytest.raises(ValueError, match="must carry selection_accuracy"):
        _ = AgenticScorecard(paired=True)


# --- Suite ------------------------------------------------------------------


def test_select_agentic_tasks_drops_usage_only_positives() -> None:
    usage_only = EvalTask(
        id="legacy", name="Legacy", description="d", expected_outcome="o"
    )
    selected = select_agentic_tasks([usage_only, _positive_task()])
    assert [t.id for t in selected] == ["pos-1"]


def test_run_agentic_suite_assembles_shared_suite_shape() -> None:
    # Arrange
    tasks = [_positive_task(), _control_task(), _near_miss_task()]
    client = ScriptedClient(
        [
            ModelTurn(tool_calls=[ModelToolCall(call_id="1", tool_name="plan")]),
            ModelTurn(text=FINAL_TEXT),
            ModelTurn(text=FINAL_TEXT),
            ModelTurn(text=FINAL_TEXT),
        ]
    )
    # Act
    outcome = asyncio.run(run_agentic_suite(tasks, FakeSession(), client))
    # Assert
    assert [t.task_id for t in outcome.suite.tasks] == ["pos-1", "ctl-1", "nm-1"]
    assert [r.passed for r in outcome.summary.results] == [True, True, True]
    assert outcome.summary.scorecard.paired is True
    assert outcome.summary.feedback


def test_run_agentic_suite_records_failure_with_reason() -> None:
    tasks = [_positive_task()]
    client = ScriptedClient([ModelTurn(text=FINAL_TEXT)])
    outcome = asyncio.run(run_agentic_suite(tasks, FakeSession(), client))
    assert outcome.summary.results[0].passed is False
    assert outcome.summary.results[0].reason
    assert outcome.suite.tasks[0].status.value == "mixed"


def test_build_skipped_outcome_marks_every_task_skipped() -> None:
    outcome = build_skipped_outcome(
        [_positive_task()], AgenticSkipReason.DEPENDENCY_MISSING
    )
    assert outcome.summary.skipped is True
    assert outcome.summary.skip_reason is AgenticSkipReason.DEPENDENCY_MISSING
    assert outcome.summary.results[0].skipped is True
    assert outcome.summary.scorecard.selection_accuracy is None


# --- Dependency gating ------------------------------------------------------


def _install_fake_anthropic(
    monkeypatch: pytest.MonkeyPatch, created: list[str]
) -> None:
    """Register a stub `anthropic` module so no real SDK or network is touched."""

    class FakeMessages:
        async def create(self, **kwargs: object) -> object:
            return object()

    class FakeAsyncAnthropic:
        def __init__(self, api_key: str) -> None:
            created.append(api_key)
            self.messages = FakeMessages()

    module = types.ModuleType("anthropic")
    setattr(module, "AsyncAnthropic", FakeAsyncAnthropic)  # noqa: B010
    monkeypatch.setitem(sys.modules, "anthropic", module)


def test_missing_dependency_yields_skip_not_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    def fail_import(name: str) -> object:
        raise ImportError(f"no module named {name}")

    monkeypatch.setattr(importlib, "import_module", fail_import)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    # Act
    resolved = resolve_model_client()
    # Assert
    assert resolved is AgenticSkipReason.DEPENDENCY_MISSING


def test_missing_api_key_yields_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _install_fake_anthropic(monkeypatch, [])
    # Act
    resolved = resolve_model_client()
    # Assert
    assert resolved is AgenticSkipReason.API_KEY_MISSING


def test_resolve_model_client_builds_adapter_with_stubbed_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    created: list[str] = []
    _install_fake_anthropic(monkeypatch, created)
    # Act
    resolved = resolve_model_client(api_key="sk-live")
    # Assert
    assert isinstance(resolved, AnthropicModelClient)
    assert created == ["sk-live"]


def test_select_agentic_tasks_drops_tasks_naming_unexposed_tools() -> None:
    """A tool the model was never shown must not be scored either way."""
    # Arrange
    tasks = [_positive_task(), _control_task(), _near_miss_task()]
    # Act
    selected = select_agentic_tasks(tasks, exposed_tools={"plan"})
    # Assert: near-miss tempts `manage_file`, which is not exposed here.
    assert [t.id for t in selected] == ["pos-1", "ctl-1"]


def test_select_agentic_tasks_keeps_controls_regardless_of_exposure() -> None:
    selected = select_agentic_tasks([_control_task()], exposed_tools=set())
    assert [t.id for t in selected] == ["ctl-1"]


def test_select_agentic_tasks_without_exposure_set_skips_the_check() -> None:
    tasks = [_positive_task(), _near_miss_task()]
    assert len(select_agentic_tasks(tasks)) == 2


def test_run_agentic_suite_excludes_tasks_absent_from_the_session_surface() -> None:
    # Arrange: this session exposes only `plan`, so the near-miss is unscorable.
    tasks = [_positive_task(), _control_task(), _near_miss_task()]
    client = ScriptedClient(
        [
            ModelTurn(tool_calls=[ModelToolCall(call_id="1", tool_name="plan")]),
            ModelTurn(text=FINAL_TEXT),
            ModelTurn(text=FINAL_TEXT),
        ]
    )
    # Act
    outcome = asyncio.run(run_agentic_suite(tasks, FakeSession(["plan"]), client))
    # Assert
    assert [r.task_id for r in outcome.summary.results] == ["pos-1", "ctl-1"]
    assert outcome.summary.scorecard.paired is False
    assert (
        outcome.summary.scorecard.unpaired_reason is UnpairedReason.NO_NEAR_MISS_TASKS
    )
    assert outcome.summary.scorecard.selection_accuracy is None
