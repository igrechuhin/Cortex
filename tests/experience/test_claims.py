"""Unit tests for the falsifiable claim vocabulary parser."""

from __future__ import annotations

import pytest

from cortex.experience.claims import (
    Claim,
    ClaimKind,
    ClaimSyntaxError,
    is_free_text,
    parse_claims,
)


@pytest.mark.parametrize(
    ("text", "kind", "target"),
    [
        ("gate clean", ClaimKind.GATE_CLEAN, ""),
        ("gate fails type_check", ClaimKind.GATE_FAILS, "type_check"),
        ("error gone ruff@src/a.py", ClaimKind.ERROR_GONE, "ruff@src/a.py"),
        ("test tests/t.py::test_x passes", ClaimKind.TEST_PASSES, "tests/t.py::test_x"),
        ("test tests/t.py::test_x fails", ClaimKind.TEST_FAILS, "tests/t.py::test_x"),
        ("coverage >= 95", ClaimKind.COVERAGE_AT_LEAST, "95"),
        ("coverage >= 92.5%", ClaimKind.COVERAGE_AT_LEAST, "92.5"),
        ("touches src/cortex/a.py", ClaimKind.TOUCHES, "src/cortex/a.py"),
        ("noop src/cortex/a.py", ClaimKind.NOOP_PATH, "src/cortex/a.py"),
        ("change", ClaimKind.CHANGE, ""),
        ("noop", ClaimKind.NOOP, ""),
    ],
)
def test_parse_each_vocabulary_form(text: str, kind: ClaimKind, target: str) -> None:
    # Arrange / Act
    claims = parse_claims(text)

    # Assert
    assert len(claims) == 1
    assert claims[0].kind is kind
    assert claims[0].target == target


def test_coverage_claim_carries_numeric_threshold() -> None:
    # Arrange / Act
    claim = parse_claims("coverage >= 92.5")[0]

    # Assert
    assert claim.threshold == 92.5


def test_compound_claims_split_on_semicolons() -> None:
    # Arrange
    text = "gate clean ; touches src/a.py;  coverage >= 90 "

    # Act
    claims = parse_claims(text)

    # Assert
    assert [c.kind for c in claims] == [
        ClaimKind.GATE_CLEAN,
        ClaimKind.TOUCHES,
        ClaimKind.COVERAGE_AT_LEAST,
    ]


def test_case_and_whitespace_tolerance() -> None:
    # Arrange / Act
    claims = parse_claims("  GATE   CLEAN  ")

    # Assert
    assert claims[0].kind is ClaimKind.GATE_CLEAN


def test_path_case_is_preserved() -> None:
    # Arrange / Act
    claim = parse_claims("touches src/Cortex/MyFile.py")[0]

    # Assert
    assert claim.target == "src/Cortex/MyFile.py"


@pytest.mark.parametrize("text", ["", "   ", ";;", None])
def test_empty_prediction_is_rejected(text: str | None) -> None:
    # Arrange / Act / Assert
    with pytest.raises(ClaimSyntaxError, match="empty prediction predicts nothing"):
        _ = parse_claims(text)


@pytest.mark.parametrize(
    "text",
    ["gate sparkling", "coverage > 90", "test only-a-nodeid", "touches"],
)
def test_malformed_keyword_claim_is_rejected(text: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(ClaimSyntaxError, match="Malformed claim"):
        _ = parse_claims(text)


def test_free_text_becomes_implied_change() -> None:
    # Arrange / Act
    claim = parse_claims("the retry loop will stop double-counting")[0]

    # Assert
    assert claim.kind is ClaimKind.CHANGE
    assert is_free_text(claim)


def test_literal_change_is_not_free_text() -> None:
    # Arrange / Act
    claim = parse_claims("change")[0]

    # Assert
    assert not is_free_text(claim)


def test_claim_round_trips_through_json() -> None:
    # Arrange
    claim = parse_claims("coverage >= 90")[0]

    # Act
    restored = Claim.model_validate(claim.model_dump(mode="json"))

    # Assert
    assert restored == claim
