"""Full-response budgeting regressions using the real serialized tokenizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from tiktoken.registry import get_encoding

from cortex.core.token_counter import TokenCounter
from cortex.tools.optimization import handlers
from cortex.tools.optimization.context_budget import enforce_context_budget


@pytest.fixture
def counter() -> TokenCounter:
    tokens = TokenCounter()
    tokens.encoding_impl = get_encoding("cl100k_base")
    return tokens


def _payload() -> dict[str, object]:
    return {
        "status": "success",
        "total_tokens": 1,
        "immutable_governance": {"content": "Never discard governance."},
        "session_scope": "Work within the requested scope.",
        "scoped_context": {"filtered_rules": "Preserve all selected rules."},
        "layered_context": "Identity and essential context.",
        "context_layers_loaded": ["L0", "L1"],
    }


def _budget(payload: dict[str, object], budget: int, counter: TokenCounter) -> str:
    return enforce_context_budget(
        json.dumps(payload),
        budget,
        "Identity and essential context.",
        ["L0", "L1"],
        counter,
    )


def _assert_accounted(serialized: str, budget: int, counter: TokenCounter) -> None:
    data = json.loads(serialized)
    assert data["status"] == "success"
    assert data["total_tokens"] == counter.count_tokens(serialized) <= budget
    assert sum(data["token_accounting"].values()) == data["total_tokens"]
    assert all(value >= 0 for value in data["token_accounting"].values())
    assert data["utilization"] == round(data["total_tokens"] / budget, 4)


def test_budget_stage_names_which_rung_the_ladder_reached(
    counter: TokenCounter,
) -> None:
    # Arrange: the same payload under three budgets exercises all three rungs.
    # Reporting only `utilization` left a caller unable to tell "everything
    # fit" from "optional content was silently dropped to make it fit".
    payload = _payload()
    payload["recent_operations"] = "Large history entry. " * 3000

    # Act
    roomy = _budget(payload, 20000, counter)
    squeezed = _budget(payload, 700, counter)
    starved = _budget(payload, 1, counter)

    # Assert
    assert json.loads(roomy)["budget_stage"] == "full"
    assert json.loads(squeezed)["budget_stage"] == "optional_omitted"
    assert json.loads(starved)["budget_stage"] == "insufficient"
    # The stage field is ordinary content, so it must stay inside the
    # converged accounting rather than riding along untracked.
    _assert_accounted(roomy, 20000, counter)
    _assert_accounted(squeezed, 700, counter)


def test_optional_history_does_not_displace_mandatory_content(
    counter: TokenCounter,
) -> None:
    payload = _payload()
    payload["recent_operations"] = "Large history entry. " * 3000
    serialized = _budget(payload, 700, counter)
    data = json.loads(serialized)
    _assert_accounted(serialized, 700, counter)
    for key in (
        "immutable_governance",
        "session_scope",
        "scoped_context",
        "layered_context",
    ):
        assert data[key] == payload[key]
    assert "recent_operations" not in data
    assert "recent_operations" in data["omitted_components"]


def test_oversized_governance_reports_required_budget(counter: TokenCounter) -> None:
    payload = _payload()
    payload["immutable_governance"] = {"content": "Mandatory instruction. " * 2000}
    data = json.loads(_budget(payload, 700, counter))
    assert data["status"] == "error"
    assert data["error"] == "insufficient_token_budget"
    assert data["required_tokens"] > 700
    assert "immutable_governance" in data["required_components"]


def test_small_budget_is_explicitly_insufficient(counter: TokenCounter) -> None:
    data = json.loads(_budget(_payload(), 1, counter))
    assert data["error"] == "insufficient_token_budget"
    assert data["required_tokens"] > 1


def test_optional_layers_do_not_truncate_essential_layers(
    counter: TokenCounter,
) -> None:
    payload = _payload()
    payload.update(
        layered_context="Large optional search. " * 3000,
        context_layers_loaded=["L0", "L1", "L3"],
    )
    serialized = _budget(payload, 700, counter)
    data = json.loads(serialized)
    _assert_accounted(serialized, 700, counter)
    assert data["layered_context"] == "Identity and essential context."
    assert data["context_layers_loaded"] == ["L0", "L1"]
    assert "optional_layers" in data["omitted_components"]


def test_graph_previews_are_optional_but_totals_remain(counter: TokenCounter) -> None:
    payload = _payload()
    payload.update(
        plan_graph_summary="Plans: 500 ready, 200 blocked.",
        plan_graph_ascii_edges="source --> destination\n" * 2000,
        plan_graph_ready=["plan-" + str(index) for index in range(500)],
        plan_graph_blocked={"blocked": ["dependency"] * 2000},
        plan_graph_ambiguous={},
        plan_graph_details={"limit": 10},
    )
    serialized = _budget(payload, 700, counter)
    data = json.loads(serialized)
    _assert_accounted(serialized, 700, counter)
    assert data["plan_graph_summary"] == payload["plan_graph_summary"]
    assert "plan_graph_ready" not in data
    assert "plan_graph_details" not in data
    assert "plan_graph_ascii_edges" in data["omitted_components"]


@pytest.mark.parametrize("optional", [None, "", "Brief useful history."])
def test_fitting_optional_sections_and_empty_sections_are_stable(
    counter: TokenCounter,
    optional: str | None,
) -> None:
    payload = _payload()
    if optional is not None:
        payload["recent_operations"] = optional
    serialized = _budget(payload, 2000, counter)
    _assert_accounted(serialized, 2000, counter)
    assert serialized == _budget(payload, 2000, counter)
    assert json.loads(serialized).get("recent_operations") == optional


@pytest.mark.asyncio
@pytest.mark.parametrize("budget", [0, -1, True, 1.5, "1000", None])
async def test_resource_rejects_invalid_configured_budgets(
    monkeypatch: pytest.MonkeyPatch,
    budget: object,
) -> None:
    monkeypatch.setattr(
        "cortex.core.session_config.read_session_config",
        lambda: {"token_budget": budget},
    )
    data = json.loads(await handlers.load_context())
    assert data["status"] == "error"
    assert data["error"] == "invalid_token_budget"


@pytest.mark.asyncio
async def test_resource_cache_preserves_accounted_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    counter: TokenCounter,
) -> None:
    calls: list[str] = []

    async def base(**_: object) -> str:
        calls.append("load")
        return json.dumps(_payload())

    async def append(payload: str, _: Path) -> str:
        return payload

    async def root(_: object, __: object) -> Path:
        return tmp_path

    monkeypatch.setattr(
        "cortex.core.session_config.read_session_config", lambda: {"token_budget": 2000}
    )
    monkeypatch.setattr(handlers, "load_context_impl", base)
    monkeypatch.setattr(handlers, "build_context_resource_payload_async", append)
    monkeypatch.setattr(handlers, "resolve_project_root_async", root)
    monkeypatch.setattr(handlers, "context_token_counter", lambda: counter)
    handlers.invalidate_context_resource_cache()
    first, second = await handlers.load_context(), await handlers.load_context()
    assert first == second
    assert calls == ["load"]
    _assert_accounted(first, 2000, counter)
    assert (
        cast(dict[str, object], json.loads(first))["immutable_governance"]
        == _payload()["immutable_governance"]
    )
    handlers.invalidate_context_resource_cache()
