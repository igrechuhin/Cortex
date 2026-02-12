import json

from cortex.tools.refactoring_operations import format_suggest_refactoring_response


def test_format_suggest_refactoring_response_consolidation_concise() -> None:
    raw = json.dumps(
        {
            "status": "success",
            "type": "consolidation",
            "opportunities": [
                {
                    "id": "c1",
                    "files": ["a.md", "b.md"],
                    "similarity": 0.9,
                    "shared_content_tokens": 100,
                    "potential_savings_tokens": 80,
                    "recommendation": "Extract shared section.",
                    "suggested_transclusion": "{{include:shared.md}}",
                    "confidence": "high",
                }
            ],
        }
    )

    out = format_suggest_refactoring_response(raw, response_format="concise")
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["type"] == "consolidation"
    assert data["suggestions"][0]["id"] == "c1"
    assert data["suggestions"][0]["type"] == "consolidation"
    assert data["suggestions"][0]["confidence"] == "high"
    assert "recommendation" in data["suggestions"][0]


def test_format_suggest_refactoring_response_detailed_passthrough() -> None:
    """When response_format='detailed', payload should be unchanged."""
    original = json.dumps({"status": "success", "type": "consolidation"})
    out = format_suggest_refactoring_response(original, response_format="detailed")
    assert out == original


def test_format_suggest_refactoring_response_invalid_json_returns_raw() -> None:
    """Invalid JSON payload should be returned unchanged in concise mode."""
    original = "not-json-at-all"

    out = format_suggest_refactoring_response(original, response_format="concise")

    assert out == original


def test_format_suggest_refactoring_response_error_status_passthrough() -> None:
    """Error payloads should be preserved even in concise mode."""
    original = json.dumps(
        {
            "status": "error",
            "error": "Something went wrong",
            "error_type": "RuntimeError",
        }
    )

    out = format_suggest_refactoring_response(original, response_format="concise")

    assert out == original


def test_format_suggest_refactoring_response_reorganization_concise() -> None:
    """Reorganization responses should produce a concise single-plan suggestion."""
    raw = json.dumps(
        {
            "status": "success",
            "type": "reorganization",
            "goal": "dependency_depth",
            "plan": {"current_state": {}, "proposed_state": {}},
        }
    )

    out = format_suggest_refactoring_response(raw, response_format="concise")
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["type"] == "reorganization"
    assert len(data["suggestions"]) == 1
    suggestion = data["suggestions"][0]
    assert suggestion["id"] == "reorganization-plan"
    assert suggestion["type"] == "reorganization"
    # Recommendation text should reflect the goal string
    assert "dependency_depth" in suggestion["recommendation"]


def test_format_suggest_refactoring_response_splits_concise() -> None:
    """Split recommendations should map reason into recommendation field."""
    raw = json.dumps(
        {
            "status": "success",
            "type": "splits",
            "recommendations": [
                {
                    "id": "split-1",
                    "file": "big.md",
                    "reason": "File too large",
                    "confidence": "medium",
                }
            ],
        }
    )

    out = format_suggest_refactoring_response(raw, response_format="concise")
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["type"] == "splits"
    assert len(data["suggestions"]) == 1
    suggestion = data["suggestions"][0]
    assert suggestion["id"] == "split-1"
    assert suggestion["type"] == "splits"
    assert suggestion["confidence"] == "medium"
    assert suggestion["recommendation"] == "File too large"


def test_format_suggest_refactoring_response_unknown_type_returns_raw() -> None:
    """Unknown result type should not be transformed."""
    original = json.dumps(
        {
            "status": "success",
            "type": "custom-type",
            "payload": {"foo": "bar"},
        }
    )

    out = format_suggest_refactoring_response(original, response_format="concise")

    assert out == original


def test_format_suggest_refactoring_response_reorganization_without_goal() -> None:
    """Reorganization responses without goal should use a generic recommendation."""
    raw = json.dumps(
        {
            "status": "success",
            "type": "reorganization",
            "plan": {"current_state": {}, "proposed_state": {}},
        }
    )

    out = format_suggest_refactoring_response(raw, response_format="concise")
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["type"] == "reorganization"
    assert len(data["suggestions"]) == 1
    suggestion = data["suggestions"][0]
    assert suggestion["id"] == "reorganization-plan"
    assert suggestion["type"] == "reorganization"
    assert suggestion["recommendation"] == "Reorganization plan"


def test_format_suggest_refactoring_response_consolidation_with_non_list_opportunities_returns_raw() -> (
    None
):
    """If opportunities is not a list, the payload should be returned unchanged."""
    original = json.dumps(
        {
            "status": "success",
            "type": "consolidation",
            "opportunities": {"id": "c1"},
        }
    )

    out = format_suggest_refactoring_response(original, response_format="concise")

    assert out == original
