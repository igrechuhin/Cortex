"""Advisory terminology collision detection for new plan bodies.

Exactly three conservative cases are detected — a declared-alias hit, a near-match
undeclared synonym, and a "not to be confused with" pair. Nothing subtler is
attempted, and findings never block plan creation.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from cortex.wiki.glossary_models import (
    Glossary,
    GlossaryEntry,
    TerminologyCase,
    TerminologyFinding,
)

# AI: Pinned against the seeded glossary. Below this, ordinary morphology
# ("planning" vs "plan") starts firing; above it, real synonyms are missed.
NEAR_MATCH_THRESHOLD = 0.86

MAX_FINDINGS = 20

_FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`]*`")
# AI: Hyphens are word separators, not word characters, so the path-style spelling
# `memory-bank` folds onto the canonical `memory bank` instead of near-matching it.
_WORD = re.compile(r"[a-z]+")


def strip_code_spans(text: str) -> str:
    """Remove fenced blocks and inline code so identifiers are not treated as prose."""
    return _INLINE_CODE.sub(" ", _FENCED_CODE.sub(" ", text))


def _singularize(word: str) -> str:
    """Fold the common English plural endings so `plans` matches `plan`."""
    if len(word) > 4 and word.endswith("ies"):
        return f"{word[:-3]}y"
    if len(word) > 4 and word.endswith(("ses", "xes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def normalize_phrase(phrase: str) -> str:
    """Lowercase a phrase and singularize its final word."""
    words = _WORD.findall(phrase.casefold())
    if not words:
        return ""
    words[-1] = _singularize(words[-1])
    return " ".join(words)


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Build a whole-word pattern tolerant of plural forms and hyphen/space breaks."""
    words = _WORD.findall(phrase.casefold())
    joined = r"[\s-]+".join(re.escape(word) for word in words)
    return re.compile(rf"\b{joined}e?s?\b", re.IGNORECASE)


def contains_phrase(text: str, phrase: str) -> bool:
    """Return True when `phrase` occurs in `text` as whole words."""
    words = _WORD.findall(phrase.casefold())
    if not words:
        return False
    return _phrase_pattern(phrase).search(text) is not None


class _GlossaryIndex:
    """Normalized lookup tables derived from a parsed glossary."""

    def __init__(self, glossary: Glossary) -> None:
        self.entries: list[GlossaryEntry] = list(glossary.entries)
        self.canonical_keys: dict[str, GlossaryEntry] = {}
        self.known_keys: set[str] = set()
        for entry in self.entries:
            key = normalize_phrase(entry.term)
            if key:
                self.canonical_keys[key] = entry
                self.known_keys.add(key)
            for alias in entry.aliases:
                alias_key = normalize_phrase(alias)
                if alias_key:
                    self.known_keys.add(alias_key)


def _alias_findings(text: str, index: _GlossaryIndex) -> list[TerminologyFinding]:
    """Case 1 — the plan uses a wording declared as an alias of a canonical term."""
    findings: list[TerminologyFinding] = []
    for entry in index.entries:
        for alias in entry.aliases:
            if normalize_phrase(alias) == normalize_phrase(entry.term):
                continue
            if contains_phrase(text, alias):
                findings.append(
                    TerminologyFinding(
                        case=TerminologyCase.DECLARED_ALIAS,
                        term=alias,
                        canonical_term=entry.term,
                        suggestion=(
                            f"'{alias}' is a declared alias of '{entry.term}'; "
                            f"use '{entry.term}' for consistency."
                        ),
                    )
                )
    return findings


def _sentences(text: str) -> list[str]:
    """Split prose into sentence-sized units for co-occurrence scoping."""
    return [part for part in re.split(r"(?<=[.!?;:])\s+|\n", text) if part.strip()]


