"""Taxonomy and core checks for memory-bank linting."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

_PLAN_PATH_PATTERN = "Plan:"
_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]|\[[^\]]+\]\(([^)]+)\)")
_CLAIM_PATTERN_GROUP = re.compile(r"\((?P<key>[^)]+)\):\s*(?P<value>.+)")


class LintFinding(BaseModel):
    """Structured finding emitted by lint checks."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    severity: Literal["error", "warning", "info"] = Field(
        description="Finding severity level"
    )
    check: str = Field(description="Stable check identifier")
    message: str = Field(description="Human-readable finding message")
    file: str | None = Field(default=None, description="Path related to finding")
    line: int | None = Field(default=None, ge=1, description="1-based line number")


class LintCheck(Protocol):
    """Contract for a memory-bank lint check."""

    name: str

    def run(self, project_root: Path) -> list[LintFinding]:
        """Run check and return findings."""
        ...


class _PlanReference(BaseModel):
    """Roadmap plan reference parsed from one line."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    raw_path: str = Field(description="Plan path as written in roadmap")
    line: int = Field(ge=1, description="1-based line index in roadmap")


class _CodeClaimSpec(BaseModel):
    """One configured code-claim assertion."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="Path to source claim file")
    pattern: str = Field(description="Regex pattern used to find claim")
    verify_against: str = Field(description="Path to verification target file")


class _LintConfig(BaseModel):
    """Subset of lint config used by CodeClaimCheck."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    code_claim_checks: list[_CodeClaimSpec] = []


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a file path."""
    return path.read_text(encoding="utf-8")


def _plans_root(project_root: Path) -> Path:
    """Return .cortex/plans root for this project."""
    return get_cortex_path(project_root, CortexResourceType.PLANS)


def _roadmap_path(project_root: Path) -> Path:
    """Return .cortex/memory-bank/roadmap.md path."""
    return get_cortex_path(project_root, CortexResourceType.MEMORY_BANK) / "roadmap.md"


def _wiki_root(project_root: Path) -> Path:
    """Return `.cortex/wiki` root for this project."""
    return get_cortex_path(project_root, CortexResourceType.CORTEX_DIR) / "wiki"


def _memory_bank_root(project_root: Path) -> Path:
    """Return `.cortex/memory-bank` root for this project."""
    return get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)


def _lint_config_path(project_root: Path) -> Path:
    """Return `.cortex/lint-config.json` path for this project."""
    return (
        get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
        / "lint-config.json"
    )


def _resolve_project_relative_path(project_root: Path, raw_path: str) -> Path:
    """Resolve relative-to-project path from config entry."""
    normalized = raw_path.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith(".cortex/"):
        normalized = normalized[len(".cortex/") :]
        return get_cortex_path(project_root, CortexResourceType.CORTEX_DIR) / normalized
    return project_root / normalized


def _normalize_plan_ref(raw_path: str) -> Path:
    """Normalize roadmap Plan path into path relative to .cortex/plans."""
    trimmed = raw_path.strip().rstrip(".,)")
    if trimmed.startswith(".cortex/plans/"):
        return Path(trimmed[len(".cortex/plans/") :])
    if trimmed.startswith("cortex/plans/"):
        return Path(trimmed[len("cortex/plans/") :])
    if trimmed.startswith("plans/"):
        return Path(trimmed[len("plans/") :])
    return Path(trimmed)


def _extract_plan_references(roadmap_content: str) -> list[_PlanReference]:
    """Return `Plan:` references found in roadmap lines."""
    references: list[_PlanReference] = []
    for line_num, line in enumerate(roadmap_content.splitlines(), start=1):
        marker_index = line.find(_PLAN_PATH_PATTERN)
        if marker_index < 0:
            continue
        path_part = line[marker_index + len(_PLAN_PATH_PATTERN) :].strip()
        if not path_part:
            continue
        references.append(_PlanReference(raw_path=path_part.split()[0], line=line_num))
    return references


def _list_non_archived_plans(project_root: Path) -> list[Path]:
    """List `.md` plan paths relative to `.cortex/plans`, excluding archive."""
    plans_root = _plans_root(project_root)
    if not plans_root.exists():
        return []
    archive_dir_name = Path(CortexResourceType.PLANS_ARCHIVE.value).name
    results: list[Path] = []
    for plan_path in plans_root.rglob("*.md"):
        relative = plan_path.relative_to(plans_root)
        if archive_dir_name in relative.parts:
            continue
        results.append(relative)
    return sorted(results)


