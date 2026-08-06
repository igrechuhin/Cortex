"""Trigger scoring for skill pack discovery.

Scores a task description against a pack's ``name``, ``description`` and
``keywords``. Extracted from ``operations.py`` so the trigger-accuracy benchmark
(plan: skill-pack-trigger-accuracy-benchmark-and-description-tuning) can measure
the scorer directly without importing the MCP tool surface.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from cortex.tools.skill_pack.models import SkillPackManifest

# AI: Weights are benchmark-tuned; changing one requires re-running the trigger
# benchmark (tests/tools/test_skill_pack_trigger_benchmark.py).
NAME_MATCH_SCORE = 3
DESCRIPTION_MATCH_SCORE = 2
MAX_KEYWORD_SCORE = 3
STRONG_MATCH_THRESHOLD = 3
# AI: A single generic keyword hit is not enough signal to recommend a pack;
# requiring two measurably removed every control false positive at no cost to
# top-1 accuracy or recall on the trigger benchmark.
MIN_RECOMMEND_SCORE = 2

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class PackScore(BaseModel):
    """Scored relevance of one pack for one task description."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Pack name")
    description: str = Field(description="Pack description")
    score: int = Field(description="Total relevance score (higher = more relevant)")
    matched_name: bool = Field(
        default=False, description="True when the pack name appears in the task"
    )
    matched_description: bool = Field(
        default=False, description="True when the full description appears in the task"
    )
    matched_keywords: list[str] = Field(
        default_factory=list, description="Keywords found in the task description"
    )


def tokenize(text: str) -> list[str]:
    """Split text into lowercase alphanumeric tokens."""
    return _TOKEN_RE.findall(text.lower())


def _contains_phrase(haystack: list[str], needle: list[str]) -> bool:
    """Return True when needle appears as a contiguous token run inside haystack."""
    if not needle or len(needle) > len(haystack):
        return False
    span = len(needle)
    return any(
        haystack[i : i + span] == needle for i in range(len(haystack) - span + 1)
    )


def _matched_keywords(manifest: SkillPackManifest, task_tokens: list[str]) -> list[str]:
    """Return the manifest keywords present in the task as whole tokens/phrases."""
    return [
        kw for kw in manifest.keywords if _contains_phrase(task_tokens, tokenize(kw))
    ]


def score_pack(manifest: SkillPackManifest, task_description: str) -> PackScore:
    """Score one pack against a task description, recording every matched signal."""
    empty = PackScore(name=manifest.name, description=manifest.description, score=0)
    if not task_description or not task_description.strip():
        return empty
    task_tokens = tokenize(task_description)
    name_hit = _contains_phrase(task_tokens, tokenize(manifest.name))
    desc_hit = bool(manifest.description) and _contains_phrase(
        task_tokens, tokenize(manifest.description)
    )
    keywords = _matched_keywords(manifest, task_tokens)
    score = (
        (NAME_MATCH_SCORE if name_hit else 0)
        + (DESCRIPTION_MATCH_SCORE if desc_hit else 0)
        # AI: Keyword contribution is capped so a verbose manifest cannot outrank
        # a genuinely closer pack purely by listing more keywords.
        + min(len(keywords), MAX_KEYWORD_SCORE)
    )
    return PackScore(
        name=manifest.name,
        description=manifest.description,
        score=score,
        matched_name=name_hit,
        matched_description=desc_hit,
        matched_keywords=keywords,
    )


def describe_match(pack_score: PackScore) -> str:
    """Build an honest, signal-specific reason string for a scored pack."""
    signals: list[str] = []
    if pack_score.matched_name:
        signals.append(f"pack name '{pack_score.name}'")
    if pack_score.matched_description:
        signals.append("pack description")
    if pack_score.matched_keywords:
        signals.append("keywords: " + ", ".join(pack_score.matched_keywords))
    if not signals:
        return "No match; this pack was not triggered by the task description"
    strength = "Strong" if pack_score.score >= STRONG_MATCH_THRESHOLD else "Weak"
    return f"{strength} match on " + "; ".join(signals)


def rank_packs(
    manifests: list[SkillPackManifest], task_description: str, limit: int
) -> list[PackScore]:
    """Return packs meeting the recommendation floor, best first, tie-broken by name."""
    scored = [score_pack(m, task_description) for m in manifests]
    scored.sort(key=lambda s: (-s.score, s.name))
    return [s for s in scored if s.score >= MIN_RECOMMEND_SCORE][:limit]
