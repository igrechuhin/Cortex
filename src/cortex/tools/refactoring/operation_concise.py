"""Concise response formatting for refactoring operations.

Extracted from operation_helpers to keep the main module under 400 lines.
"""

from typing import cast

from cortex.core.models import JsonDict, JsonValue, ResponseFormat

from .result_models import (
    ConciseRefactoringSuggestionEntry,
    SuggestRefactoringConcisePayload,
)


def _str_or_none(v: JsonValue) -> str | None:
    """Coerce JSON value to str or None for suggestion entry fields."""
    if v is None:
        return None
    return str(v)


def _parse_suggest_refactoring_json(raw: str) -> JsonDict | None:
    """Parse raw JSON string into a dict or return None on failure."""
    import json

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    return cast(JsonDict, loaded)


def _build_consolidation_suggestions(
    data: JsonDict,
) -> list[ConciseRefactoringSuggestionEntry]:
    """Build concise entries for consolidation suggestions."""
    suggestions: list[ConciseRefactoringSuggestionEntry] = []
    opportunities_raw: object = data.get("opportunities") or []
    if not isinstance(opportunities_raw, list):
        return suggestions
    for opp_obj in cast(list[object], opportunities_raw):
        if not isinstance(opp_obj, dict):
            continue
        opp = cast(JsonDict, opp_obj)
        suggestions.append(
            ConciseRefactoringSuggestionEntry(
                id=_str_or_none(opp.get("id")),
                type="consolidation",
                confidence=_str_or_none(opp.get("confidence")),
                recommendation=_str_or_none(opp.get("recommendation")),
            )
        )
    return suggestions


def _build_splits_suggestions(
    data: JsonDict,
) -> list[ConciseRefactoringSuggestionEntry]:
    """Build concise entries for split recommendations."""
    suggestions: list[ConciseRefactoringSuggestionEntry] = []
    recommendations_raw: object = data.get("recommendations") or []
    if not isinstance(recommendations_raw, list):
        return suggestions
    for rec_obj in cast(list[object], recommendations_raw):
        if not isinstance(rec_obj, dict):
            continue
        rec = cast(JsonDict, rec_obj)
        suggestions.append(
            ConciseRefactoringSuggestionEntry(
                id=_str_or_none(rec.get("id")),
                type="splits",
                confidence=_str_or_none(rec.get("confidence")),
                recommendation=_str_or_none(rec.get("reason")),
            )
        )
    return suggestions


def _build_reorg_suggestions(
    data: JsonDict,
) -> list[ConciseRefactoringSuggestionEntry]:
    """Build concise entry for reorganization plan."""
    goal_raw = data.get("goal")
    goal_val: str | None = goal_raw if isinstance(goal_raw, str) else None
    goal = goal_val
    recommendation = (
        f"Reorganization plan optimized for goal='{goal}'"
        if goal is not None
        else "Reorganization plan"
    )
    return [
        ConciseRefactoringSuggestionEntry(
            id="reorganization-plan",
            type="reorganization",
            confidence=None,
            recommendation=recommendation,
        )
    ]


def _build_concise_suggestions(
    data: JsonDict,
) -> tuple[list[ConciseRefactoringSuggestionEntry], str | None]:
    """Dispatch to type-specific concise suggestion builders."""
    type_raw_val = data.get("type")
    type_raw: str | None = type_raw_val if isinstance(type_raw_val, str) else None
    if type_raw == "consolidation":
        return _build_consolidation_suggestions(data), type_raw
    if type_raw == "splits":
        return _build_splits_suggestions(data), type_raw
    if type_raw == "reorganization":
        return _build_reorg_suggestions(data), type_raw
    return [], type_raw


def format_suggest_refactoring_response(
    raw: str,
    response_format: ResponseFormat,
) -> str:
    """Format suggest_refactoring response based on response_format."""
    if response_format != ResponseFormat.CONCISE:
        return raw

    data = _parse_suggest_refactoring_json(raw)
    if data is None:
        return raw

    status_raw = data.get("status")
    status_val: str = status_raw if isinstance(status_raw, str) else "success"
    status = status_val
    if status != "success":
        return raw

    suggestions, type_raw = _build_concise_suggestions(data)
    if not suggestions:
        return raw

    type_str = str(type_raw) if type_raw is not None else None
    payload = SuggestRefactoringConcisePayload(
        status=status,
        type=type_str,
        suggestions=suggestions,
    )
    return payload.model_dump_json(indent=2)
