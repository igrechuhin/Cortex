"""Budget the serialized context resource, never truncating required instructions."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import cast

from cortex.core.token_counter import TokenCounter

_OPTIONAL_GROUPS = (
    ("plan_graph_ascii_edges",),
    (
        "plan_graph_ready",
        "plan_graph_blocked",
        "plan_graph_ambiguous",
        "plan_graph_details",
    ),
    ("explore_summary",),
    ("recent_artifacts",),
    ("recent_ingested_sources",),
    ("recent_operations",),
)
# AI: envelope and enforcer-written metadata -- not context content. Excluded
# from the per-component breakdown so `token_accounting` and the
# `required_components` error list describe actual context, instead of naming
# the enforcer's own bookkeeping as something the operator must shrink. Their
# tokens still land in `serialization_and_metadata`, so the total stays exact.
_ACCOUNTING_KEYS = {
    "total_tokens",
    "token_budget",
    "token_accounting",
    "utilization",
    "budget_stage",
    "omitted_components",
    "status",
}


@lru_cache(maxsize=1)
def context_token_counter() -> TokenCounter:
    """Reuse the standard tokenizer across resource cache misses."""
    return TokenCounter()


def invalid_context_budget(budget: object) -> str | None:
    """Reject malformed explicit budgets rather than silently using the default."""
    if isinstance(budget, int) and not isinstance(budget, bool) and budget > 0:
        return None
    return json.dumps(
        {
            "status": "error",
            "error": "invalid_token_budget",
            "message": "Context token_budget must be a positive integer.",
        },
        indent=2,
        sort_keys=True,
    )


def _serialize(payload: dict[str, object]) -> str:
    fields: list[str] = []
    for key, value in sorted(payload.items()):
        # AI: Fixed decimal width keeps numeric utilization from oscillating token counts.
        encoded = (
            f"{value:.4f}"
            if key == "utilization" and isinstance(value, float)
            else json.dumps(value, indent=2, sort_keys=True)
        )
        fields.append(f"  {json.dumps(key)}: " + encoded.replace("\n", "\n  "))
    return "{\n" + ",\n".join(fields) + "\n}"


def _account(payload: dict[str, object], budget: int, counter: TokenCounter) -> str:
    """Attribute value tokens plus the exact remaining JSON/metadata overhead."""
    components = {
        key: counter.count_tokens(json.dumps(value, indent=2, sort_keys=True))
        for key, value in sorted(payload.items())
        if key not in _ACCOUNTING_KEYS
    }
    content_tokens = sum(components.values())
    payload.update(token_budget=budget, total_tokens=content_tokens)
    for _ in range(32):
        total = cast(int, payload["total_tokens"])
        payload["token_accounting"] = {
            **components,
            "serialization_and_metadata": total - content_tokens,
        }
        payload["utilization"] = total / budget
        serialized = _serialize(payload)
        measured = counter.count_tokens(serialized)
        if measured == total:
            return serialized
        payload["total_tokens"] = measured
    raise ValueError("Context token accounting did not converge")


def _required_payload(
    payload: dict[str, object], essential_layered: str, essential_names: list[str]
) -> tuple[dict[str, object], list[dict[str, object]]]:
    required = dict(payload)
    optional: list[dict[str, object]] = []
    if payload.get("layered_context") != essential_layered:
        optional.append(
            {key: required[key] for key in ("layered_context", "context_layers_loaded")}
        )
    required.update(
        layered_context=essential_layered, context_layers_loaded=essential_names
    )
    for group in _OPTIONAL_GROUPS:
        values = {key: required.pop(key) for key in group if key in required}
        if values:
            optional.append(values)
    return required, optional


def _omission_names(group: dict[str, object]) -> list[str]:
    return ["optional_layers"] if "layered_context" in group else list(group)


def _insufficient_budget(required: dict[str, object], budget: int) -> str:
    return _serialize(
        {
            "status": "error",
            "error": "insufficient_token_budget",
            "message": "Required governance and essential context exceed token_budget; increase the budget. Required content was not silently truncated.",
            "token_budget": budget,
            "required_tokens": required["total_tokens"],
            "required_components": sorted(
                key for key in required if key not in _ACCOUNTING_KEYS
            ),
            "budget_stage": "insufficient",
        }
    )


def _allocate_optional(
    required: dict[str, object],
    optional: list[dict[str, object]],
    budget: int,
    counter: TokenCounter,
) -> str:
    omitted = [name for group in optional for name in _omission_names(group)]
    required["omitted_components"] = omitted
    required["budget_stage"] = "full" if not omitted else "optional_omitted"
    result = _account(required, budget, counter)
    if cast(int, required["total_tokens"]) > budget:
        return _insufficient_budget(required, budget)
    for group in optional:
        remaining = [key for key in omitted if key not in _omission_names(group)]
        candidate = {
            **required,
            **group,
            "omitted_components": remaining,
            "budget_stage": "full" if not remaining else "optional_omitted",
        }
        serialized = _account(candidate, budget, counter)
        if cast(int, candidate["total_tokens"]) <= budget:
            required, omitted, result = candidate, remaining, serialized
    return result


def enforce_context_budget(
    serialized: str,
    budget: int,
    essential_layered: str,
    essential_names: list[str],
    counter: TokenCounter,
) -> str:
    """Keep mandatory fields intact; include optional groups only when they fit."""
    invalid = invalid_context_budget(budget)
    if invalid is not None:
        return invalid
    payload: object = json.loads(serialized)
    if not isinstance(payload, dict):
        return serialized
    if cast(dict[str, object], payload).get("status") != "success":
        return serialized
    required, optional = _required_payload(
        cast(dict[str, object], payload), essential_layered, essential_names
    )
    try:
        return _allocate_optional(required, optional, budget, counter)
    except ValueError as exc:
        # AI: an accounting failure is still a ladder outcome. Reporting no
        # stage here would leave the caller unable to tell a convergence
        # failure apart from a rung that was never attempted.
        return _serialize(
            {
                "status": "error",
                "error": "token_accounting_failed",
                "message": str(exc),
                "budget_stage": "accounting_failed",
            }
        )
