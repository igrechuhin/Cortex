"""Trigger-accuracy benchmark and scorer tests for skill pack discovery.

Plan: skill-pack-trigger-accuracy-benchmark-and-description-tuning.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cortex.tools.skill_pack.benchmark import (
    MISSING_NEGATIVES_REASON,
    NO_PACK_NEEDED,
    FixtureSet,
    TriggerFixture,
    format_report,
    run_benchmark,
)
from cortex.tools.skill_pack.models import SkillPackManifest
from cortex.tools.skill_pack.operations import (
    NO_MATCH_REASON,
    discover_packs,
    load_shipped_manifests,
    skill_pack,
)
from cortex.tools.skill_pack.scoring import describe_match, rank_packs, score_pack

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "skill_pack_trigger"
    / "fixtures.json"
)

# AI: Recorded post-tuning figures. A regression below these bounds means a
# manifest or scorer edit degraded discovery and must be reverted.
BASELINE_TOP1 = 0.9167
BASELINE_NEAR_MISS_FP = 0.2857


@pytest.fixture
def fixture_set() -> FixtureSet:
    """Load the committed labeled fixture set."""
    return FixtureSet.model_validate_json(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def manifests() -> list[SkillPackManifest]:
    """Load the shipped skill pack manifests."""
    return load_shipped_manifests()


def _manifest(name: str, **kwargs: object) -> SkillPackManifest:
    """Build a minimal manifest for scorer unit tests."""
    return SkillPackManifest.model_validate(
        {"name": name, "description": f"{name} pack", **kwargs}
    )


# --- fixture set validation -------------------------------------------------


def test_every_pack_has_a_positive_fixture(
    fixture_set: FixtureSet, manifests: list[SkillPackManifest]
) -> None:
    """Every shipped manifest is the expected answer of at least one positive."""
    # Arrange
    covered = {f.expected_pack for f in fixture_set.of_kind("positive")}
    # Act
    missing = sorted({m.name for m in manifests} - covered)
    # Assert
    assert missing == []


def test_fixture_set_has_required_negative_counts(fixture_set: FixtureSet) -> None:
    """At least five controls and five near-misses are present."""
    # Arrange / Act
    controls = fixture_set.of_kind("control")
    near = fixture_set.of_kind("near-miss")
    # Assert
    assert len(controls) >= 5
    assert len(near) >= 5


def test_duplicate_fixture_ids_rejected() -> None:
    """A repeated fixture id is rejected so per-fixture history stays intact."""
    # Arrange
    raw = {
        "fixtures": [
            {"id": "dup", "kind": "control", "task": "a"},
            {"id": "dup", "kind": "control", "task": "b"},
        ]
    }
    # Act / Assert
    with pytest.raises(ValidationError, match="Duplicate fixture ids"):
        _ = FixtureSet.model_validate(raw)


def test_near_miss_without_covered_by_rejected() -> None:
    """A near-miss must name what actually covers the task."""
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="requires expected_pack and covered_by"):
        _ = TriggerFixture.model_validate(
            {"id": "x", "kind": "near-miss", "task": "t", "expected_pack": "core"}
        )


def test_control_with_expected_pack_rejected() -> None:
    """A control fixture may not carry an expected_pack or covered_by."""
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="must not set expected_pack"):
        _ = TriggerFixture.model_validate(
            {"id": "x", "kind": "control", "task": "t", "expected_pack": "core"}
        )


def test_positive_without_expected_pack_rejected() -> None:
    """A positive fixture must name the pack it expects."""
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="requires expected_pack"):
        _ = TriggerFixture.model_validate({"id": "x", "kind": "positive", "task": "t"})


def test_unknown_kind_rejected() -> None:
    """An unrecognised kind is rejected rather than silently defaulted."""
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        _ = TriggerFixture.model_validate({"id": "x", "kind": "gap", "task": "t"})


# --- pairing enforcement ----------------------------------------------------


def test_missing_near_miss_yields_no_accuracy(
    fixture_set: FixtureSet, manifests: list[SkillPackManifest]
) -> None:
    """Dropping every near-miss withholds all accuracy figures."""
    # Arrange
    trimmed = FixtureSet(
        fixtures=[f for f in fixture_set.fixtures if f.kind != "near-miss"]
    )
    # Act
    result = run_benchmark(trimmed, manifests)
    # Assert
    assert result.valid is False
    assert result.reason == MISSING_NEGATIVES_REASON
    assert result.top1_accuracy is None
    assert result.near_miss_false_positive_rate is None


def test_missing_control_yields_no_accuracy(
    fixture_set: FixtureSet, manifests: list[SkillPackManifest]
) -> None:
    """Dropping every control withholds all accuracy figures."""
    # Arrange
    trimmed = FixtureSet(
        fixtures=[f for f in fixture_set.fixtures if f.kind != "control"]
    )
    # Act
    result = run_benchmark(trimmed, manifests)
    # Assert
    assert result.valid is False
    assert result.top1_accuracy is None


def test_complete_set_reports_separate_false_positive_rates(
    fixture_set: FixtureSet, manifests: list[SkillPackManifest]
) -> None:
    """A complete set yields accuracy plus both rates as distinct fields."""
    # Arrange / Act
    result = run_benchmark(fixture_set, manifests)
    # Assert
    assert result.valid is True
    assert result.top1_accuracy is not None
    assert result.control_false_positive_rate is not None
    assert result.near_miss_false_positive_rate is not None


# --- benchmark behaviour ----------------------------------------------------


def test_benchmark_is_deterministic(
    fixture_set: FixtureSet, manifests: list[SkillPackManifest]
) -> None:
    """Two runs over the same inputs produce byte-identical reports."""
    # Arrange / Act
    first = format_report(run_benchmark(fixture_set, manifests))
    second = format_report(run_benchmark(fixture_set, manifests))
    # Assert
    assert first == second


def test_benchmark_meets_recorded_targets(
    fixture_set: FixtureSet, manifests: list[SkillPackManifest]
) -> None:
    """Post-tuning figures beat the recorded baseline and never regress."""
    # Arrange / Act
    result = run_benchmark(fixture_set, manifests)
    # Assert
    assert result.top1_accuracy == 1.0
    assert result.recall == 1.0
    assert result.control_false_positive_rate == 0.0
    assert result.near_miss_false_positive_rate is not None
    assert result.near_miss_false_positive_rate <= BASELINE_NEAR_MISS_FP
    assert result.top1_accuracy is not None and result.top1_accuracy > BASELINE_TOP1


def test_benchmark_subset_matches_hand_computed_metrics(
    manifests: list[SkillPackManifest],
) -> None:
    """A small fixed subset reports hand-computed metrics."""
    # Arrange
    subset = FixtureSet(
        fixtures=[
            TriggerFixture(
                id="s-pos",
                kind="positive",
                task="Run the pre-commit quality gate and autofix lint errors",
                expected_pack="quality",
            ),
            TriggerFixture(
                id="s-ctl", kind="control", task="Rename tmp2 to buffer_length"
            ),
            TriggerFixture(
                id="s-nm",
                kind="near-miss",
                task="One lint error on line 40; delete the unused import",
                expected_pack="quality",
                covered_by=NO_PACK_NEEDED,
            ),
        ]
    )
    # Act
    result = run_benchmark(subset, manifests)
    # Assert
    assert result.top1_accuracy == 1.0
    assert result.control_false_positive_rate == 0.0
    assert result.near_miss_false_positive_rate == 0.0
    assert result.precision == 1.0
    assert result.misclassified == []


def test_invariance_to_unrelated_pack(
    fixture_set: FixtureSet, manifests: list[SkillPackManifest]
) -> None:
    """Adding a pack with an unrelated subject leaves every per-id result unchanged."""
    # Arrange
    before = run_benchmark(fixture_set, manifests)
    extra = _manifest(
        "hydroponics",
        when_to_use="When adjusting nutrient film irrigation schedules.",
        keywords=["hydroponics", "nutrient film", "irrigation"],
    )
    # Act
    after = run_benchmark(fixture_set, [*manifests, extra])
    # Assert
    assert after.outcomes == before.outcomes
    assert after.top1_accuracy == before.top1_accuracy


def test_invariance_to_workflow_edit(
    fixture_set: FixtureSet, manifests: list[SkillPackManifest]
) -> None:
    """Editing a pack's workflow without touching its wording keeps figures flat."""
    # Arrange
    before = run_benchmark(fixture_set, manifests)
    edited = [
        m.model_copy(update={"workflow_sequences": [*m.workflow_sequences, "extra"]})
        for m in manifests
    ]
    # Act
    after = run_benchmark(fixture_set, edited)
    # Assert
    assert after.model_dump() == before.model_dump()


