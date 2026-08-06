"""Tests for volatile-field relocation on the rules agent-visible surface."""

from __future__ import annotations

import json

from cortex.core.models import ModelDict
from cortex.optimization.models import RulesManagerStatusModel
from cortex.tools.synapse.rules_operation_helpers import (
    VOLATILE_STATUS_FIELDS,
    RulesOperation,
    build_diagnostics_response,
    build_get_relevant_response,
    stable_status_payload,
)


def _status(
    last_indexed: str | None = "2026-08-06T15:57:20.399696",
) -> RulesManagerStatusModel:
    return RulesManagerStatusModel(
        enabled=True,
        rules_folder=".cortex/rules",
        indexed_files=42,
        last_indexed=last_indexed,
        auto_reindex_enabled=False,
        reindex_interval_minutes=60.0,
        total_tokens=1234,
    )


class TestStableStatusPayload:
    """Volatile fields are stripped from the byte-stable surface."""

    def test_last_indexed_is_stripped(self) -> None:
        # Arrange
        status = _status()

        # Act
        payload = stable_status_payload(status)

        # Assert
        assert "last_indexed" not in payload
        assert payload["indexed_files"] == 42

    def test_payload_identical_for_differing_timestamps(self) -> None:
        # Arrange / Act
        first = stable_status_payload(_status("2026-01-01T00:00:00"))
        second = stable_status_payload(_status("2026-12-31T23:59:59"))

        # Assert
        assert first == second

    def test_volatile_field_set_documents_last_indexed(self) -> None:
        # Arrange / Act / Assert
        assert "last_indexed" in VOLATILE_STATUS_FIELDS


class TestGetRelevantResponseStability:
    """The get_relevant body is byte-stable for unchanged rule state."""

    def test_bytes_identical_across_reindex_timestamps(self) -> None:
        # Arrange
        rules: list[ModelDict] = [{"file": "a.mdc", "tokens": 10}]
        context: ModelDict = {
            "context": {"filtered_count": 0},
            "source": "indexed",
        }

        # Act
        first = build_get_relevant_response(
            "task", 5000, 0.5, rules, 10, _status("2026-01-01T00:00:00"), context
        )
        second = build_get_relevant_response(
            "task", 5000, 0.5, rules, 10, _status("2026-12-31T23:59:59"), context
        )

        # Assert
        assert first == second

    def test_keys_are_sorted(self) -> None:
        # Arrange / Act
        body = build_get_relevant_response("task", 1, 0.1, [], 0, _status(), {})
        keys = list(json.loads(body).keys())

        # Assert
        assert keys == sorted(keys)

    def test_mutation_guard_differing_rule_content_changes_bytes(self) -> None:
        """Real content changes must still change the bytes."""
        # Arrange / Act
        first = build_get_relevant_response("task", 1, 0.1, [], 0, _status(), {})
        changed: list[ModelDict] = [{"file": "a.mdc"}]
        second = build_get_relevant_response("task", 1, 0.1, changed, 0, _status(), {})

        # Assert
        assert first != second


class TestDiagnosticsResponse:
    """The relocated volatile value stays reachable explicitly."""

    def test_diagnostics_exposes_last_indexed(self) -> None:
        # Arrange / Act
        parsed = json.loads(build_diagnostics_response(_status()))

        # Assert
        assert parsed["rules_manager_status"]["last_indexed"] == (
            "2026-08-06T15:57:20.399696"
        )
        assert parsed["operation"] == RulesOperation.DIAGNOSTICS.value
        assert parsed["byte_stable"] is False

    def test_diagnostics_is_a_valid_operation(self) -> None:
        # Arrange / Act / Assert
        assert RulesOperation("diagnostics") is RulesOperation.DIAGNOSTICS