class OrphanedPlansCheck:
    """Find plan files not referenced by roadmap `Plan:` entries."""

    name = "orphaned_plans"

    def run(self, project_root: Path) -> list[LintFinding]:
        roadmap = _roadmap_path(project_root)
        if not roadmap.exists():
            return []
        referenced = {
            _normalize_plan_ref(ref.raw_path)
            for ref in _extract_plan_references(_read_text(roadmap))
        }
        findings: list[LintFinding] = []
        for relative_plan in _list_non_archived_plans(project_root):
            if relative_plan in referenced:
                continue
            findings.append(
                LintFinding(
                    severity="warning",
                    check=self.name,
                    message=f"Plan is not referenced in roadmap: .cortex/plans/{relative_plan}",
                    file=f".cortex/plans/{relative_plan}",
                    line=None,
                )
            )
        return findings


class MissingPlanFilesCheck:
    """Find roadmap `Plan:` references whose target file is missing."""

    name = "missing_plan_files"

    def run(self, project_root: Path) -> list[LintFinding]:
        roadmap = _roadmap_path(project_root)
        if not roadmap.exists():
            return []
        findings: list[LintFinding] = []
        for ref in _extract_plan_references(_read_text(roadmap)):
            relative_plan = _normalize_plan_ref(ref.raw_path)
            target = _plans_root(project_root) / relative_plan
            if target.exists():
                continue
            findings.append(
                LintFinding(
                    severity="error",
                    check=self.name,
                    message=f"Roadmap references missing plan file: {ref.raw_path.rstrip('.,)')}",
                    file=".cortex/memory-bank/roadmap.md",
                    line=ref.line,
                )
            )
        return findings


def _extract_iso_dates_with_lines(content: str) -> list[tuple[str, int]]:
    """Extract unique ISO dates with first-seen line numbers."""
    dates: list[tuple[str, int]] = []
    seen: set[str] = set()
    for line_num, line in enumerate(content.splitlines(), start=1):
        for match in _DATE_PATTERN.finditer(line):
            date_text = match.group(1)
            if date_text in seen:
                continue
            seen.add(date_text)
            dates.append((date_text, line_num))
    return dates


def _parse_iso_date(date_text: str) -> datetime | None:
    """Parse `YYYY-MM-DD` into UTC midnight datetime."""
    try:
        parsed = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC)


class StaleActiveContextCheck:
    """Find stale activeContext dates not represented in progress.md."""

    name = "stale_active_context"

    def __init__(self, stale_threshold_days: int = 30) -> None:
        self._stale_threshold_days = stale_threshold_days

    def _is_stale_without_progress(
        self,
        *,
        date_text: str,
        parsed_date: datetime | None,
        now_utc: datetime,
        progress_content: str,
    ) -> bool:
        if parsed_date is None:
            return False
        threshold = timedelta(days=self._stale_threshold_days)
        if now_utc - parsed_date <= threshold:
            return False
        return date_text not in progress_content

    def _build_finding(self, date_text: str, line_num: int) -> LintFinding:
        return LintFinding(
            severity="warning",
            check=self.name,
            message=(
                "Stale activeContext entry date has no matching progress entry: "
                f"{date_text}"
            ),
            file=".cortex/memory-bank/activeContext.md",
            line=line_num,
        )

    def run(self, project_root: Path) -> list[LintFinding]:
        memory_bank_root = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
        active_context = memory_bank_root / "activeContext.md"
        progress = memory_bank_root / "progress.md"
        if not active_context.exists() or not progress.exists():
            return []

        now_utc = datetime.now(UTC)
        progress_content = _read_text(progress)
        findings: list[LintFinding] = []
        for date_text, line_num in _extract_iso_dates_with_lines(
            _read_text(active_context)
        ):
            parsed_date = _parse_iso_date(date_text)
            if not self._is_stale_without_progress(
                date_text=date_text,
                parsed_date=parsed_date,
                now_utc=now_utc,
                progress_content=progress_content,
            ):
                continue
            findings.append(self._build_finding(date_text=date_text, line_num=line_num))
        return findings