# --- scorer -----------------------------------------------------------------


def test_name_match_outranks_keyword_only_match() -> None:
    """A pack-name hit scores above a single keyword hit."""
    # Arrange
    named = _manifest("telemetry")
    keyworded = _manifest("other", keywords=["telemetry"])
    # Act
    named_score = score_pack(named, "investigate telemetry gaps").score
    keyword_score = score_pack(keyworded, "investigate telemetry gaps").score
    # Assert
    assert named_score > keyword_score


def test_verbose_manifest_does_not_outrank_closer_pack() -> None:
    """Keyword contribution is capped so verbosity alone cannot win."""
    # Arrange
    verbose = _manifest(
        "verbose",
        keywords=["fix", "error", "line", "code", "file", "test", "run"],
    )
    close = _manifest("telemetry", keywords=["telemetry"])
    task = (
        "fix the error on this line of code in the file and run the test for telemetry"
    )
    # Act
    ranked = rank_packs([verbose, close], task, limit=5)
    # Assert
    assert ranked[0].name == "telemetry"


@pytest.mark.parametrize(
    "task", ["when the build is red", "we are collecting runtime numbers now"]
)
def test_when_to_use_text_alone_does_not_score(task: str) -> None:
    """Scoring reads name, description and keywords only -- never when_to_use."""
    # Arrange
    pack = _manifest("telemetry", when_to_use="When collecting runtime metrics.")
    # Act
    result = score_pack(pack, task)
    # Assert
    assert result.score == 0


