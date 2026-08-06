"""Trigger-accuracy benchmark for skill pack discovery.

Runs a labeled fixture set through the discovery scorer and reports top-1
accuracy, recall and precision **always paired** with separately reported
``control`` and ``near-miss`` false-positive rates. A run missing either negative
kind emits no accuracy figure at all — that pairing rule is what prevents manifest
tuning from becoming a description-inflation ratchet
(plan: skill-pack-trigger-accuracy-benchmark-and-description-tuning).
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cortex.tools.skill_pack.models import SkillPackManifest
from cortex.tools.skill_pack.scoring import PackScore, rank_packs

FixtureKind = Literal["positive", "control", "near-miss"]

# AI: Explicit marker for "no pack needed; direct tool use covers this task".
NO_PACK_NEEDED = "no-pack-needed"

MISSING_NEGATIVES_REASON = (
    "Fixture set must contain at least one 'control' and one 'near-miss' fixture; "
    "accuracy without paired false-positive rates is not a valid result"
)


class TriggerFixture(BaseModel):
    """One labeled discovery case: a task description and its correct outcome."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Permanent kebab-case fixture id (never reused)")
    kind: FixtureKind = Field(description="positive | control | near-miss")
    task: str = Field(description="Realistic task description handed to discovery")
    expected_pack: str | None = Field(
        default=None,
        description="positive: the correct pack. near-miss: the tempting pack.",
    )
    covered_by: str | None = Field(
        default=None,
        description="near-miss only: the real answer, or the no-pack-needed marker",
    )

    @model_validator(mode="after")
    def _check_kind_fields(self) -> TriggerFixture:
        """Enforce the per-kind field contract instead of silently defaulting."""
        if self.kind == "positive" and not self.expected_pack:
            raise ValueError(f"{self.id}: positive fixture requires expected_pack")
        if self.kind == "positive" and self.covered_by:
            raise ValueError(f"{self.id}: positive fixture must not set covered_by")
        if self.kind == "control" and (self.expected_pack or self.covered_by):
            raise ValueError(
                f"{self.id}: control fixture must not set expected_pack or covered_by"
            )
        if self.kind == "near-miss" and not (self.expected_pack and self.covered_by):
            raise ValueError(
                f"{self.id}: near-miss fixture requires expected_pack and covered_by"
            )
        return self


class FixtureSet(BaseModel):
    """A complete labeled fixture set with unique, permanent ids."""

    model_config = ConfigDict(frozen=True)

    fixtures: list[TriggerFixture] = Field(description="All labeled fixtures")

    @model_validator(mode="after")
    def _check_unique_ids(self) -> FixtureSet:
        """Reject duplicate ids so per-fixture history stays attributable."""
        ids = [f.id for f in self.fixtures]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"Duplicate fixture ids: {duplicates}")
        return self

    def of_kind(self, kind: FixtureKind) -> list[TriggerFixture]:
        """Return every fixture of the given kind."""
        return [f for f in self.fixtures if f.kind == kind]


