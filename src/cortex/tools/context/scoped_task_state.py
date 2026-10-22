"""Compact, nonauthoritative task evidence carried by scoped context."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.tools.context.scoped_evidence_state import ScopedEvidenceState
from cortex.tools.context.scoped_readiness import ScopedReadiness


class _Evidence(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)

    value: str | None = None
    sources: list[str] = Field(default_factory=list)
    state: ScopedEvidenceState = ScopedEvidenceState.MISSING


class _DependencyEvidence(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)

    slug: str
    source: str
    status: str | None = None
    satisfied: bool = False


class _ContextIssue(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)

    code: str
    sources: list[str]
    message: str


class ScopedTaskState(BaseModel):
    """Evidence is reported without choosing between conflicting authorities."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    goal: _Evidence = Field(default_factory=_Evidence)
    plan_goal: _Evidence = Field(default_factory=_Evidence)
    status: _Evidence = Field(default_factory=_Evidence)
    dependencies: list[_DependencyEvidence] = Field(
        default_factory=list[_DependencyEvidence]
    )
    readiness: ScopedReadiness = ScopedReadiness.UNKNOWN
    allowed_files: list[str] = Field(default_factory=list)
    prohibitions: list[str] = Field(default_factory=list)
    prohibition_sources: list[str] = Field(default_factory=list)
    plan_prohibitions: _Evidence = Field(default_factory=_Evidence)
    open_decisions: _Evidence = Field(default_factory=_Evidence)
    decision_summary: _Evidence = Field(default_factory=_Evidence)
    issues: list[_ContextIssue] = Field(default_factory=list[_ContextIssue])

    def issue(self, code: str, sources: list[str], message: str) -> None:
        self.issues.append(_ContextIssue(code=code, sources=sources, message=message))

    def evidence(
        self,
        field: str,
        value: str | None,
        sources: list[str],
        state: ScopedEvidenceState | None = None,
    ) -> None:
        evidence = _Evidence(
            value=value,
            sources=sources,
            state=state
            or (ScopedEvidenceState.PRESENT if value else ScopedEvidenceState.MISSING),
        )
        setattr(self, field, evidence)

    def dependency(
        self, slug: str, source: str, status: str | None, done: bool
    ) -> None:
        self.dependencies.append(
            _DependencyEvidence(slug=slug, source=source, status=status, satisfied=done)
        )