@pytest.mark.parametrize("task", ["", "   ", "\n\t "])
def test_blank_task_scores_zero(task: str) -> None:
    """Empty and whitespace-only descriptions are handled without a crash."""
    # Arrange
    pack = _manifest("telemetry", keywords=["telemetry"])
    # Act / Assert
    assert score_pack(pack, task).score == 0


def test_task_matching_every_pack_is_handled(
    manifests: list[SkillPackManifest],
) -> None:
    """A description hitting every pack returns a bounded, ordered list."""
    # Arrange
    task = " ".join(m.name for m in manifests)
    # Act
    ranked = rank_packs(manifests, task, limit=5)
    # Assert
    assert len(ranked) == 5
    assert [s.score for s in ranked] == sorted((s.score for s in ranked), reverse=True)


# --- reason strings and discover result -------------------------------------


def test_reason_distinguishes_strong_weak_and_absent() -> None:
    """Positive, weak, and no-match each produce a distinct accurate reason."""
    # Arrange
    pack = _manifest("telemetry", keywords=["metrics", "traces"])
    # Act
    strong = describe_match(score_pack(pack, "telemetry work"))
    weak = describe_match(score_pack(pack, "check metrics and traces"))
    absent = describe_match(score_pack(pack, "unrelated"))
    # Assert
    assert strong.startswith("Strong match on pack name 'telemetry'")
    assert weak.startswith("Weak match on keywords: metrics, traces")
    assert absent.startswith("No match")


def test_load_shipped_manifests_returns_every_pack() -> None:
    """The public manifest accessor exposes all shipped packs."""
    # Arrange / Act
    names = {m.name for m in load_shipped_manifests()}
    # Assert
    assert {"core", "quality", "refactoring"} <= names


def test_discover_packs_returns_empty_on_no_match() -> None:
    """A task matching no pack yields no recommendation at all."""
    # Arrange / Act
    ranked = discover_packs("Rename the variable tmp2 to buffer_length", limit=5)
    # Assert
    assert ranked == []


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_discover_no_match_reports_explicit_reason() -> None:
    """The arbitrary-pack fallback is gone; a clear reason replaces it."""
    # Arrange / Act
    raw = await skill_pack(
        operation="discover",
        task_description="Rename the variable tmp2 to buffer_length",
    )
    data = json.loads(raw)
    # Assert
    assert data["count"] == 0
    assert data["packs"] == []
    assert data["reason"] == NO_MATCH_REASON


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_discover_exposes_score_and_honest_reason() -> None:
    """Each recommendation carries its numeric score and a signal-specific reason."""
    # Arrange / Act
    raw = await skill_pack(
        operation="discover",
        task_description="Run the pre-commit quality gate and autofix lint errors",
    )
    data = json.loads(raw)
    # Assert
    top = data["packs"][0]
    assert top["name"] == "quality"
    assert top["score"] >= 2
    assert "Default recommendation" not in top["reason"]
    assert top["reason"].startswith(("Strong match on", "Weak match on"))