class CrossRefCheck:
    """Find references to wiki pages whose files do not exist."""

    name = "cross_ref"

    def _existing_wiki_pages(self, wiki_root: Path) -> set[str]:
        existing: set[str] = set()
        for page in wiki_root.rglob("*.md"):
            existing.add(page.relative_to(wiki_root).as_posix())
        return existing

    def _iter_references(self, content: str) -> list[tuple[str, int]]:
        references: list[tuple[str, int]] = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            for match in _WIKI_LINK_PATTERN.finditer(line):
                target = match.group(1) or match.group(2)
                if not target:
                    continue
                normalized = target.strip().replace("\\", "/")
                if not normalized or normalized.startswith(
                    ("http://", "https://", "#")
                ):
                    continue
                if normalized.startswith("/"):
                    normalized = normalized[1:]
                if not normalized.endswith(".md"):
                    normalized = f"{normalized}.md"
                references.append((normalized, line_num))
        return references

    def run(self, project_root: Path) -> list[LintFinding]:
        wiki_root = _wiki_root(project_root)
        if not wiki_root.exists():
            return []
        existing = self._existing_wiki_pages(wiki_root)
        findings: list[LintFinding] = []
        for source_file in wiki_root.rglob("*.md"):
            relative_source = source_file.relative_to(wiki_root).as_posix()
            for target, line_num in self._iter_references(_read_text(source_file)):
                if target in existing:
                    continue
                findings.append(
                    LintFinding(
                        severity="warning",
                        check=self.name,
                        message=f"Wiki reference points to missing page: {target}",
                        file=f".cortex/wiki/{relative_source}",
                        line=line_num,
                    )
                )
        return findings


class OrphanedWikiPagesCheck:
    """Find wiki pages without inbound links from wiki or memory-bank files."""

    name = "orphaned_wiki_pages"

    def _normalize_target(self, target: str) -> str | None:
        normalized = target.strip().replace("\\", "/")
        if not normalized or normalized.startswith(("http://", "https://", "#")):
            return None
        if normalized.startswith("/"):
            normalized = normalized[1:]
        if not normalized.endswith(".md"):
            normalized = f"{normalized}.md"
        return normalized

    def _iter_targets(self, content: str) -> list[str]:
        targets: list[str] = []
        for line in content.splitlines():
            for match in _WIKI_LINK_PATTERN.finditer(line):
                raw_target = match.group(1) or match.group(2)
                if not raw_target:
                    continue
                normalized = self._normalize_target(raw_target)
                if normalized is None:
                    continue
                targets.append(normalized)
        return targets

    def _memory_bank_sources(self, project_root: Path) -> list[Path]:
        memory_bank_root = _memory_bank_root(project_root)
        if not memory_bank_root.exists():
            return []
        return sorted(memory_bank_root.rglob("*.md"))

    def _collect_inbound_links(
        self, project_root: Path, wiki_root: Path, wiki_pages: list[Path]
    ) -> tuple[set[str], set[str]]:
        existing_pages = {page.relative_to(wiki_root).as_posix() for page in wiki_pages}
        inbound_links: set[str] = set()
        wiki_pages_with_outbound_links: set[str] = set()
        for wiki_page in wiki_pages:
            relative_source = wiki_page.relative_to(wiki_root).as_posix()
            for target in self._iter_targets(_read_text(wiki_page)):
                if target in existing_pages:
                    wiki_pages_with_outbound_links.add(relative_source)
                    inbound_links.add(target)
        for memory_bank_file in self._memory_bank_sources(project_root):
            for target in self._iter_targets(_read_text(memory_bank_file)):
                if target in existing_pages:
                    inbound_links.add(target)
        return inbound_links, wiki_pages_with_outbound_links

    def _build_findings(
        self,
        wiki_root: Path,
        wiki_pages: list[Path],
        inbound_links: set[str],
        linked_roots: set[str],
    ) -> list[LintFinding]:
        findings: list[LintFinding] = []
        for wiki_page in wiki_pages:
            relative_page = wiki_page.relative_to(wiki_root).as_posix()
            if relative_page == "index.md" and relative_page in linked_roots:
                continue
            if relative_page in inbound_links:
                continue
            findings.append(
                LintFinding(
                    severity="warning",
                    check=self.name,
                    message=f"Wiki page has no inbound links: {relative_page}",
                    file=f".cortex/wiki/{relative_page}",
                    line=None,
                )
            )
        return findings

    def run(self, project_root: Path) -> list[LintFinding]:
        wiki_root = _wiki_root(project_root)
        if not wiki_root.exists():
            return []
        wiki_pages = sorted(wiki_root.rglob("*.md"))
        inbound_links, linked_roots = self._collect_inbound_links(
            project_root, wiki_root, wiki_pages
        )
        return self._build_findings(wiki_root, wiki_pages, inbound_links, linked_roots)


