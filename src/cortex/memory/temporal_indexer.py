"""Temporal memory indexer for memory-bank markdown files."""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.memory.temporal_store import (
    TemporalFact,
    TemporalFactCategory,
    TemporalMemoryStore,
)

logger = logging.getLogger(__name__)

_ROADMAP_STATUS_RE = re.compile(
    r"^-\s*\*\*(.+?)\*\*.*-\s*(PENDING|DONE|BLOCKED|ACTIVE)\b"
)
_PLAN_PATH_RE = re.compile(
    r"Plan:\s*\.cortex/plans/([a-z0-9][a-z0-9\-]*)\.md", re.IGNORECASE
)
_DEPENDS_RE = re.compile(r"^depends_on:\s*\[(.*?)\]\s*$", re.IGNORECASE)
_COMPLETED_RE = re.compile(r"completed:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def _today_iso() -> str:
    return date.today().isoformat()


def _slugify(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return lowered or "unknown"


def _plan_slug_from_roadmap_line(title: str, line: str) -> str:
    match = _PLAN_PATH_RE.search(line)
    if match is not None:
        return match.group(1)
    return _slugify(title)


class TemporalIndexer:
    """Parse memory-bank files and persist temporal facts."""

    def __init__(self, store: TemporalMemoryStore, project_root: Path) -> None:
        self._store = store
        self._project_root = project_root

    def index_all(self) -> dict[str, int]:
        files = list((self._project_root / ".cortex" / "memory-bank").glob("*.md"))
        counts: dict[str, int] = {}
        for file_path in sorted(files):
            counts[file_path.name] = self.index_file(file_path)
        return counts

    def index_file(self, file_path: Path) -> int:
        if not file_path.exists():
            return 0
        content = file_path.read_text(encoding="utf-8")
        facts = self._extract_facts(file_path, content)
        added = 0
        for fact in facts:
            conflicts = self.check_contradiction(fact)
            if conflicts:
                self._log_conflicts(fact, conflicts)
            self._store.add_fact(fact)
            added += 1
        return added

    def check_contradiction(self, new_fact: TemporalFact) -> list[TemporalFact]:
        open_facts = self._store.current_facts(subject=new_fact.subject)
        return [
            fact
            for fact in open_facts
            if fact.predicate == new_fact.predicate and fact.object != new_fact.object
        ]

    def _extract_facts(self, file_path: Path, content: str) -> list[TemporalFact]:
        facts: list[TemporalFact] = []
        if file_path.name == MemoryBankFile.ROADMAP:
            facts.extend(self._extract_roadmap_status(file_path, content))
        if file_path.suffix == ".md":
            facts.extend(self._extract_plan_depends_on(file_path, content))
        if file_path.name == MemoryBankFile.ACTIVE_CONTEXT:
            facts.extend(self._extract_active_context_completion(file_path, content))
        return facts

    def _extract_roadmap_status(
        self, file_path: Path, content: str
    ) -> list[TemporalFact]:
        facts: list[TemporalFact] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            match = _ROADMAP_STATUS_RE.match(line.strip())
            if match is None:
                continue
            title, status = match.group(1).strip(), match.group(2).strip()
            facts.append(
                TemporalFact(
                    category=TemporalFactCategory.STATUS,
                    subject=_plan_slug_from_roadmap_line(title, line),
                    predicate="status",
                    object=status,
                    valid_from=_today_iso(),
                    source_file=str(file_path),
                    source_line=line_no,
                )
            )
        return facts

    def _extract_plan_depends_on(
        self, file_path: Path, content: str
    ) -> list[TemporalFact]:
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            return []
        slug = file_path.stem
        facts: list[TemporalFact] = []
        for line_no, line in enumerate(lines[1:], start=2):
            if line.strip() == "---":
                break
            match = _DEPENDS_RE.match(line.strip())
            if match is None:
                continue
            values = [item.strip().strip("'\"") for item in match.group(1).split(",")]
            for dep in [item for item in values if item]:
                facts.append(
                    TemporalFact(
                        category=TemporalFactCategory.DEPENDENCY,
                        subject=slug,
                        predicate="depends_on",
                        object=dep,
                        valid_from=_today_iso(),
                        source_file=str(file_path),
                        source_line=line_no,
                    )
                )
        return facts

    def _extract_active_context_completion(
        self, file_path: Path, content: str
    ) -> list[TemporalFact]:
        facts: list[TemporalFact] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            match = _COMPLETED_RE.search(line)
            if match is None:
                continue
            completed_date = match.group(1)
            facts.append(
                TemporalFact(
                    category=TemporalFactCategory.STATUS,
                    subject="active-context-entry",
                    predicate="completed",
                    object="true",
                    valid_from=completed_date,
                    valid_to=completed_date,
                    source_file=str(file_path),
                    source_line=line_no,
                )
            )
        return facts

    def _log_conflicts(
        self, new_fact: TemporalFact, conflicts: list[TemporalFact]
    ) -> None:
        for old_fact in conflicts:
            logger.warning(
                "[temporal] Possible contradiction: %s.%s = %s conflicts with open fact %s (since %s)",
                new_fact.subject,
                new_fact.predicate,
                new_fact.object,
                old_fact.object,
                old_fact.valid_from,
            )
