"""Tests for the glossary parser and the advisory terminology gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.plans.terminology_gate import check_plan_terminology
from cortex.wiki.glossary import (
    glossary_document_path,
    load_glossary,
    parse_glossary,
)
from cortex.wiki.glossary_detect import (
    NEAR_MATCH_THRESHOLD,
    contains_phrase,
    detect_terminology_collisions,
    normalize_phrase,
)
from cortex.wiki.glossary_models import (
    Glossary,
    GlossaryParseError,
    TerminologyCase,
    TerminologyReport,
)

GLOSSARY_MD = """## Cortex domain glossary

Intro prose.

## Terms

### Plan

- **Definition**: A markdown file describing one finite unit of work.
- **Aliases**: plan file, plan document
- **Not to be confused with**: roadmap entry

### Roadmap entry

- **Definition**: A bullet registering a plan as upcoming work.
- **Aliases**: roadmap item
- **Not to be confused with**: plan

### Subagent

- **Definition**: A separate agent spawned for context isolation.
- **Aliases**: none
- **Not to be confused with**: none
"""


def _write_glossary(root: Path, markdown: str) -> Path:
    """Write a glossary into a fake project root and return its path."""
    path = glossary_document_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(markdown, encoding="utf-8")
    return path


class TestParseGlossaryPositive:
    """Well-formed glossary markdown parses into typed entries."""

    def test_parses_all_entries(self) -> None:
        """Arrange a full glossary; act by parsing; assert every term is present."""
        glossary = parse_glossary(GLOSSARY_MD)

        assert [e.term for e in glossary.entries] == [
            "Plan",
            "Roadmap entry",
            "Subagent",
        ]
        assert glossary.is_empty() is False

    def test_parses_multiple_aliases(self) -> None:
        """A comma-separated alias field yields one list item per alias."""
        glossary = parse_glossary(GLOSSARY_MD)

        plan = glossary.entries[0]

        assert plan.aliases == ["plan file", "plan document"]
        assert plan.not_to_be_confused_with == ["roadmap entry"]

    def test_none_fields_become_empty_lists(self) -> None:
        """`none` is the explicit empty marker for both list fields."""
        glossary = parse_glossary(GLOSSARY_MD)

        subagent = glossary.entries[2]

        assert subagent.aliases == []
        assert subagent.not_to_be_confused_with == []

    def test_empty_terms_section_parses_to_empty_glossary(self) -> None:
        """A Terms section with no entries is valid and yields no terms."""
        glossary = parse_glossary("## Terms\n")

        assert glossary.entries == []
        assert glossary.is_empty() is True


class TestParseGlossaryNegative:
    """Malformed glossary markdown raises GlossaryParseError."""

    def test_empty_file_rejected(self) -> None:
        """An empty glossary file has no Terms section and is rejected."""
        with pytest.raises(GlossaryParseError, match="Terms"):
            _ = parse_glossary("")

    def test_missing_definition_rejected(self) -> None:
        """An entry without a Definition bullet is a schema violation."""
        markdown = "## Terms\n\n### Plan\n\n- **Aliases**: none\n"

        with pytest.raises(GlossaryParseError, match="Definition"):
            _ = parse_glossary(markdown)

    def test_missing_confusable_field_rejected(self) -> None:
        """Both list fields are mandatory even when empty."""
        markdown = (
            "## Terms\n\n### Plan\n\n- **Definition**: A doc.\n- **Aliases**: none\n"
        )

        with pytest.raises(GlossaryParseError, match="Not to be confused with"):
            _ = parse_glossary(markdown)

    def test_duplicate_term_rejected(self) -> None:
        """A canonical term may be declared only once."""
        entry = (
            "### Plan\n\n- **Definition**: A doc.\n- **Aliases**: none\n"
            "- **Not to be confused with**: none\n\n"
        )

        with pytest.raises(GlossaryParseError, match="Duplicate"):
            _ = parse_glossary(f"## Terms\n\n{entry}{entry}")


class TestLoadGlossary:
    """Filesystem loading through the wiki root path."""

    def test_returns_none_when_absent(self, tmp_path: Path) -> None:
        """A project without a glossary loads as None, not an error."""
        assert load_glossary(tmp_path) is None

    def test_loads_written_file(self, tmp_path: Path) -> None:
        """A written glossary is found at the canonical wiki root path."""
        path = _write_glossary(tmp_path, GLOSSARY_MD)

        glossary = load_glossary(tmp_path)

        assert path.name == "glossary.md"
        assert glossary is not None
        assert len(glossary.entries) == 3


class TestDetectionCases:
    """One test per allowed detection case, plus the clean-plan baseline."""

    def test_declared_alias_hit(self) -> None:
        """Using a declared alias suggests the canonical term."""
        glossary = parse_glossary(GLOSSARY_MD)

        findings = detect_terminology_collisions(
            "This plan document defines the work.", glossary
        )

        alias_hits = [f for f in findings if f.case is TerminologyCase.DECLARED_ALIAS]
        assert len(alias_hits) == 1
        assert alias_hits[0].term == "plan document"
        assert alias_hits[0].canonical_term == "Plan"

    def test_possible_synonym_near_match(self) -> None:
        """A near-match that is not a declared alias is reported as possible."""
        glossary = parse_glossary(GLOSSARY_MD)

        findings = detect_terminology_collisions(
            "The sub-agent handles isolation.", glossary
        )

        synonyms = [f for f in findings if f.case is TerminologyCase.POSSIBLE_SYNONYM]
        assert [f.canonical_term for f in synonyms] == ["Subagent"]
        assert "possible unintended synonym" in synonyms[0].suggestion

    def test_confusable_pair_in_one_sentence(self) -> None:
        """Two confusable terms sharing a sentence are flagged once."""
        glossary = parse_glossary(GLOSSARY_MD)

        findings = detect_terminology_collisions(
            "Add the plan and the roadmap entry together.", glossary
        )

        pairs = [f for f in findings if f.case is TerminologyCase.CONFUSABLE_PAIR]
        assert len(pairs) == 1
        assert {pairs[0].term, pairs[0].canonical_term} == {"Plan", "Roadmap entry"}

    def test_confusable_pair_not_flagged_across_sentences(self) -> None:
        """Document-wide co-occurrence alone is not evidence of confusion."""
        glossary = parse_glossary(GLOSSARY_MD)

        findings = detect_terminology_collisions(
            "Write the plan first.\nRegister the roadmap entry afterwards.",
            glossary,
        )

        assert [f for f in findings if f.case is TerminologyCase.CONFUSABLE_PAIR] == []

    def test_clean_plan_produces_no_findings(self) -> None:
        """Prose containing no glossary vocabulary yields nothing."""
        glossary = parse_glossary(GLOSSARY_MD)

        assert (
            detect_terminology_collisions("Rename the colour picker.", glossary) == []
        )

    def test_empty_glossary_short_circuits(self) -> None:
        """With no terms declared there is nothing to collide with."""
        assert detect_terminology_collisions("plan document", Glossary()) == []


class TestFalsePositiveGuards:
    """Correct use of canonical vocabulary must stay silent."""

    def test_canonical_term_not_flagged(self) -> None:
        """Using the canonical term itself produces no finding."""
        glossary = parse_glossary(GLOSSARY_MD)

        assert detect_terminology_collisions("Write the plan.", glossary) == []

    def test_plural_canonical_term_not_flagged(self) -> None:
        """Plural forms normalize to the canonical term."""
        glossary = parse_glossary(GLOSSARY_MD)

        assert detect_terminology_collisions("List all plans here.", glossary) == []

    def test_morphological_variant_not_flagged(self) -> None:
        """`planning` is below the near-match threshold and must not fire."""
        glossary = parse_glossary(GLOSSARY_MD)

        assert detect_terminology_collisions("Planning proceeds now.", glossary) == []

    def test_code_spans_are_ignored(self) -> None:
        """Identifiers inside code spans are not prose and are skipped."""
        glossary = parse_glossary(GLOSSARY_MD)

        findings = detect_terminology_collisions(
            "Call `plan document` then:\n```\nplan document\n```\n", glossary
        )

        assert findings == []

    def test_threshold_is_pinned(self) -> None:
        """The tuned threshold is part of the contract, not an implementation detail."""
        assert NEAR_MATCH_THRESHOLD == 0.86


class TestTerminologyGate:
    """The gate wrapper degrades to silence and never raises."""

    def test_no_glossary_reports_unchecked(self, tmp_path: Path) -> None:
        """Projects without a glossary get checked=False and no findings."""
        report = check_plan_terminology(tmp_path, "any plan body")

        assert report.checked is False
        assert report.findings == []
        assert report.summary() == "Not checked (no glossary)"

    def test_malformed_glossary_does_not_raise(self, tmp_path: Path) -> None:
        """A broken glossary is downgraded to unchecked, not an exception."""
        _ = _write_glossary(tmp_path, "no terms section here")

        report = check_plan_terminology(tmp_path, "plan document")

        assert report.checked is False

    def test_findings_returned_for_colliding_body(self, tmp_path: Path) -> None:
        """A colliding body yields checked=True with findings."""
        _ = _write_glossary(tmp_path, GLOSSARY_MD)

        report = check_plan_terminology(tmp_path, "The plan document is ready.")

        assert report.checked is True
        assert [f.canonical_term for f in report.findings] == ["Plan"]
        assert "plan document -> Plan" in report.summary()

    def test_clean_body_summary(self, tmp_path: Path) -> None:
        """A clean plan reports the 'No collisions' row value."""
        _ = _write_glossary(tmp_path, GLOSSARY_MD)

        report = check_plan_terminology(tmp_path, "Rename the colour picker.")

        assert report.checked is True
        assert report.summary() == "No collisions"

    def test_report_default_is_silent(self) -> None:
        """An unchecked report carries no findings by default."""
        assert TerminologyReport(checked=False).findings == []


class TestPlanCreateIntegration:
    """`plan(operation="create")` stays advisory: findings AND a written file."""

    @pytest.mark.asyncio
    async def test_colliding_plan_is_still_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Collisions are reported but the plan file is written and status succeeds."""
        from cortex.tools.plans import crud

        _ = _write_glossary(tmp_path, GLOSSARY_MD)

        async def _root(*_args: object, **_kwargs: object) -> Path:
            return tmp_path

        monkeypatch.setattr(crud, "resolve_project_root_async", _root)

        raw = await crud.create_plan(
            operation="create",
            title="Advisory Gate Demo",
            content="## Goal\n\nThe plan document must still be created.\n",
        )
        payload = json.loads(raw)

        assert payload["status"] == "success"
        assert Path(payload["file_path"]).is_file()
        assert (
            payload["terminology_summary"] == "plan document -> Plan (declared_alias)"
        )
        assert payload["terminology_findings"][0]["canonical_term"] == "Plan"

    @pytest.mark.asyncio
    async def test_clean_plan_reports_no_collisions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A clean plan body still carries the Terminology row value."""
        from cortex.tools.plans import crud

        _ = _write_glossary(tmp_path, GLOSSARY_MD)

        async def _root(*_args: object, **_kwargs: object) -> Path:
            return tmp_path

        monkeypatch.setattr(crud, "resolve_project_root_async", _root)

        raw = await crud.create_plan(
            operation="create",
            title="Clean Demo",
            content="## Goal\n\nRename the colour picker.\n",
        )
        payload = json.loads(raw)

        assert payload["status"] == "success"
        assert payload["terminology_findings"] == []
        assert payload["terminology_summary"] == "No collisions"


class TestNormalizationHelpers:
    """Normalization branches that the detection cases exercise indirectly."""

    def test_ies_plural_folds_to_y(self) -> None:
        """`entries` folds onto the canonical `entry` spelling."""
        assert normalize_phrase("roadmap entries") == "roadmap entry"

    def test_ches_plural_folds(self) -> None:
        """`-ches` plurals drop the `es` suffix."""
        assert normalize_phrase("branches") == "branch"

    def test_double_s_word_is_not_singularized(self) -> None:
        """A word ending in `ss` is already singular."""
        assert normalize_phrase("progress") == "progress"

    def test_hyphen_is_a_word_separator(self) -> None:
        """Path-style spellings fold onto the spaced canonical form."""
        assert normalize_phrase("memory-bank") == "memory bank"

    def test_non_alphabetic_phrase_normalizes_to_empty(self) -> None:
        """A phrase with no letters yields an empty key."""
        assert normalize_phrase("123") == ""

    def test_contains_phrase_rejects_empty_phrase(self) -> None:
        """An empty phrase never matches."""
        assert contains_phrase("any text", "123") is False


class TestDetectionRobustness:
    """Edge cases that must not crash or duplicate output."""

    def test_repeated_alias_reported_once(self) -> None:
        """The same alias occurring twice yields a single finding."""
        glossary = parse_glossary(GLOSSARY_MD)

        findings = detect_terminology_collisions(
            "The plan document is here. Read the plan document again.", glossary
        )

        assert len(findings) == 1
        assert findings[0].term == "plan document"

    def test_entry_with_no_letters_is_skipped(self) -> None:
        """A term that normalizes to nothing is ignored rather than crashing."""
        markdown = (
            "## Terms\n\n### 123\n\n- **Definition**: Odd.\n"
            "- **Aliases**: none\n- **Not to be confused with**: none\n"
        )
        glossary = parse_glossary(markdown)

        assert detect_terminology_collisions("Some plan text.", glossary) == []

    def test_alias_equal_to_canonical_term_is_not_reported(self) -> None:
        """An alias that is only a plural of the term produces no finding."""
        markdown = (
            "## Terms\n\n### Plan\n\n- **Definition**: A doc.\n"
            "- **Aliases**: plans\n- **Not to be confused with**: none\n"
        )
        glossary = parse_glossary(markdown)

        assert detect_terminology_collisions("Write the plans.", glossary) == []