class CodeClaimCheck:
    """Validate configured claims in docs against source-of-truth files."""

    name = "code_claim"

    def _load_config(self, project_root: Path) -> _LintConfig | None:
        config_path = _lint_config_path(project_root)
        if not config_path.exists():
            return None
        try:
            return _LintConfig.model_validate_json(_read_text(config_path))
        except ValueError:
            return None

    def _extract_claim_value(
        self,
        *,
        line: str,
        line_num: int,
    ) -> tuple[str, str, int] | None:
        match = _CLAIM_PATTERN_GROUP.search(line)
        if match is None:
            return None
        key = match.group("key").strip()
        value = match.group("value").strip()
        if not key or not value:
            return None
        return key, value, line_num

    def _claims_from_file(
        self,
        *,
        claim_path: Path,
        pattern: re.Pattern[str],
    ) -> list[tuple[str, str, int]]:
        claims: list[tuple[str, str, int]] = []
        for line_num, line in enumerate(_read_text(claim_path).splitlines(), start=1):
            if pattern.search(line) is None:
                continue
            parsed = self._extract_claim_value(
                line=line,
                line_num=line_num,
            )
            if parsed is None:
                continue
            claims.append(parsed)
        return claims

    def _actual_values(self, verify_path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in _read_text(verify_path).splitlines():
            parsed = self._extract_claim_value(
                line=line,
                line_num=1,
            )
            if parsed is None:
                continue
            key, value, _ = parsed
            values[key] = value
        return values

    def _mismatch_finding(
        self,
        *,
        key: str,
        expected_value: str,
        actual_value: str,
        claim_file: str,
        line_num: int,
    ) -> LintFinding:
        return LintFinding(
            severity="warning",
            check=self.name,
            message=(
                "Claim value does not match verification file for "
                f"'{key}': expected '{expected_value}', actual '{actual_value}'"
            ),
            file=claim_file,
            line=line_num,
        )

    def _resolve_claim_paths(
        self, *, claim_spec: _CodeClaimSpec, project_root: Path
    ) -> tuple[Path, Path] | None:
        claim_path = _resolve_project_relative_path(project_root, claim_spec.file)
        verify_path = _resolve_project_relative_path(
            project_root, claim_spec.verify_against
        )
        if not claim_path.exists() or not verify_path.exists():
            return None
        return claim_path, verify_path

    def _findings_for_spec(
        self, *, claim_spec: _CodeClaimSpec, project_root: Path
    ) -> list[LintFinding]:
        resolved_paths = self._resolve_claim_paths(
            claim_spec=claim_spec, project_root=project_root
        )
        if resolved_paths is None:
            return []
        claim_path, verify_path = resolved_paths
        pattern = re.compile(claim_spec.pattern)
        actual_values = self._actual_values(verify_path)
        findings: list[LintFinding] = []
        for key, expected_value, line_num in self._claims_from_file(
            claim_path=claim_path, pattern=pattern
        ):
            actual_value = actual_values.get(key)
            if actual_value is None or actual_value == expected_value:
                continue
            findings.append(
                self._mismatch_finding(
                    key=key,
                    expected_value=expected_value,
                    actual_value=actual_value,
                    claim_file=claim_spec.file,
                    line_num=line_num,
                )
            )
        return findings

    def run(self, project_root: Path) -> list[LintFinding]:
        config = self._load_config(project_root)
        if config is None or not config.code_claim_checks:
            return []

        findings: list[LintFinding] = []
        for claim_spec in config.code_claim_checks:
            findings.extend(
                self._findings_for_spec(
                    claim_spec=claim_spec, project_root=project_root
                )
            )
        return findings