def _confusable_findings(text: str, index: _GlossaryIndex) -> list[TerminologyFinding]:
    """Case 3 — a term and one of its declared confusables share one sentence.

    Document-wide co-occurrence is not evidence of confusion — most plans mention
    several glossary terms legitimately. Requiring the pair inside a single
    sentence is the narrowest reading of "a context suggesting confusion".
    """
    findings: list[TerminologyFinding] = []
    seen: set[frozenset[str]] = set()
    for sentence in _sentences(text):
        for entry in index.entries:
            if not contains_phrase(sentence, entry.term):
                continue
            for other in entry.not_to_be_confused_with:
                other_entry = index.canonical_keys.get(normalize_phrase(other))
                if other_entry is None or not contains_phrase(sentence, other):
                    continue
                pair = frozenset(
                    {normalize_phrase(entry.term), normalize_phrase(other)}
                )
                if pair in seen:
                    continue
                seen.add(pair)
                findings.append(_confusable_finding(entry, other_entry))
    return findings


def _confusable_finding(
    entry: GlossaryEntry, other_entry: GlossaryEntry
) -> TerminologyFinding:
    """Build the advisory finding for a confusable pair sharing a sentence."""
    return TerminologyFinding(
        case=TerminologyCase.CONFUSABLE_PAIR,
        term=other_entry.term,
        canonical_term=entry.term,
        suggestion=(
            f"'{other_entry.term}' and '{entry.term}' are easily confused; "
            "confirm each use names the intended concept."
        ),
    )


def _candidate_phrases(text: str) -> set[str]:
    """Collect normalized unigrams and bigrams from plan prose."""
    words = _WORD.findall(text.casefold())
    phrases: set[str] = set()
    for position, word in enumerate(words):
        if len(word) >= 4:
            phrases.add(normalize_phrase(word))
        if position + 1 < len(words):
            phrases.add(normalize_phrase(f"{word} {words[position + 1]}"))
    phrases.discard("")
    return phrases


def _best_near_match(
    candidate: str, index: _GlossaryIndex
) -> tuple[GlossaryEntry, float] | None:
    """Return the closest canonical entry above the near-match threshold."""
    best: tuple[GlossaryEntry, float] | None = None
    for key, entry in index.canonical_keys.items():
        ratio = SequenceMatcher(None, candidate, key).ratio()
        if ratio >= NEAR_MATCH_THRESHOLD and (best is None or ratio > best[1]):
            best = (entry, ratio)
    return best


def _synonym_findings(text: str, index: _GlossaryIndex) -> list[TerminologyFinding]:
    """Case 2 — a near-match of a canonical term that is not a declared alias."""
    findings: list[TerminologyFinding] = []
    for candidate in sorted(_candidate_phrases(text)):
        if candidate in index.known_keys:
            continue
        match = _best_near_match(candidate, index)
        if match is None:
            continue
        entry, _ratio = match
        findings.append(
            TerminologyFinding(
                case=TerminologyCase.POSSIBLE_SYNONYM,
                term=candidate,
                canonical_term=entry.term,
                suggestion=(
                    f"'{candidate}' closely resembles '{entry.term}' but is not a "
                    f"declared alias; possible unintended synonym."
                ),
            )
        )
    return findings


def _deduplicate(findings: list[TerminologyFinding]) -> list[TerminologyFinding]:
    """Drop repeated (case, term, canonical) triples and cap the report size."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[TerminologyFinding] = []
    for finding in findings:
        key = (
            finding.case.value,
            finding.term.casefold(),
            finding.canonical_term.casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique[:MAX_FINDINGS]


def detect_terminology_collisions(
    plan_markdown: str, glossary: Glossary
) -> list[TerminologyFinding]:
    """Detect the three advisory collision cases in a plan body.

    Returns an empty list for a clean plan or an empty glossary. Never raises for
    ordinary input, so plan creation is unaffected by the outcome.
    """
    if glossary.is_empty():
        return []
    text = strip_code_spans(plan_markdown)
    index = _GlossaryIndex(glossary)
    return _deduplicate(
        _alias_findings(text, index)
        + _synonym_findings(text, index)
        + _confusable_findings(text, index)
    )
