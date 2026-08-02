"""Typed models for the canonical domain glossary and its terminology gate."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from cortex.tools.models_base import StrictBaseModel


class GlossaryParseError(ValueError):
    """Raised when `.cortex/wiki/glossary.md` does not match the entry schema."""


class GlossaryEntry(StrictBaseModel):
    """One canonical term with its definition, aliases, and confusable terms."""

    term: str = Field(min_length=1, description="Canonical term as written in the wiki")
    definition: str = Field(min_length=1, description="One-sentence meaning in Cortex")
    aliases: list[str] = Field(
        default_factory=lambda: [],
        description="Wordings that should be rewritten to the canonical term",
    )
    not_to_be_confused_with: list[str] = Field(
        default_factory=lambda: [],
        description="Canonical terms commonly mistaken for this one",
    )


class Glossary(StrictBaseModel):
    """Parsed `glossary.md` document."""

    entries: list[GlossaryEntry] = Field(
        default_factory=lambda: [],
        description="Canonical entries in document order",
    )

    def is_empty(self) -> bool:
        """Return True when the glossary declares no terms."""
        return not self.entries


class TerminologyCase(str, Enum):
    """The three conservative collision cases the gate is allowed to report."""

    DECLARED_ALIAS = "declared_alias"
    POSSIBLE_SYNONYM = "possible_synonym"
    CONFUSABLE_PAIR = "confusable_pair"


class TerminologyFinding(StrictBaseModel):
    """A single advisory terminology collision found in a plan body."""

    case: TerminologyCase = Field(description="Which of the three detection cases hit")
    term: str = Field(min_length=1, description="Wording found in the plan text")
    canonical_term: str = Field(
        min_length=1, description="Glossary term the wording collides with"
    )
    suggestion: str = Field(
        min_length=1, description="Human-facing advice; never blocks plan creation"
    )


class TerminologyReport(StrictBaseModel):
    """Advisory result of checking a plan body against the glossary.

    ``checked`` is False when no glossary exists or it could not be parsed; the
    gate stays silent rather than guessing, and plan creation always proceeds.
    """

    checked: bool = Field(description="True when a glossary was loaded and applied")
    findings: list[TerminologyFinding] = Field(
        default_factory=lambda: [],
        description="Deduplicated findings, empty when no collisions were detected",
    )

    def summary(self) -> str:
        """Return the one-line Terminology row value for the plan final report."""
        if not self.checked:
            return "Not checked (no glossary)"
        if not self.findings:
            return "No collisions"
        return "; ".join(
            f"{f.term} -> {f.canonical_term} ({f.case.value})" for f in self.findings
        )
