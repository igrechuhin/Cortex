"""Falsifiable claim vocabulary for the prediction gate.

A prediction is a small, structured claim an agent records *before* it edits
code. Every form in this module is decidable from a quality-gate result or a
git diff, so the next gate run can contradict it. Free text is accepted but
degrades to an implied ``change`` claim -- an empty prediction is rejected
outright, because an empty prediction predicts nothing.

Grading lives in :mod:`cortex.experience.claim_grading`; this module is pure
vocabulary and has no dependency on the gate machinery.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "CLAIM_HELP",
    "Claim",
    "ClaimKind",
    "ClaimSyntaxError",
    "ClaimVerdict",
    "Verdict",
    "is_free_text",
    "parse_claims",
]

CLAIM_HELP = (
    "Claim forms (join several with ';'): "
    "'gate clean' | 'gate fails <check>' | 'error gone <check>@<path>' | "
    "'test <nodeid> passes' | 'test <nodeid> fails' | 'coverage >= <pct>' | "
    "'touches <path>' | 'noop <path>' | 'change' | 'noop'. "
    "Free text is graded as an implied 'change'."
)


class ClaimSyntaxError(ValueError):
    """Raised for an empty prediction or a malformed structured claim."""


class ClaimKind(str, Enum):
    """The decidable claim forms."""

    GATE_CLEAN = "gate_clean"
    GATE_FAILS = "gate_fails"
    ERROR_GONE = "error_gone"
    TEST_PASSES = "test_passes"
    TEST_FAILS = "test_fails"
    COVERAGE_AT_LEAST = "coverage_at_least"
    TOUCHES = "touches"
    NOOP_PATH = "noop_path"
    CHANGE = "change"
    NOOP = "noop"


class Verdict(str, Enum):
    """Grading outcome for a single claim.

    ``UNGRADED`` is first-class on purpose: when the frame carries no evidence
    either way, saying so is honest, while a silent pass is a lie.
    """

    HIT = "HIT"
    MISS = "MISS"
    UNGRADED = "UNGRADED"


class Claim(BaseModel):
    """One parsed, falsifiable claim."""

    kind: ClaimKind
    target: str = Field(default="", description="Check name, path, or test node id")
    threshold: float | None = Field(
        default=None, description="Numeric bound for coverage claims"
    )
    raw: str = Field(description="Original claim text as written")


class ClaimVerdict(BaseModel):
    """A claim plus the verdict a grading frame produced for it."""

    claim: Claim
    verdict: Verdict
    evidence: str = Field(description="What in the frame decided the verdict")


# AI: ordered longest-form-first so 'noop <path>' wins over bare 'noop'.
_PATTERNS: tuple[tuple[re.Pattern[str], ClaimKind], ...] = (
    (re.compile(r"^gate\s+clean$", re.IGNORECASE), ClaimKind.GATE_CLEAN),
    (
        re.compile(r"^gate\s+fails\s+(?P<target>\S+)$", re.IGNORECASE),
        ClaimKind.GATE_FAILS,
    ),
    (
        re.compile(r"^error\s+gone\s+(?P<target>[^@\s]+@\S+)$", re.IGNORECASE),
        ClaimKind.ERROR_GONE,
    ),
    (
        re.compile(r"^test\s+(?P<target>\S+)\s+passes$", re.IGNORECASE),
        ClaimKind.TEST_PASSES,
    ),
    (
        re.compile(r"^test\s+(?P<target>\S+)\s+fails$", re.IGNORECASE),
        ClaimKind.TEST_FAILS,
    ),
    (
        re.compile(r"^coverage\s*>=\s*(?P<target>\d+(?:\.\d+)?)\s*%?$", re.IGNORECASE),
        ClaimKind.COVERAGE_AT_LEAST,
    ),
    (re.compile(r"^touches\s+(?P<target>\S+)$", re.IGNORECASE), ClaimKind.TOUCHES),
    (re.compile(r"^noop\s+(?P<target>\S+)$", re.IGNORECASE), ClaimKind.NOOP_PATH),
    (re.compile(r"^change$", re.IGNORECASE), ClaimKind.CHANGE),
    (re.compile(r"^noop$", re.IGNORECASE), ClaimKind.NOOP),
)

# AI: a claim opening with one of these words meant to be structured -- failing
# to match a pattern is a typo worth rejecting, not free text worth guessing.
_KEYWORDS: frozenset[str] = frozenset(
    {"gate", "error", "test", "coverage", "touches", "noop", "change"}
)


def _build_claim(kind: ClaimKind, target: str, raw: str) -> Claim:
    threshold = (
        float(target) if kind is ClaimKind.COVERAGE_AT_LEAST and target else None
    )
    return Claim(kind=kind, target=target, threshold=threshold, raw=raw)


def _match_pattern(normalized: str) -> Claim | None:
    for pattern, kind in _PATTERNS:
        match = pattern.match(normalized)
        if match is None:
            continue
        return _build_claim(kind, match.groupdict().get("target") or "", normalized)
    return None


def _parse_one(part: str) -> Claim:
    normalized = " ".join(part.split())
    claim = _match_pattern(normalized)
    if claim is not None:
        return claim
    first_word = normalized.split(" ", 1)[0].lower()
    if first_word in _KEYWORDS:
        raise ClaimSyntaxError(f"Malformed claim {normalized!r}. {CLAIM_HELP}")
    # AI: free text still commits the agent to *something* changing.
    return Claim(kind=ClaimKind.CHANGE, target="", raw=normalized)


def parse_claims(text: str | None) -> list[Claim]:
    """Parse ``text`` into one or more claims, splitting on ``;``.

    Raises ``ClaimSyntaxError`` when the prediction is empty or when a claim
    that opens with a vocabulary keyword does not match any known form.
    """
    parts = [part for part in (text or "").split(";") if part.strip()]
    if not parts:
        raise ClaimSyntaxError(f"An empty prediction predicts nothing. {CLAIM_HELP}")
    return [_parse_one(part) for part in parts]


def is_free_text(claim: Claim) -> bool:
    """True when the claim came from free text rather than the vocabulary."""
    return claim.kind is ClaimKind.CHANGE and claim.raw.strip().lower() != "change"
