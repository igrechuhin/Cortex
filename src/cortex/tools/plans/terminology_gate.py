"""Advisory glossary terminology gate for `plan(operation="create")`.

The gate is deliberately non-blocking: a plan is always written and registerable
regardless of what this returns. Findings exist to give the author visibility,
not to veto vocabulary.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cortex.wiki.glossary import load_glossary
from cortex.wiki.glossary_detect import detect_terminology_collisions
from cortex.wiki.glossary_models import GlossaryParseError, TerminologyReport

logger = logging.getLogger(__name__)

__all__ = ["check_plan_terminology"]


def check_plan_terminology(project_root: Path, plan_markdown: str) -> TerminologyReport:
    """Check a plan body against `.cortex/wiki/glossary.md`.

    Returns a report with ``checked=False`` when no glossary exists or it cannot be
    read or parsed. Every failure mode degrades to silence — this function never
    raises, so plan creation cannot fail because of the terminology gate.
    """
    try:
        glossary = load_glossary(project_root)
    except (GlossaryParseError, OSError) as exc:
        logger.warning("terminology gate: glossary unavailable (%s)", exc)
        return TerminologyReport(checked=False, findings=[])
    if glossary is None:
        return TerminologyReport(checked=False, findings=[])
    try:
        findings = detect_terminology_collisions(plan_markdown, glossary)
    except Exception as exc:  # pragma: no cover - defensive; gate must never block
        logger.warning("terminology gate: detection failed (%s)", exc)
        return TerminologyReport(checked=False, findings=[])
    return TerminologyReport(checked=True, findings=findings)