class FixtureOutcome(BaseModel):
    """Per-fixture result, tracked by permanent id across manifest revisions."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Fixture id")
    kind: FixtureKind = Field(description="Fixture kind")
    top_pack: str | None = Field(description="Rank-1 recommendation, or None")
    top_score: int = Field(default=0, description="Score of the rank-1 recommendation")
    passed: bool = Field(description="True when discovery behaved correctly")


class BenchmarkResult(BaseModel):
    """Benchmark figures. Accuracy fields are omitted when pairing is unmet."""

    model_config = ConfigDict(frozen=True)

    valid: bool = Field(description="False when the fixture set lacks a negative kind")
    reason: str | None = Field(default=None, description="Why accuracy was withheld")
    top1_accuracy: float | None = Field(default=None, description="Top-1 on positives")
    recall: float | None = Field(default=None, description="Expected pack in any rank")
    precision: float | None = Field(
        default=None, description="Correct rank-1 hits over all rank-1 recommendations"
    )
    control_false_positive_rate: float | None = Field(
        default=None, description="Controls receiving any recommendation"
    )
    near_miss_false_positive_rate: float | None = Field(
        default=None, description="Near-misses resolving to the tempting pack"
    )
    misclassified: list[str] = Field(
        default_factory=list, description="Ids of fixtures that behaved incorrectly"
    )
    outcomes: list[FixtureOutcome] = Field(
        default_factory=list[FixtureOutcome],
        description="Per-fixture outcomes in fixture order",
    )


def _evaluate(fixture: TriggerFixture, ranked: list[PackScore]) -> bool:
    """Return True when discovery behaved correctly for this fixture."""
    top = ranked[0].name if ranked else None
    if fixture.kind == "positive":
        return top == fixture.expected_pack
    if fixture.kind == "control":
        return top is None
    # AI: near-miss passes when the covering pack wins, or when nothing is
    # recommended and the covering answer is direct tool use. Recommending the
    # tempting pack is the failure this kind exists to catch.
    if fixture.covered_by == NO_PACK_NEEDED:
        return top is None
    return top == fixture.covered_by


def _rate(numerator: int, denominator: int) -> float:
    """Return numerator/denominator, or 0.0 when the denominator is zero."""
    return round(numerator / denominator, 4) if denominator else 0.0


def _positive_metrics(
    fixture_set: FixtureSet, ranked_by_id: dict[str, list[PackScore]]
) -> tuple[float, float, int]:
    """Return (top1_accuracy, recall, hit_count) over positive fixtures."""
    positives = fixture_set.of_kind("positive")
    hits = sum(
        1
        for f in positives
        if ranked_by_id[f.id] and ranked_by_id[f.id][0].name == f.expected_pack
    )
    recalled = sum(
        1
        for f in positives
        if any(s.name == f.expected_pack for s in ranked_by_id[f.id])
    )
    return _rate(hits, len(positives)), _rate(recalled, len(positives)), hits


def run_benchmark(
    fixture_set: FixtureSet,
    manifests: list[SkillPackManifest],
    limit: int = 5,
) -> BenchmarkResult:
    """Score every fixture through the discovery ranker and report paired metrics."""
    ranked_by_id = {
        f.id: rank_packs(manifests, f.task, limit) for f in fixture_set.fixtures
    }
    outcomes = [
        FixtureOutcome(
            id=f.id,
            kind=f.kind,
            top_pack=ranked_by_id[f.id][0].name if ranked_by_id[f.id] else None,
            top_score=ranked_by_id[f.id][0].score if ranked_by_id[f.id] else 0,
            passed=_evaluate(f, ranked_by_id[f.id]),
        )
        for f in fixture_set.fixtures
    ]
    misclassified = [o.id for o in outcomes if not o.passed]
    controls = fixture_set.of_kind("control")
    near_misses = fixture_set.of_kind("near-miss")
    if not controls or not near_misses:
        return BenchmarkResult(
            valid=False,
            reason=MISSING_NEGATIVES_REASON,
            misclassified=misclassified,
            outcomes=outcomes,
        )
    return _paired_result(
        fixture_set, ranked_by_id, outcomes, misclassified, controls, near_misses
    )


def _paired_result(
    fixture_set: FixtureSet,
    ranked_by_id: dict[str, list[PackScore]],
    outcomes: list[FixtureOutcome],
    misclassified: list[str],
    controls: list[TriggerFixture],
    near_misses: list[TriggerFixture],
) -> BenchmarkResult:
    """Build the full result once both negative kinds are present."""
    top1, recall, hits = _positive_metrics(fixture_set, ranked_by_id)
    by_id = {o.id: o for o in outcomes}
    control_fp = sum(1 for f in controls if by_id[f.id].top_pack is not None)
    near_fp = sum(1 for f in near_misses if by_id[f.id].top_pack == f.expected_pack)
    recommendations = sum(1 for o in outcomes if o.top_pack is not None)
    return BenchmarkResult(
        valid=True,
        top1_accuracy=top1,
        recall=recall,
        precision=_rate(hits, recommendations),
        control_false_positive_rate=_rate(control_fp, len(controls)),
        near_miss_false_positive_rate=_rate(near_fp, len(near_misses)),
        misclassified=misclassified,
        outcomes=outcomes,
    )


def format_report(result: BenchmarkResult) -> str:
    """Render a benchmark result as deterministic pretty JSON."""
    return json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True)
